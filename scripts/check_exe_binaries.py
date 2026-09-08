"""Verify actual PyInstaller archive entries instead of byte substrings."""
import argparse
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader


def check_archive(path):
    archive = CArchiveReader(str(path))
    entries = {name.replace(chr(92), '/').lower() for name in archive.toc}
    required = {f'bin/{name}.exe' for name in ('ffmpeg', 'ffprobe', 'fpcalc')}
    missing = required - entries
    forbidden = {name for name in entries if name.endswith(('.db', '.sqlite', '.sqlite3'))}
    if missing or forbidden:
        raise RuntimeError(f'Invalid package: missing={sorted(missing)}, databases={sorted(forbidden)}')
    print('Verified: FFmpeg, FFprobe and Chromaprint bundled; no user databases.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?', type=Path,
                        default=Path(__file__).resolve().parents[1]/'dist'/'AudioDuplicateDetector.exe')
    check_archive(parser.parse_args().path)
