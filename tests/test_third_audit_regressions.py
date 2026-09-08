"""Regression coverage for findings from the third independent audit."""
import csv
import hashlib
import io
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from core.clustering import cluster_duplicates
from core.comparator import compare_tracks
import core.file_manager as fm
from core.file_manager import FileOperationService, OperationJournal, OperationResult, OperationStatus
from core.models import AudioTrack, DuplicateGroup, DuplicateType, FileAction, ScanCoverageReport
from core.quality_analyzer import _probe_audio_segment, evaluate_track_quality
from core.spectral_types import SpectralAssessment


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _exact_group(root: Path):
    root.mkdir()
    content = b"third-audit-identical-audio" * 200
    keep, delete = root / "keep.wav", root / "delete.wav"
    keep.write_bytes(content)
    delete.write_bytes(content)
    tracks = [
        AudioTrack(filepath=str(keep), filesize=len(content), sha256=_sha(content), action=FileAction.KEEP),
        AudioTrack(filepath=str(delete), filesize=len(content), sha256=_sha(content), action=FileAction.DELETE),
    ]
    return DuplicateGroup(group_id="third", primary_type=DuplicateType.EXACT_HASH,
                          tracks=tracks, best_track_path=str(keep)), delete


class TestConcurrentFileSafety(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows no-replace rename semantics")
    def test_backup_collision_preserves_foreign_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            group, source = _exact_group(root / "case")
            backup = root / "backup"
            target = backup / source.name
            foreign = b"foreign data created concurrently"
            real_rename = os.rename

            def raced_rename(src, dst):
                if os.path.normcase(str(dst)) == os.path.normcase(str(target)):
                    target.write_bytes(foreign)
                return real_rename(src, dst)

            with patch.object(fm.os, "rename", side_effect=raced_rename):
                result = FileOperationService.backup(
                    [group], str(backup), journal_path=str(root / "journal.db")
                )
            self.assertEqual(result.status, OperationStatus.FAILED)
            self.assertEqual(target.read_bytes(), foreign)
            self.assertTrue(source.exists())

    def test_source_recreated_after_copy_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            group, source = _exact_group(root / "case")
            backup = root / "backup"
            new_version = b"new unique version written concurrently"
            real_copy = fm._copy_backup_verified

            def recreate_source(src, dst, temporary, expected):
                real_copy(src, dst, temporary, expected)
                source.write_bytes(new_version)

            with patch.object(fm, "_copy_backup_verified", side_effect=recreate_source):
                result = FileOperationService.backup(
                    [group], str(backup), journal_path=str(root / "journal.db")
                )
            self.assertEqual(result.status, OperationStatus.FAILED)
            self.assertEqual(source.read_bytes(), new_version)
            self.assertTrue((backup / source.name).exists())

    def test_reconcile_never_removes_ambiguous_final_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            group, source = _exact_group(root / "case")
            target = root / "foreign.wav"
            foreign = b"foreign destination"
            target.write_bytes(foreign)
            journal_path = str(root / "journal.db")
            journal = OperationJournal(journal_path)
            journal.record_pending("pending", str(source), "backup", str(target),
                                   str(root / "private.partial"), group.tracks[1].sha256)
            journal.reconcile()
            self.assertEqual(target.read_bytes(), foreign)
            self.assertTrue(source.exists())


class TestDetectionAndQualityCorrections(unittest.TestCase):
    def test_hamming_tolerant_candidate_reaches_comparator(self):
        a = [(index + 1) * 4096 + 0x120 for index in range(300)]
        b = [value ^ 0x10 for value in a]
        tracks = [AudioTrack(filepath=name, duration=60, fingerprint_raw=fp)
                  for name, fp in (("A.wav", a), ("B.wav", b))]
        direct = compare_tracks(*tracks)
        groups, coverage = cluster_duplicates(tracks, return_coverage=True)
        self.assertEqual(direct.classification, DuplicateType.ACOUSTIC_DUPLICATE)
        self.assertEqual(len(groups), 1)
        self.assertGreaterEqual(coverage.candidate_pairs_retained, 1)
        self.assertTrue(groups[0].requires_manual_review)

    def test_spectral_probe_uses_resolved_binary(self):
        with patch("core.quality_analyzer.get_ffmpeg_path", return_value="C:/bundle/ffmpeg.exe") as resolver:
            with patch("core.quality_analyzer.subprocess.Popen", side_effect=FileNotFoundError) as process:
                self.assertIsNone(_probe_audio_segment("fixture.wav", 0, 4, 44100, 2))
        resolver.assert_called_once_with()
        self.assertEqual(process.call_args.args[0][0], "C:/bundle/ffmpeg.exe")

    def test_unknown_lossless_is_not_labeled_authentic(self):
        track = AudioTrack(filepath="unknown.flac", format="FLAC", is_lossless=True,
                           bitrate=950, samplerate=44100,
                           spectral_assessment=SpectralAssessment.UNKNOWN)
        evaluate_track_quality(track)
        self.assertNotIn("Auténtico", track.quality_details)
        self.assertIn("autenticidad no determinada", track.quality_details)

    def test_unknown_spectrum_has_no_fabricated_bars(self):
        from PyQt6.QtWidgets import QApplication, QLabel
        from gui.components.ab_comparison import SpectralBarsWidget, TrackPanel
        app = QApplication.instance() or QApplication([])
        track = AudioTrack(filepath="unknown.flac", format="FLAC", is_lossless=True,
                           spectral_assessment=SpectralAssessment.UNKNOWN)
        panel = TrackPanel(track, "A")
        self.assertEqual(panel.findChildren(SpectralBarsWidget), [])
        self.assertTrue(any("Sin medición espectral" in label.text()
                            for label in panel.findChildren(QLabel)))
        panel.close()


class TestOperationalEvaluation(unittest.TestCase):
    def test_cli_returns_failure_code_and_closes_database(self):
        import main
        stats = SimpleNamespace(elapsed_seconds=1.0, is_complete=False, files_failed=1,
                                worker_failures=0, candidate_pairs_dropped=0, files_scanned=1,
                                total_files_found=1, phase="Completado",
                                exact_duplicates_count=0, acoustic_duplicates_count=0,
                                possible_duplicates_count=0, potential_space_saving=0)
        args = SimpleNamespace(folder=os.getcwd(), db="mock.db", export_csv=None,
                               auto_move="backup", dry_run=False)
        with patch("core.database.Database") as database, \
             patch("core.scanner.AudioScanner") as scanner, \
             patch("core.file_manager.move_marked_duplicates", return_value=OperationResult(
                 0, 1, ["injected failure"], status=OperationStatus.FAILED)), \
             patch("sys.stdout", new_callable=io.StringIO):
            scanner.return_value.stats = stats
            scanner.return_value.scan_directory.return_value = []
            code = main.run_cli_mode(args)
        self.assertEqual(code, 4)
        database.return_value.close.assert_called_once_with()

    def test_pipeline_evaluation_measures_final_group_recall(self):
        from scripts.evaluation_runner import run_pipeline_evaluation
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = root / "manifest.csv"
            manifest.write_text(
                "track_a_path,track_b_path,expected_category\n"
                "A.wav,B.wav,EXACT_HASH\n"
                "A.wav,C.wav,NO_MATCH\n", encoding="utf-8"
            )
            fake_tracks = {
                str(root / "A.wav"): AudioTrack(filepath=str(root / "A.wav"), sha256="same"),
                str(root / "B.wav"): AudioTrack(filepath=str(root / "B.wav"), sha256="same"),
                str(root / "C.wav"): AudioTrack(filepath=str(root / "C.wav"), sha256="other"),
            }
            for path in fake_tracks:
                Path(path).write_bytes(b"fixture")

            def fake_worker(path):
                track = fake_tracks[path]
                return {**track.to_dict(), "fingerprint_raw": []}

            report_path = root / "pipeline.json"
            with patch("scripts.evaluation_runner._process_audio_worker", side_effect=fake_worker):
                report = run_pipeline_evaluation(str(manifest), str(root), str(report_path))
            self.assertEqual(report["summary"]["recall"], 1.0)
            self.assertEqual(report["summary"]["precision"], 1.0)
            self.assertEqual(report["summary"]["unevaluated_pairs"], 0)


if __name__ == "__main__":
    unittest.main()
