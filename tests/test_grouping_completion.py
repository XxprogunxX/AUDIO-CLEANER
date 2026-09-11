"""Regressions for responsive and cached full-PCM grouping."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core.clustering import cluster_duplicates
from core.database import Database
from core.models import AudioTrack, DuplicateType
from core.scanner import AudioScanner, _process_audio_worker


class TestPcmIdentityCache(unittest.TestCase):
    def test_database_roundtrip_is_keyed_by_file_sha(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "cache.db")
            with Database(path) as database:
                self.assertEqual(database.get_pcm_identities(["sha-a"]), {})
                database.upsert_pcm_identities({"sha-a": "pcm-v1:one", "sha-b": ""})
                self.assertEqual(
                    database.get_pcm_identities(["sha-a", "sha-b", "missing"]),
                    {"sha-a": "pcm-v1:one"},
                )
            with Database(path) as reopened:
                self.assertEqual(reopened.get_pcm_identities(["sha-a"])["sha-a"],
                                 "pcm-v1:one")

    def test_clustering_uses_cached_identity_without_pair_decode(self):
        tracks = [
            AudioTrack("A.flac", sha256="sha-a", audio_hash="prefix", duration=120),
            AudioTrack("B.wav", sha256="sha-b", audio_hash="prefix", duration=120),
        ]
        identities = {"sha-a": "pcm-v1:same", "sha-b": "pcm-v1:same"}
        with patch("core.fingerprint.verify_full_normalized_pcm_match",
                   side_effect=AssertionError("pair decode must not run")):
            groups = cluster_duplicates(tracks, pcm_identities=identities)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].primary_type, DuplicateType.EXACT_AUDIO)

    def test_scanner_computes_once_then_reuses_persistent_cache(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Database(str(Path(folder) / "cache.db"))
            scanner = AudioScanner(database, max_workers=2)
            tracks = [
                AudioTrack("A.flac", sha256="sha-a", audio_hash="prefix", duration=120),
                AudioTrack("B.wav", sha256="sha-b", audio_hash="prefix", duration=120),
                AudioTrack("C.wav", sha256="sha-c", audio_hash="other", duration=90),
            ]
            phases = []
            with patch("core.scanner.compute_full_normalized_pcm_identity",
                       return_value="pcm-v1:same") as compute:
                identities = scanner._prepare_full_pcm_identities(
                    tracks, lambda stats: phases.append(stats.phase)
                )
            self.assertEqual(compute.call_count, 2)
            self.assertEqual(set(identities), {"sha-a", "sha-b"})
            self.assertTrue(any("audio completo" in phase for phase in phases))

            fresh_tracks = [
                AudioTrack("A.flac", sha256="sha-a", audio_hash="prefix", duration=120),
                AudioTrack("B.wav", sha256="sha-b", audio_hash="prefix", duration=120),
            ]
            with patch("core.scanner.compute_full_normalized_pcm_identity") as compute_again:
                reused = scanner._prepare_full_pcm_identities(fresh_tracks)
            compute_again.assert_not_called()
            self.assertEqual(reused, identities)
            self.assertTrue(all(track.full_pcm_identity for track in fresh_tracks))
            database.close()


class TestCoverageDiagnostics(unittest.TestCase):
    def test_oversized_tokens_do_not_report_millions_of_dropped_candidates(self):
        tracks = [
            AudioTrack(f"track-{index}.wav", duration=60, fingerprint_raw=[9999])
            for index in range(10)
        ]
        _, coverage = cluster_duplicates(
            tracks, max_bucket_size=3, return_coverage=True
        )
        self.assertTrue(coverage.is_approximate)
        self.assertTrue(coverage.ambiguous_pair_occurrences_ignored)
        self.assertEqual(coverage.candidate_pairs_dropped, 0)
        self.assertTrue(coverage.is_complete)

    def test_duration_prefilter_is_not_an_incomplete_scan(self):
        tracks = [
            AudioTrack("short.wav", duration=10, fingerprint_raw=[1, 2, 3, 4]),
            AudioTrack("long.wav", duration=200, fingerprint_raw=[1, 2, 3, 4]),
        ]
        _, coverage = cluster_duplicates(tracks, return_coverage=True)
        self.assertGreater(coverage.candidate_pairs_prefiltered, 0)
        self.assertEqual(coverage.candidate_pairs_dropped, 0)
        self.assertTrue(coverage.is_complete)

    def test_empty_audio_is_reported_as_invalid_instead_of_failed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.mp3"
            path.touch()
            result = _process_audio_worker(str(path), spectral_analysis=False)
        self.assertEqual(result["_scan_status"], "skipped_invalid")
        self.assertIn("0 bytes", result["reason"])

    def test_known_windows_system_directories_are_pruned(self):
        with tempfile.TemporaryDirectory() as folder, Database(":memory:") as database:
            recycle = Path(folder) / "$RECYCLE.BIN"
            recycle.mkdir()
            (recycle / "not-music.mp3").touch()
            scanner = AudioScanner(database, max_workers=1)
            scanner.scan_directory(folder)
        self.assertEqual(scanner.stats.total_files_found, 0)
        self.assertEqual(scanner.stats.files_failed, 0)
        self.assertEqual(scanner.stats.system_directories_skipped, 1)

    def test_duration_incompatible_prefixes_need_no_full_decode(self):
        with tempfile.TemporaryDirectory() as folder:
            database = Database(str(Path(folder) / "cache.db"))
            scanner = AudioScanner(database, max_workers=1)
            tracks = [
                AudioTrack("A.flac", sha256="sha-a", audio_hash="prefix", duration=60),
                AudioTrack("B.flac", sha256="sha-b", audio_hash="prefix", duration=61),
            ]
            with patch("core.scanner.compute_full_normalized_pcm_identity") as compute:
                identities = scanner._prepare_full_pcm_identities(tracks)
            compute.assert_not_called()
            self.assertEqual(identities, {})
            database.close()


if __name__ == "__main__":
    unittest.main()
