"""Exercise CLI scanning and dry-run on generated audio, optionally in a release exe."""
import argparse
from contextlib import closing
import csv
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='audioclean-release-') as temporary:
        work = Path(temporary)
        music = work/'music'
        music.mkdir()
        original = music/'original.wav'
        with wave.open(str(original), 'wb') as audio:
            audio.setparams((1, 2, 44100, 0, 'NONE', 'not compressed'))
            frames = b''.join(struct.pack('<h', int(12000*math.sin(2*math.pi*440*i/44100))) for i in range(44100*12))
            audio.writeframes(frames)
        shutil.copy2(original, music/'binary-copy.wav')
        shutil.copy2(original, music/'metadata-copy.wav')
        with (music/'metadata-copy.wav').open('ab') as audio:
            audio.write(b'audit metadata')
        before = {p.name: p.read_bytes() for p in music.iterdir()}
        spectral_music = work/'spectral-music'
        spectral_music.mkdir()
        lowpass = spectral_music/'lowpass.flac'
        ffmpeg = shutil.which('ffmpeg')
        if not ffmpeg:
            raise RuntimeError('FFmpeg is required to generate the spectral smoke fixture')
        subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                        'anoisesrc=sample_rate=44100:duration=12:seed=381',
                        '-af', 'lowpass=f=12000:p=2,lowpass=f=12000:p=2,lowpass=f=12000:p=2',
                        str(lowpass)], check=True, capture_output=True, timeout=30,
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        env = dict(os.environ, APPDATA=str(work/'appdata'))
        command = [str(args.exe.resolve())] if args.exe else [sys.executable, '-B', str(root/'main.py')]
        if args.exe:
            # The standalone package must find its own audio tools.
            env['PATH'] = str(Path(os.environ.get('SystemRoot', 'C:/Windows'))/'System32')
        gui_env = dict(env, QT_QPA_PLATFORM='offscreen')
        gui_run = subprocess.run(
            command + ['--gui-smoke-test'], cwd=work, env=gui_env,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if gui_run.returncode:
            raise RuntimeError(
                f'GUI import failed: {gui_run.returncode}\n{gui_run.stdout}\n{gui_run.stderr}'
            )
        for attempt in range(2):
            output = work/f'results-{attempt}.csv'
            run = subprocess.run(command + ['--cli', '--folder', str(music), '--db', str(work/'cache.db'),
                '--dry-run', '--auto-move', str(work/'backup'), '--export-csv', str(output)],
                cwd=work, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if run.returncode:
                raise RuntimeError(f'CLI failed: {run.returncode}\n{run.stdout}\n{run.stderr}')
            with output.open(encoding='utf-8', newline='') as handle:
                rows = list(csv.DictReader(handle))
            assert len(rows) == 3, rows
            assert {row['Tipo Duplicado'] for row in rows} == {'EXACT_AUDIO'}, rows
            assert sum(row['Acción Recomendada'] == 'CONSERVAR' for row in rows) == 1
            assert {p.name: p.read_bytes() for p in music.iterdir()} == before
            assert not (work/'backup').exists(), 'dry-run performed a move'
        spectral_db = work/'spectral-cache.db'
        spectral_run = subprocess.run(
            command + ['--cli', '--folder', str(spectral_music), '--db', str(spectral_db), '--dry-run'],
            cwd=work, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if spectral_run.returncode:
            raise RuntimeError(f'Spectral CLI failed: {spectral_run.returncode}\n{spectral_run.stdout}\n{spectral_run.stderr}')
        with closing(sqlite3.connect(spectral_db)) as connection:
            spectral_state = connection.execute(
                'SELECT spectral_assessment FROM tracks WHERE filepath = ?', (str(lowpass),)
            ).fetchone()[0]
        assert spectral_state == 'suspected_transcode', spectral_state
        print(json.dumps({'status':'passed', 'mode':'packaged' if args.exe else 'source',
                          'gui_import':True, 'scans':3, 'files':4, 'classification':'EXACT_AUDIO',
                          'spectral_assessment':spectral_state, 'dry_run_preserved_files':True}))


if __name__ == '__main__':
    main()
