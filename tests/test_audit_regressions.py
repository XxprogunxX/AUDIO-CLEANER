"""Regressions for the September 2026 audit; all files are disposable fixtures."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from core.clustering import cluster_duplicates, DuplicateGroupList
from core.config import DetectionConfig
from core.database import Database
from core.file_manager import FileOperationService, OperationJournal, OperationStatus
from core.fingerprint import AudioStreamInfo, verify_full_normalized_pcm_match
from core.models import AudioTrack, DuplicateGroup, DuplicateType, FileAction, EvidenceReport, ScanCoverageReport
from core.scanner import AudioScanner
from core.session_manager import load_session_safe, save_session_atomic
from core.spectral_types import SpectralAssessment


def local_pool(**kwargs):
    return ThreadPoolExecutor(max_workers=kwargs['max_workers'])


class TestGroupingSafety(unittest.TestCase):
    def test_acoustic_similarity_never_selects_files_automatically(self):
        tracks = [AudioTrack(filepath=p, quality_score=2-i, fingerprint_raw=[17, 33, 49])
                  for i, p in enumerate(('A', 'B'))]
        report = EvidenceReport('A', 'B', DuplicateType.ACOUSTIC_DUPLICATE, 99.9)
        with patch('core.clustering.ProcessPoolExecutor', side_effect=local_pool), \
             patch('core.clustering.compare_tracks', return_value=report):
            groups = cluster_duplicates(tracks)
        self.assertEqual(groups[0].primary_type, DuplicateType.ACOUSTIC_DUPLICATE)
        self.assertTrue(groups[0].requires_manual_review)
        self.assertTrue(all(t.action == FileAction.UNSET for t in groups[0].tracks))

    def test_negative_or_missing_edge_to_retained_copy_requires_review(self):
        for missing_kind in (DuplicateType.NO_MATCH, DuplicateType.UNCERTAIN):
            with self.subTest(missing_kind=missing_kind):
                tracks = [AudioTrack(filepath=p, quality_score=3-i, fingerprint_raw=[17, 33, 49])
                          for i, p in enumerate('ABC')]
                def compare(a, b, config=None):
                    kind = missing_kind if {a.filepath, b.filepath} == {'A', 'C'} else DuplicateType.ACOUSTIC_DUPLICATE
                    return EvidenceReport(a.filepath, b.filepath, kind, 98)
                with patch('core.clustering.ProcessPoolExecutor', side_effect=local_pool), patch('core.clustering.compare_tracks', side_effect=compare):
                    groups = cluster_duplicates(tracks)
                self.assertEqual(len(groups), 1)
                self.assertTrue(groups[0].requires_manual_review)
                self.assertTrue(all(t.action == FileAction.UNSET for t in groups[0].tracks))

    def test_ten_thousand_exact_copies_need_linear_evidence_and_no_pcm(self):
        tracks = [AudioTrack(filepath=f'{i:05}.wav', sha256='same', audio_hash='same-prefix') for i in range(10000)]
        with patch('core.clustering.EvidenceReport', wraps=EvidenceReport) as reports, patch('core.fingerprint.verify_full_normalized_pcm_match') as pcm:
            groups = cluster_duplicates(tracks)
        self.assertEqual(len(groups[0].tracks), 10000)
        self.assertEqual(reports.call_count, 9999)
        pcm.assert_not_called()
        self.assertFalse(groups[0].requires_manual_review)

    def test_high_hit_pairs_cannot_exceed_admission_cap(self):
        tracks = [AudioTrack(filepath=str(i), fingerprint_raw=list(range(1, 40))) for i in range(30)]
        with patch('core.clustering.ProcessPoolExecutor', side_effect=local_pool):
            groups, coverage = cluster_duplicates(tracks, max_pair_hits=5, return_coverage=True)
        self.assertLessEqual(coverage.candidate_pairs_retained, 5)
        self.assertFalse(coverage.is_complete)
        self.assertGreater(coverage.candidate_pairs_dropped, 0)

    def test_cancel_interrupts_exact_phase(self):
        calls = 0
        def cancel():
            nonlocal calls
            calls += 1
            return calls > 10
        tracks = [AudioTrack(filepath=str(i), sha256='same') for i in range(1000)]
        groups, coverage = cluster_duplicates(tracks, is_cancelled=cancel, return_coverage=True)
        self.assertEqual(groups, [])
        self.assertFalse(coverage.is_complete)
        self.assertEqual(coverage.scan_status, 'CANCELLED')
        self.assertLess(calls, 20)

    def test_unproven_acoustic_operation_leaves_real_files_intact(self):
        with tempfile.TemporaryDirectory() as folder:
            files = [Path(folder) / name for name in ('keep', 'delete')]
            for p in files:
                p.write_bytes(b'fixture')
            tracks = [AudioTrack(filepath=str(p), action=FileAction.KEEP if i == 0 else FileAction.DELETE)
                      for i, p in enumerate(files)]
            group = DuplicateGroup('unsafe', DuplicateType.ACOUSTIC_DUPLICATE, tracks, str(files[0]))
            result = FileOperationService.delete_permanently([group], journal_path=str(Path(folder)/'journal.db'))
            self.assertEqual(result.success, 0)
            self.assertEqual(result.blocked, 1)
            self.assertTrue(all(p.exists() for p in files))


class TestPCMExecution(unittest.TestCase):
    def run_process_comparison(self, programs, **kwargs):
        info = AudioStreamInfo('pcm_s16le', 44100, 2, 'stereo', 's16', 16, True)
        real_popen = subprocess.Popen
        launched, commands = [], []
        def launch(command, **options):
            commands.append(command)
            proc = real_popen([sys.executable, '-c', programs[len(launched)]], **options)
            launched.append(proc)
            return proc
        with patch('core.fingerprint.os.path.isfile', return_value=True), patch('core.fingerprint.get_audio_stream_info', return_value=info), patch('core.fingerprint.get_ffmpeg_path', return_value='C:/bundled/ffmpeg.exe'), patch('core.fingerprint.subprocess.Popen', side_effect=launch):
            result = verify_full_normalized_pcm_match('A', 'B', **kwargs)
        self.assertTrue(all(p.poll() is not None for p in launched))
        self.assertTrue(all(c[0] == 'C:/bundled/ffmpeg.exe' for c in commands))
        return result

    def test_equal_streams_with_different_read_boundaries(self):
        programs = ["import sys;sys.stdout.buffer.write(b'a'*100000)",
                    "import sys,time;sys.stdout.buffer.write(b'a'*100);sys.stdout.buffer.flush();time.sleep(.05);sys.stdout.buffer.write(b'a'*99900)"]
        self.assertTrue(self.run_process_comparison(programs, total_timeout=5))

    def test_stalled_process_is_terminated(self):
        start = time.monotonic()
        self.assertFalse(self.run_process_comparison(['import time;time.sleep(30)']*2, stall_timeout=.2, total_timeout=5))
        self.assertLess(time.monotonic()-start, 5)

    def test_total_timeout_applies_despite_continuous_output(self):
        program = "import sys,time\nwhile True:\n sys.stdout.buffer.write(b'x'*1024);sys.stdout.buffer.flush();time.sleep(.01)"
        self.assertFalse(self.run_process_comparison([program]*2, stall_timeout=2, total_timeout=.25))

    def test_cancellation_terminates_children(self):
        self.assertFalse(self.run_process_comparison(['import time;time.sleep(30)']*2, is_cancelled=lambda: True))

    def test_nonzero_exit_and_different_streams_are_rejected(self):
        for programs in (["print('same');raise SystemExit(1)", "print('same')"], ["print('a')", "print('b')"]):
            with self.subTest(programs=programs):
                self.assertFalse(self.run_process_comparison(programs, total_timeout=5))


class TestCacheAndCoverage(unittest.TestCase):
    def test_extraction_options_invalidate_cache_and_spectral_state_roundtrips(self):
        with tempfile.TemporaryDirectory() as folder, Database(':memory:') as db:
            path = Path(folder) / 'audio.wav'
            path.write_bytes(b'fixture')
            def worker(filepath, min_duration, spectral_analysis):
                from core.cache_signature import compute_quick_signature
                stat = path.stat()
                return dict(filepath=filepath, filesize=stat.st_size, mtime=stat.st_mtime,
                    mtime_ns=stat.st_mtime_ns, quick_signature=compute_quick_signature(filepath),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(), audio_hash='', duration=10,
                    format='WAV', bitrate=1000, samplerate=44100, channels=2, bit_depth=16,
                    is_lossless=True, spectral_cutoff=0, fake_lossless_confidence=0,
                    spectral_assessment=SpectralAssessment.UNKNOWN if spectral_analysis else SpectralAssessment.NOT_ANALYZED,
                    fingerprint_raw=[1,2,3] if min_duration <= 10 else [], title='', artist='', album='')
            with patch('core.scanner.ProcessPoolExecutor', side_effect=local_pool), patch('core.scanner._process_audio_worker', side_effect=worker) as process:
                for config, count in ((DetectionConfig(min_duration=20, spectral_analysis=False), 1),
                                      (DetectionConfig(min_duration=20, spectral_analysis=False), 1),
                                      (DetectionConfig(min_duration=5, spectral_analysis=False), 2),
                                      (DetectionConfig(min_duration=5, spectral_analysis=True), 3)):
                    AudioScanner(db, max_workers=1, detection_config=config).scan_directory(folder)
                    self.assertEqual(process.call_count, count)
                    cached = db.get_track(str(path))
                    self.assertEqual(cached.spectral_assessment, SpectralAssessment.UNKNOWN if config.spectral_analysis else SpectralAssessment.NOT_ANALYZED)

    def test_worker_error_counted_once_and_coverage_propagated(self):
        with tempfile.TemporaryDirectory() as folder, Database(':memory:') as db:
            (Path(folder)/'bad.wav').write_bytes(b'x')
            coverage = ScanCoverageReport(is_complete=False, is_approximate=True, candidate_pairs_dropped=9, worker_failures=2)
            scanner = AudioScanner(db, max_workers=1)
            with patch('core.scanner.ProcessPoolExecutor', side_effect=local_pool), patch('core.scanner._process_audio_worker', side_effect=OSError('fixture error')), patch('core.scanner.cluster_duplicates', return_value=DuplicateGroupList([], coverage)):
                scanner.scan_directory(folder)
            self.assertEqual(scanner.stats.files_failed, 1)
            self.assertEqual(scanner.stats.worker_failures, 2)
            self.assertEqual(scanner.stats.candidate_pairs_dropped, 9)
            self.assertFalse(scanner.stats.is_complete)
            self.assertTrue(scanner.stats.is_approximate)


class TestSessionRecovery(unittest.TestCase):
    def test_saving_after_corruption_preserves_last_valid_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'session.json'
            backup = Path(str(path)+'.bak')
            backup.write_text(json.dumps({'folder': 'good', 'groups': []}), encoding='utf-8')
            path.write_text('{"groups":null}', encoding='utf-8')
            self.assertTrue(save_session_atomic(str(path), 'new', []))
            self.assertEqual(json.loads(backup.read_text(encoding='utf-8'))['folder'], 'good')

    def test_valid_json_with_invalid_structure_recovers_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'session.json'
            Path(str(path)+'.bak').write_text(json.dumps({'folder':'backup', 'groups':[]}), encoding='utf-8')
            for payload in ([], 42, {'groups': None}, {'groups': {}}, {'folder': [], 'groups': []}):
                with self.subTest(payload=payload):
                    path.write_text(json.dumps(payload), encoding='utf-8')
                    self.assertEqual(load_session_safe(str(path)), ('backup', []))

    def test_acoustic_legacy_session_cannot_replay_unproven_delete(self):
        group = DuplicateGroup('g', DuplicateType.ACOUSTIC_DUPLICATE,
            [AudioTrack('A', action=FileAction.KEEP), AudioTrack('B', action=FileAction.DELETE)], 'A')
        restored = DuplicateGroup.from_dict(group.to_dict())
        self.assertTrue(restored.requires_manual_review)
        self.assertEqual(restored.tracks[1].action, FileAction.UNSET)

    def test_pair_evidence_survives_session_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder)/'session.json')
            group = DuplicateGroup('g', DuplicateType.ACOUSTIC_DUPLICATE,
                [AudioTrack('A'), AudioTrack('B')], 'A', verified_pairs=[['A','B']])
            self.assertTrue(save_session_atomic(path, folder, [group]))
            restored = load_session_safe(path)[1][0]
            self.assertTrue(restored.requires_manual_review)
            self.assertEqual(restored.verified_pairs, [['A','B']])


class TestVerifiedBackupRecovery(unittest.TestCase):
    def make_group(self, folder):
        keep, delete = Path(folder)/'keep.wav', Path(folder)/'delete.wav'
        keep.write_bytes(b'original-audio')
        delete.write_bytes(keep.read_bytes())
        digest = hashlib.sha256(keep.read_bytes()).hexdigest()
        tracks = [AudioTrack(str(keep), sha256=digest, action=FileAction.KEEP),
                  AudioTrack(str(delete), sha256=digest, action=FileAction.DELETE)]
        return DuplicateGroup('exact', DuplicateType.EXACT_HASH, tracks, str(keep)), keep, delete

    @staticmethod
    def journal_state(path):
        connection = sqlite3.connect(path)
        try:
            return connection.execute('SELECT state FROM operation_journal').fetchone()[0]
        finally:
            connection.close()

    def test_backup_blocks_source_changed_after_scan(self):
        with tempfile.TemporaryDirectory() as folder:
            group, _, delete = self.make_group(folder)
            delete.write_bytes(b'a-different-recording')
            destination = Path(folder)/'backup'
            result = FileOperationService.backup(
                [group], str(destination), journal_path=str(Path(folder)/'journal.db'))
            self.assertEqual(result.status, OperationStatus.FAILED)
            self.assertTrue(delete.exists())
            self.assertFalse(destination.exists() and any(destination.iterdir()))

    def test_interrupted_copy_removes_partial_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            group, _, delete = self.make_group(folder)
            destination = Path(folder)/'backup'
            def partial_copy(source, target, length):
                target.write(source.read(4))
                target.flush()
                raise OSError('simulated interrupted copy')
            with patch('core.file_manager.shutil.copyfileobj', side_effect=partial_copy):
                result = FileOperationService.backup(
                    [group], str(destination), journal_path=str(Path(folder)/'journal.db'))
            self.assertEqual(result.status, OperationStatus.FAILED)
            self.assertTrue(delete.exists())
            self.assertEqual(list(destination.iterdir()), [])

    def test_reconcile_preserves_ambiguous_artifacts_when_source_exists(self):
        with tempfile.TemporaryDirectory() as folder:
            group, _, delete = self.make_group(folder)
            target, temporary = Path(folder)/'backup.wav', Path(folder)/'partial.tmp'
            target.write_bytes(delete.read_bytes())
            temporary.write_bytes(b'partial')
            digest = hashlib.sha256(delete.read_bytes()).hexdigest()
            journal_path = str(Path(folder)/'journal.db')
            journal = OperationJournal(journal_path)
            journal.record_pending('op', str(delete), 'backup', str(target), str(temporary), digest)
            logs = journal.reconcile()
            self.assertTrue(delete.exists())
            self.assertTrue(target.exists())
            self.assertTrue(temporary.exists())
            self.assertEqual(self.journal_state(journal_path), 'ABORTED')
            self.assertTrue(logs)

    def test_reconcile_accepts_only_verified_destination(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt), tempfile.TemporaryDirectory() as folder:
                group, _, delete = self.make_group(folder)
                target = Path(folder)/'backup.wav'
                expected = hashlib.sha256(delete.read_bytes()).hexdigest()
                target.write_bytes(b'corrupt' if corrupt else delete.read_bytes())
                delete.unlink()
                journal_path = str(Path(folder)/'journal.db')
                journal = OperationJournal(journal_path)
                journal.record_pending('op', str(delete), 'backup', str(target), '', expected)
                with Database(str(Path(folder)/'library.db')) as database:
                    database.upsert_track(group.tracks[1])
                    journal.reconcile(database)
                    cached = database.get_track(str(delete)) is not None
                self.assertEqual(self.journal_state(journal_path), 'FAILED' if corrupt else 'COMPLETED')
                self.assertEqual(cached, corrupt)

    def test_legacy_backup_without_hash_requires_manual_inspection(self):
        with tempfile.TemporaryDirectory() as folder:
            _, _, delete = self.make_group(folder)
            target = Path(folder)/'backup.wav'
            target.write_bytes(delete.read_bytes())
            delete.unlink()
            journal_path = str(Path(folder)/'journal.db')
            journal = OperationJournal(journal_path)
            journal.record_pending('legacy', str(delete), 'backup', str(target))
            journal.reconcile()
            self.assertEqual(self.journal_state(journal_path), 'FAILED')


class TestResponsiveGUI(unittest.TestCase):
    def test_operation_runs_off_ui_thread_while_event_loop_remains_active(self):
        from PyQt6.QtCore import QTimer
        from PyQt6.QtWidgets import QApplication
        from gui.operation_worker import run_file_operation
        from core.file_manager import OperationResult
        app = QApplication.instance() or QApplication([])
        ticks = []
        timer = QTimer()
        timer.timeout.connect(lambda: ticks.append(1))
        timer.start(10)
        owner = threading.get_ident()
        def operation():
            self.assertNotEqual(threading.get_ident(), owner)
            time.sleep(.15)
            return OperationResult(1, 0, [])
        result = run_file_operation(None, operation)
        timer.stop()
        self.assertEqual(result.success, 1)
        self.assertGreater(len(ticks), 0)


if __name__ == '__main__':
    unittest.main()
