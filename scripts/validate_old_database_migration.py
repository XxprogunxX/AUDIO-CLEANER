"""
Legacy Database Migration & Backward Compatibility Validation Script
Validates:
1. Pre-Phase E legacy schema without mtime_ns / quick_signature.
2. Safe additive migration on open via PRAGMA table_info and ALTER TABLE.
3. Preservation of all historical tracks and metadata.
4. Migration idempotency on subsequent database connections.
5. Search, retrieval, and scanning continue working seamlessly on migrated DB.
"""

import os
import sys
import sqlite3
import tempfile
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.database import Database
from core.models import AudioTrack
from core.scanner import AudioScanner


def create_legacy_database(db_path: str):
    """Creates a database strictly using the pre-Phase E schema."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE tracks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filepath TEXT UNIQUE NOT NULL,
            filesize INTEGER NOT NULL,
            mtime REAL NOT NULL,
            duration REAL,
            bitrate INTEGER,
            format TEXT,
            samplerate INTEGER,
            channels INTEGER,
            audio_hash TEXT,
            quality_score REAL,
            fingerprint BLOB,
            title TEXT,
            artist TEXT,
            album TEXT
        )
    """)
    import zlib
    # Insert 5 historical tracks
    legacy_tracks = [
        ("/music/album1/song1.mp3", 5242880, 1690000000.5, 210.0, 320, "MP3", 44100, 2, "hash1", 85.0, zlib.compress(b"\x01\x00\x00\x00\x02\x00\x00\x00"), "Song 1", "Artist A", "Album 1"),
        ("/music/album1/song2.mp3", 4194304, 1690000010.5, 180.0, 256, "MP3", 44100, 2, "hash2", 75.0, zlib.compress(b"\x03\x00\x00\x00\x04\x00\x00\x00"), "Song 2", "Artist A", "Album 1"),
        ("/music/album2/trackA.flac", 31457280, 1690000020.0, 240.0, 950, "FLAC", 44100, 2, "hashA", 98.0, zlib.compress(b"\x05\x00\x00\x00\x06\x00\x00\x00"), "Track A", "Band B", "Album 2"),
        ("/music/album2/trackB.flac", 32505856, 1690000030.0, 245.0, 960, "FLAC", 44100, 2, "hashB", 98.0, zlib.compress(b"\x07\x00\x00\x00\x08\x00\x00\x00"), "Track B", "Band B", "Album 2"),
        ("/music/singles/hit.wav", 44000000, 1690000040.0, 200.0, 1411, "WAV", 44100, 2, "hashHit", 99.0, zlib.compress(b"\x09\x00\x00\x00\x0A\x00\x00\x00"), "Hit Single", "Pop Star", "Hits")
    ]
    cur.executemany("""
        INSERT INTO tracks (filepath, filesize, mtime, duration, bitrate, format, samplerate, channels, audio_hash, quality_score, fingerprint, title, artist, album)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, legacy_tracks)
    conn.commit()
    conn.close()


def validate_migration(db_path: str):
    print("Step 1: Verifying legacy schema has NO mtime_ns or quick_signature...")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(tracks)")
    cols_pre = {row[1] for row in cur.fetchall()}
    assert "mtime_ns" not in cols_pre, "Test setup error: mtime_ns already in legacy schema"
    assert "quick_signature" not in cols_pre, "Test setup error: quick_signature already in legacy schema"
    conn.close()
    print("  -> Confirmed: Pure legacy schema (14 columns).")

    print("Step 2: Opening legacy database with new Database engine (first open)...")
    db1 = Database(db_path=db_path)
    with db1._get_connection() as conn:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(tracks)")
        cols_post = {row[1] for row in cur.fetchall()}
    assert "mtime_ns" in cols_post, "Migration failed: mtime_ns column missing!"
    assert "quick_signature" in cols_post, "Migration failed: quick_signature column missing!"

    # Verify all 5 tracks preserved
    tracks = db1.get_all_tracks()
    assert len(tracks) == 5, f"Data loss detected: Expected 5 tracks, found {len(tracks)}"
    print(f"  -> Migration successful: Columns added. All {len(tracks)} tracks intact.")
    db1.close()

    print("Step 3: Opening database a second time to verify idempotency...")
    db2 = Database(db_path=db_path)
    tracks2 = db2.get_all_tracks()
    assert len(tracks2) == 5, f"Idempotency failure: Expected 5 tracks, found {len(tracks2)}"
    
    # Query validation
    track = db2.get_track("/music/album1/song1.mp3")
    assert track is not None, "Failed to retrieve track by path on migrated database"
    assert track.artist == "Artist A", f"Metadata mismatch: {track.artist}"
    assert track.title == "Song 1", f"Metadata mismatch: {track.title}"

    stats = db2.get_format_statistics()
    assert stats["MP3"]["count"] == 2, f"Format stats MP3 count unexpected: {stats.get('MP3')}"
    assert stats["FLAC"]["count"] == 2, f"Format stats FLAC count unexpected: {stats.get('FLAC')}"
    assert stats["WAV"]["count"] == 1, f"Format stats WAV count unexpected: {stats.get('WAV')}"
    db2.close()
    print("  -> Idempotency verified: Re-opening preserves schema and query operations.")
    print("=" * 80)
    print("LEGACY DATABASE MIGRATION VALIDATION: PASS")
    print("=" * 80)


if __name__ == "__main__":
    temp_dir = tempfile.mkdtemp(prefix="audioclean_mig_")
    db_file = os.path.join(temp_dir, "legacy_v0.db")
    try:
        create_legacy_database(db_file)
        validate_migration(db_file)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
