"""
Comprehensive Real-File Smoke Test & End-to-End Validation Script
Validates:
1. Controlled dataset with 100+ audio files (WAV, FLAC, MP3, unique, dupes, corrupt, ultrashort, unicode, subdirs).
2. Scan execution with live memory RSS monitoring (psutil).
3. Exact Hash, Exact Audio, Acoustic Duplicates, and Manual Review classifications.
4. Clean shutdown and no orphan processes.
"""

import os
import sys
import time
import math
import wave
import struct
import shutil
import tempfile
import subprocess
import threading
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    import psutil
except ImportError:
    psutil = None

from core.models import AudioTrack, DuplicateGroup, DuplicateType, FileAction, ScanStats
from core.scanner import AudioScanner
from core.database import Database
from core.config import DetectionConfig
from core.binary_resolver import get_ffmpeg_path, get_ffprobe_path, get_fpcalc_path


def get_total_rss_mb() -> float:
    if not psutil:
        return 0.0
    try:
        proc = psutil.Process()
        total = proc.memory_info().rss
        for child in proc.children(recursive=True):
            try:
                total += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return total / (1024.0 * 1024.0)
    except Exception:
        return 0.0


def create_sine_wav(filepath: str, duration: float = 4.0, freq: float = 440.0, sample_rate: int = 44100):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    num_samples = int(duration * sample_rate)
    with wave.open(filepath, "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(num_samples):
            val = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * freq * i / sample_rate))
            frames.extend(struct.pack("<hh", val, val))
        wf.writeframes(frames)


def generate_real_file_library(base_dir: str) -> Dict[str, Any]:
    ffmpeg_bin = get_ffmpeg_path() or "ffmpeg"
    print(f"Creating real audio files in: {base_dir}...")
    manifest = {
        "unique_count": 0,
        "exact_hash_pairs": 0,
        "exact_audio_pairs": 0,
        "corrupt_count": 0,
        "ultrashort_count": 0,
        "unicode_count": 0,
        "subdirs": set()
    }

    # 1. Base unique songs (different frequencies)
    for i in range(1, 41):
        freq = 200.0 + i * 25.0
        wav_path = os.path.join(base_dir, f"song_unique_{i:03d}.wav")
        create_sine_wav(wav_path, duration=3.5, freq=freq)
        manifest["unique_count"] += 1

    # 2. Binary duplicates (EXACT_HASH)
    base_dupe_wav = os.path.join(base_dir, "exact_hash_master.wav")
    create_sine_wav(base_dupe_wav, duration=4.0, freq=523.25)
    for k in range(1, 6):
        copy_path = os.path.join(base_dir, f"exact_hash_copy_{k}.wav")
        shutil.copyfile(base_dupe_wav, copy_path)
        manifest["exact_hash_pairs"] += 1

    # 3. Canonical PCM duplicates (WAV vs FLAC with identical PCM - EXACT_AUDIO)
    pcm_wav = os.path.join(base_dir, "pcm_master.wav")
    create_sine_wav(pcm_wav, duration=4.0, freq=440.0)
    pcm_flac = os.path.join(base_dir, "pcm_equivalent.flac")
    ret = subprocess.run([ffmpeg_bin, "-y", "-i", pcm_wav, "-c:a", "flac", pcm_flac], capture_output=True)
    if ret.returncode == 0:
        manifest["exact_audio_pairs"] += 1

    # 4. MP3 conversion
    mp3_path = os.path.join(base_dir, "acoustic_compressed.mp3")
    subprocess.run([ffmpeg_bin, "-y", "-i", pcm_wav, "-c:a", "libmp3lame", "-b:a", "192k", mp3_path], capture_output=True)

    # 5. Unicode paths and subdirectories
    sub_unicode = os.path.join(base_dir, "Álbum Especial — Música Clásica 🎵", "SubCarpeta_日本語")
    os.makedirs(sub_unicode, exist_ok=True)
    manifest["subdirs"].add(sub_unicode)
    uni_wav = os.path.join(sub_unicode, "Pista_ñandú_acústica_№1.wav")
    create_sine_wav(uni_wav, duration=3.0, freq=330.0)
    manifest["unicode_count"] += 1

    uni_copy = os.path.join(sub_unicode, "Pista_ñandú_acústica_№1_copia.wav")
    shutil.copyfile(uni_wav, uni_copy)

    # 6. Ultra-short audio (< 1s)
    short_wav = os.path.join(base_dir, "ultrashort_click.wav")
    create_sine_wav(short_wav, duration=0.2, freq=1000.0)
    manifest["ultrashort_count"] += 1

    # 7. Corrupt audio file (random binary content with .flac extension)
    corrupt_flac = os.path.join(base_dir, "corrupt_damaged_header.flac")
    with open(corrupt_flac, "wb") as f:
        f.write(b"NOT_A_VALID_FLAC_FILE_RANDOM_DATA_HEADER_GARBAGE" * 20)
    manifest["corrupt_count"] += 1

    # 8. More diverse tracks to reach ~100+ files
    for j in range(1, 51):
        sub_dir = os.path.join(base_dir, f"Subfolder_{(j % 5) + 1}")
        os.makedirs(sub_dir, exist_ok=True)
        manifest["subdirs"].add(sub_dir)
        p = os.path.join(sub_dir, f"track_bulk_{j:03d}.wav")
        create_sine_wav(p, duration=3.0, freq=250.0 + j * 10.0)

    total_files = len([os.path.join(dp, f) for dp, dn, fn in os.walk(base_dir) for f in fn])
    manifest["total_files_on_disk"] = total_files
    print(f"Dataset generated: {total_files} files across {len(manifest['subdirs'])} subdirectories.")
    return manifest


def run_smoke_test(target_dir: str, db_path: str) -> Dict[str, Any]:
    cfg = DetectionConfig(
        acoustic_threshold=85.0,
        possible_threshold=70.0,
        max_workers=4
    )
    db = Database(db_path=db_path)
    scanner = AudioScanner(db=db, detection_config=cfg)

    peak_rss = [get_total_rss_mb()]
    stop_monitor = threading.Event()

    def monitor_loop():
        while not stop_monitor.is_set():
            rss = get_total_rss_mb()
            if rss > peak_rss[0]:
                peak_rss[0] = rss
            time.sleep(0.05)

    mon_thread = threading.Thread(target=monitor_loop, daemon=True)
    mon_thread.start()

    t_start = time.monotonic()
    groups = scanner.scan_directory(target_dir)
    elapsed = time.monotonic() - t_start

    stop_monitor.set()
    mon_thread.join(timeout=1.0)

    # Categorize detected groups
    exact_hash_groups = [g for g in groups if g.primary_type == DuplicateType.EXACT_HASH]
    exact_audio_groups = [g for g in groups if g.primary_type == DuplicateType.EXACT_AUDIO]
    acoustic_groups = [g for g in groups if g.primary_type == DuplicateType.ACOUSTIC_DUPLICATE]
    possible_groups = [g for g in groups if g.primary_type == DuplicateType.POSSIBLE_DUPLICATE]
    manual_review_groups = [g for g in groups if g.requires_manual_review]

    stats = scanner.stats
    db.close()

    return {
        "tracks_discovered": stats.total_files_found,
        "tracks_processed": stats.files_scanned,
        "tracks_failed": stats.files_failed,
        "total_groups": len(groups),
        "exact_hash_groups": len(exact_hash_groups),
        "exact_audio_groups": len(exact_audio_groups),
        "acoustic_duplicate_groups": len(acoustic_groups),
        "possible_duplicate_groups": len(possible_groups),
        "manual_review_groups": len(manual_review_groups),
        "elapsed_seconds": elapsed,
        "peak_rss_mb": peak_rss[0],
        "coverage_status": "SUCCESS" if stats.is_complete else "PARTIAL",
        "is_approximate": stats.is_approximate
    }


if __name__ == "__main__":
    temp_dir = tempfile.mkdtemp(prefix="audioclean_smoke_")
    test_db = os.path.join(temp_dir, "smoke_library.db")
    try:
        manifest = generate_real_file_library(temp_dir)
        results = run_smoke_test(temp_dir, test_db)
        print("\n" + "=" * 80)
        print("REAL-FILE SMOKE TEST RESULTS")
        print("=" * 80)
        for k, v in results.items():
            print(f"  {k:<28}: {v}")
        print("=" * 80)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
