"""
Cache validation helpers: fast nanosecond mtime and quick signature.
STRICT ARCHITECTURAL RULE (Phase E):
Quick signature is an auxiliary cache validation filter, NOT an authoritative
proof of cryptographic file identity for destructive operations (delete, trash).
Exact matches destined for auto-delete must re-validate the full SHA-256 hash.
"""

import os
import hashlib
from typing import Optional, Any, Tuple


def compute_quick_signature(filepath: str, block_size: int = 4096) -> str:
    """
    Computes a fast signature from head, middle, and tail blocks of a file.
    Deterministic across all file sizes, including small, zero-byte, or overlapping files.
    """
    if not filepath or not os.path.isfile(filepath):
        return ""

    try:
        size = os.path.getsize(filepath)
        if size == 0:
            return hashlib.blake2b(b"empty").hexdigest()

        hasher = hashlib.blake2b(digest_size=20)
        hasher.update(size.to_bytes(8, byteorder="big"))

        with open(filepath, "rb") as f:
            if size <= block_size * 3:
                # Small or overlapping file: read entire file once deterministically
                hasher.update(f.read())
            else:
                # 1. Head block (first 4KB)
                head = f.read(block_size)
                hasher.update(head)

                # 2. Middle block (4KB centered)
                mid_offset = (size // 2) - (block_size // 2)
                f.seek(mid_offset)
                middle = f.read(block_size)
                hasher.update(middle)

                # 3. Tail block (last 4KB)
                tail_offset = size - block_size
                f.seek(tail_offset)
                tail = f.read(block_size)
                hasher.update(tail)

        return hasher.hexdigest()
    except Exception:
        return ""


def is_cache_valid(
    filepath: str,
    cached_size: int,
    cached_mtime_ns: int,
    cached_signature: str
) -> bool:
    """
    Validates whether an AudioTrack database cache record is fresh.
    Requires st_size, st_mtime_ns, and quick_signature to match.
    """
    try:
        stat = os.stat(filepath)
        if stat.st_size != cached_size:
            return False

        current_mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
        if current_mtime_ns != cached_mtime_ns:
            return False

        if cached_signature:
            curr_sig = compute_quick_signature(filepath)
            if curr_sig != cached_signature:
                return False

        return True
    except Exception:
        return False


def verify_authoritative_sha256_before_destructive_action(filepath: str, claimed_sha256: str) -> bool:
    """
    Guarantees that a cached SHA-256 is re-verified byte-by-byte before any destructive action.
    A quick signature must NEVER be used alone to authorize permanent file deletion.
    """
    if not filepath or not os.path.isfile(filepath) or not claimed_sha256:
        return False

    try:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest() == claimed_sha256
    except Exception:
        return False


def compute_current_file_sha256(filepath: str) -> str:
    """Computes fresh byte-by-byte SHA-256 hash of a file on disk."""
    if not filepath or not os.path.isfile(filepath):
        return ""
    try:
        hasher = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return ""


def revalidate_destructive_action(
    duplicate_type: Any,
    track_to_delete: Any,
    retained_track: Optional[Any] = None
) -> tuple[bool, str]:
    """
    Authoritative destructive revalidation firewall before delete or trash.
    
    EXACT_HASH:
      - Recalculates current SHA-256 of both files on disk.
      - Confirms neither file changed since initial scan.
      - Strictly requires current_del_sha256 == current_ret_sha256.
      
    EXACT_AUDIO:
      - Does NOT require binary SHA-256 equality between track_to_delete and retained_track
        (e.g., FLAC vs WAV have different container hashes but identical PCM).
      - Verifies that neither file changed since scan (curr == analyzed_sha256).
      - Revalidates information-preserving canonical PCM match on disk.
    """
    del_path = getattr(track_to_delete, "filepath", str(track_to_delete))
    if not del_path or not os.path.isfile(del_path):
        return False, f"Archivo a eliminar no encontrado en disco: {del_path}"

    curr_del_hash = compute_current_file_sha256(del_path)
    if not curr_del_hash:
        return False, f"No fue posible calcular hash SHA-256 actual de {del_path}"

    del_analyzed_hash = getattr(track_to_delete, "sha256", None)
    if del_analyzed_hash and curr_del_hash != del_analyzed_hash:
        return False, f"El archivo a eliminar fue modificado en disco tras el escaneo (SHA-256 cambió)"

    if retained_track is None:
        return True, "Revalidación de archivo individual aprobada"

    ret_path = getattr(retained_track, "filepath", str(retained_track))
    if not ret_path or not os.path.isfile(ret_path):
        return False, f"Archivo conservado no encontrado en disco: {ret_path}"

    curr_ret_hash = compute_current_file_sha256(ret_path)
    if not curr_ret_hash:
        return False, f"No fue posible calcular hash SHA-256 actual de {ret_path}"

    ret_analyzed_hash = getattr(retained_track, "sha256", None)
    if ret_analyzed_hash and curr_ret_hash != ret_analyzed_hash:
        return False, f"El archivo conservado fue modificado en disco tras el escaneo (SHA-256 cambió)"

    type_str = getattr(duplicate_type, "value", str(duplicate_type))

    if type_str == "EXACT_HASH":
        if curr_del_hash != curr_ret_hash:
            return False, f"Fallo EXACT_HASH: Los hashes SHA-256 actuales no coinciden ({curr_del_hash[:8]} != {curr_ret_hash[:8]})"
        return True, "Revalidación EXACT_HASH aprobada: hashes binarios actuales idénticos"

    elif type_str == "EXACT_AUDIO":
        # NO exigir que coincidan los hashes binarios SHA-256 entre sí (ej. FLAC vs WAV)
        # Revalidar preservación estricta de PCM
        try:
            from core.fingerprint import verify_full_normalized_pcm_match
            pcm_match = verify_full_normalized_pcm_match(del_path, ret_path)
            if not pcm_match:
                return False, "Fallo EXACT_AUDIO: La verificación PCM canónica en caliente falló"
            return True, "Revalidación EXACT_AUDIO aprobada: PCM canónico idéntico verificado (hashes binarios independientes)"
        except Exception as e:
            return False, f"Error durante la revalidación PCM de EXACT_AUDIO: {e}"

    return True, f"Revalidación de integridad aprobada para tipo {type_str}"

