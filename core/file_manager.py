"""
Safe File Management, Review and Organization Operations.
Centralized FileOperationService enforcing strict safety invariants across all deletion modes.
"""

import os
import sys
import shutil
import sqlite3
import uuid
import subprocess
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, replace
from typing import List, Tuple, Optional, Callable, Dict, Any
from core.models import DuplicateGroup, AudioTrack, FileAction, DuplicateType, prune_duplicate_groups
from core.database import Database
from core.cache_signature import compute_current_file_sha256


class JournalError(Exception):
    """Raised when journal persistence operations fail."""
    pass


class OperationStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    PARTIAL_FAILURE = "PARTIAL_FAILURE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


def is_volume_accessible(filepath: str) -> bool:
    """
    Checks if the filesystem volume, drive or root containing filepath is mounted and accessible.
    Prevents treating disconnected NAS, external USB drives or network shares as 'deleted files'.
    """
    if not filepath:
        return False
    try:
        abs_path = os.path.abspath(filepath)
        drive, _ = os.path.splitdrive(abs_path)
        if drive:
            drive_root = drive + os.path.sep
            return os.path.exists(drive_root)
        else:
            parent = os.path.dirname(abs_path)
            if os.path.exists(parent):
                return True
            return os.path.exists(os.path.sep)
    except Exception:
        return False


def _fsync_parent_directory(path: str) -> None:
    """Best-effort durability barrier for directory metadata on supported systems."""
    if os.name == "nt":
        return
    descriptor = None
    try:
        descriptor = os.open(os.path.dirname(os.path.abspath(path)), os.O_RDONLY)
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _copy_backup_verified(source: str, target: str, temporary: str, expected_sha256: str) -> None:
    """Copy to a private temporary file, fsync it, verify it, then publish it."""
    temporary_created = False
    if os.path.exists(temporary):
        raise FileExistsError(f"La ruta temporal privada ya existe: {temporary}")
    try:
        with open(source, "rb") as input_file, open(temporary, "xb") as output_file:
            temporary_created = True
            shutil.copyfileobj(input_file, output_file, length=1024 * 1024)
            output_file.flush()
            os.fsync(output_file.fileno())
        if compute_current_file_sha256(temporary) != expected_sha256:
            raise IOError("La copia temporal no coincide con el SHA-256 del archivo original")
        try:
            shutil.copystat(source, temporary)
        except OSError:
            pass
        if os.name == "nt":
            # Windows rename fails if another process created the destination.
            os.rename(temporary, target)
        else:
            # A hard link publishes the verified inode atomically without replacing
            # a path that appeared after collision resolution.
            os.link(temporary, target)
            os.remove(temporary)
        _fsync_parent_directory(target)
    except Exception:
        # The final target is deliberately never removed here: if publication
        # collided, it belongs to another writer; if publication succeeded, it
        # is already a verified recovery copy. Only this invocation's private
        # temporary file can be cleaned safely.
        if temporary_created and os.path.isfile(temporary):
            try:
                os.remove(temporary)
            except OSError:
                pass
        raise


def _source_claim_path(filepath: str, op_id: str) -> str:
    """Private same-directory name used to atomically claim the scanned source."""
    directory, filename = os.path.split(filepath)
    return os.path.join(directory, f".{filename}.audioclean-{op_id}.claimed")


def _restore_claim_if_unoccupied(claim_path: str, original_path: str) -> bool:
    """Restore a claimed source without overwriting a concurrently-created file."""
    if not os.path.isfile(claim_path):
        return False
    if os.path.exists(original_path):
        return False
    os.rename(claim_path, original_path)
    return True


@contextmanager
def _source_lease(filepath: str):
    """Deny concurrent writes on Windows while allowing this process to rename/delete."""
    if os.name != "nt":
        yield
        return
    import ctypes
    from ctypes import wintypes

    create_file = ctypes.windll.kernel32.CreateFileW
    create_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create_file.restype = wintypes.HANDLE
    close_handle = ctypes.windll.kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    generic_read = 0x80000000
    share_read = 0x00000001
    share_delete = 0x00000004
    open_existing = 3
    normal = 0x00000080
    invalid = wintypes.HANDLE(-1).value
    handle = create_file(filepath, generic_read, share_read | share_delete, None,
                         open_existing, normal, None)
    if handle == invalid:
        raise OSError(ctypes.get_last_error(), f"No se pudo bloquear el origen contra escrituras: {filepath}")
    try:
        yield
    finally:
        close_handle(handle)


@dataclass
class OperationResult:
    """
    Structured outcome of a file management operation.
    Supports tuple unpacking (success, failed, logs) for 100% backwards compatibility.
    """
    success: int
    failed: int
    logs: List[str]
    blocked: int = 0
    status: OperationStatus = OperationStatus.SUCCESS
    partial_failures: int = 0
    reason: str = ""

    def __iter__(self):
        return iter((self.success, self.failed, self.logs))

    def __getitem__(self, index):
        return (self.success, self.failed, self.logs)[index]


class OperationJournal:
    """
    Durable, independent SQLite journal for filesystem operations.
    Stored separately from the main library database (operation_journal.db)
    to guarantee crash recovery and reconciliation even if library.db is locked or corrupted.
    States: PENDING -> FS_DONE -> COMPLETED (or FAILED / ABORTED).
    """
    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self.db_path = db_path
        else:
            base_dir = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "AudioDuplicateDetector")
            try:
                os.makedirs(base_dir, exist_ok=True)
            except Exception:
                pass
            self.db_path = os.path.join(base_dir, "operation_journal.db")
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=FULL;")
        conn.execute("PRAGMA busy_timeout=10000;")
        return conn

    def _init_db(self):
        conn = None
        try:
            conn = self._get_connection()
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS operation_journal (
                        op_id TEXT PRIMARY KEY,
                        filepath TEXT NOT NULL,
                        action TEXT NOT NULL,
                        target_path TEXT,
                        target_tmp_path TEXT DEFAULT '',
                        source_claim_path TEXT DEFAULT '',
                        expected_sha256 TEXT DEFAULT '',
                        state TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );
                """)
                existing = {row[1] for row in conn.execute("PRAGMA table_info(operation_journal)")}
                if "target_tmp_path" not in existing:
                    conn.execute("ALTER TABLE operation_journal ADD COLUMN target_tmp_path TEXT DEFAULT ''")
                if "source_claim_path" not in existing:
                    conn.execute("ALTER TABLE operation_journal ADD COLUMN source_claim_path TEXT DEFAULT ''")
                if "expected_sha256" not in existing:
                    conn.execute("ALTER TABLE operation_journal ADD COLUMN expected_sha256 TEXT DEFAULT ''")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_op_journal_state ON operation_journal(state);")
                conn.commit()
        except Exception as e:
            raise JournalError(f"Fallo crítico al inicializar la base de datos del journal ({self.db_path}): {e}") from e
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def record_pending(
        self,
        op_id: str,
        filepath: str,
        action: str,
        target_path: Optional[str] = None,
        target_tmp_path: Optional[str] = None,
        expected_sha256: str = "",
        source_claim_path: Optional[str] = None
    ):
        conn = None
        try:
            now = datetime.now().isoformat()
            conn = self._get_connection()
            with conn:
                conn.execute(
                    "INSERT INTO operation_journal "
                    "(op_id, filepath, action, target_path, target_tmp_path, source_claim_path, expected_sha256, state, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (op_id, filepath, action, target_path or "", target_tmp_path or "",
                     source_claim_path or "", expected_sha256 or "", "PENDING", now, now)
                )
                conn.commit()
        except Exception as e:
            raise JournalError(f"Fallo al escribir estado PENDING en el journal para {filepath}: {e}") from e
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def update_state(self, op_id: str, state: str):
        conn = None
        try:
            now = datetime.now().isoformat()
            conn = self._get_connection()
            with conn:
                conn.execute(
                    "UPDATE operation_journal SET state = ?, updated_at = ? WHERE op_id = ?",
                    (state, now, op_id)
                )
                conn.commit()
        except Exception as e:
            raise JournalError(f"Fallo al actualizar estado a {state} en el journal (op_id={op_id}): {e}") from e
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def get_incomplete_operations(self) -> List[Dict[str, Any]]:
        conn = None
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM operation_journal "
                "WHERE state IN ('PENDING', 'SOURCE_CLAIMED', 'TARGET_VERIFIED', 'FS_DONE') ORDER BY created_at ASC"
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            raise JournalError(f"Fallo al consultar operaciones incompletas del journal: {e}") from e
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    def reconcile(self, db: Optional[Database] = None) -> List[str]:
        logs: List[str] = []
        for op in self.get_incomplete_operations():
            op_id = op["op_id"]
            filepath = op["filepath"]
            action = op.get("action", "")
            target_path = op.get("target_path", "")
            target_tmp_path = op.get("target_tmp_path", "")
            claim_path = op.get("source_claim_path", "")
            expected_sha256 = op.get("expected_sha256", "")
            state = op.get("state", "")

            if not is_volume_accessible(filepath):
                logs.append(
                    f"⚠️ Reconciliación omitida: El volumen o unidad para '{filepath}' no está accesible o está desconectado. "
                    f"Operación {op_id} conservada como {state} para prevenir purga errónea de la biblioteca."
                )
                continue
            if action == "backup" and target_path and not is_volume_accessible(target_path):
                logs.append(
                    f"⚠️ Reconciliación omitida: El volumen destino de backup para '{target_path}' no está accesible. "
                    f"Operación {op_id} conservada como {state}."
                )
                continue

            source_exists = os.path.isfile(filepath)
            claim_exists = bool(claim_path and os.path.isfile(claim_path))
            target_exists = bool(target_path and os.path.isfile(target_path))
            target_hash = compute_current_file_sha256(target_path) if target_exists else ""
            target_verified = bool(expected_sha256 and target_hash == expected_sha256)

            if claim_exists and compute_current_file_sha256(claim_path) != expected_sha256:
                self.update_state(op_id, "FAILED")
                logs.append(
                    f"⚠️ Reclamación de origen no verificable para {os.path.basename(filepath)}; "
                    "se conservan todos los archivos para revisión manual."
                )
                continue

            if source_exists and claim_exists:
                # Another writer recreated the original name. Never overwrite or
                # remove it. A verified backup makes the claimed old version
                # redundant; otherwise both versions remain for manual recovery.
                if action == "backup" and target_verified:
                    os.remove(claim_path)
                self.update_state(op_id, "FAILED")
                logs.append(
                    f"⚠️ El origen {os.path.basename(filepath)} fue recreado durante la operación; "
                    "se preservó la versión nueva y el estado requiere revisión."
                )
                continue

            if claim_exists and not source_exists:
                if action == "backup" and target_verified:
                    os.remove(claim_path)
                    source_exists = False
                else:
                    try:
                        _restore_claim_if_unoccupied(claim_path, filepath)
                        self.update_state(op_id, "ABORTED")
                        logs.append(
                            f"Reconciliación: se restauró el origen de {os.path.basename(filepath)} "
                            "tras una operación interrumpida."
                        )
                    except OSError as restore_error:
                        self.update_state(op_id, "FAILED")
                        logs.append(f"⚠️ No se pudo restaurar {os.path.basename(filepath)}: {restore_error}")
                    continue

            if source_exists:
                # A legacy PENDING row or a crash before source claim. Final target
                # paths are never deleted because ownership cannot be proven.
                self.update_state(op_id, "ABORTED")
                logs.append(
                    f"Reconciliación: operación para {os.path.basename(filepath)} descartada; "
                    "el archivo original permanece intacto."
                )
                continue

            if action == "backup":
                if not expected_sha256 or not target_verified:
                    self.update_state(op_id, "FAILED")
                    logs.append(
                        f"⚠️ Backup dañado, ausente o no verificable para {os.path.basename(filepath)}; "
                        "la base de datos se conserva para revisión manual."
                    )
                    continue
                # A complete private temporary copy is redundant. An incomplete
                # or foreign file is preserved because its ownership is ambiguous.
                if target_tmp_path and os.path.isfile(target_tmp_path):
                    if compute_current_file_sha256(target_tmp_path) == expected_sha256:
                        os.remove(target_tmp_path)
                success_message = (
                    f"Reconciliación exitosa: backup verificado por SHA-256 de "
                    f"{os.path.basename(filepath)} completado y registrado."
                )
            else:
                success_message = (
                    f"Reconciliación exitosa: archivo {os.path.basename(filepath)} confirmado ausente "
                    f"en disco (estado previo: {state}). Registro purgado."
                )

            if db is not None:
                try:
                    db.delete_track(filepath)
                except Exception as db_error:
                    logs.append(f"Reconciliación pendiente: error al sincronizar SQLite para {os.path.basename(filepath)}: {db_error}")
                    continue
            self.update_state(op_id, "COMPLETED")
            logs.append(success_message)
        return logs


def open_file_in_explorer(filepath: str):
    """Opens Windows Explorer with the target file highlighted."""
    if not os.path.exists(filepath):
        return
    if sys.platform == "win32":
        path = os.path.normpath(filepath)
        subprocess.run(f'explorer /select,"{path}"')
    else:
        # Cross-platform fallback
        subprocess.run(["xdg-open", os.path.dirname(filepath)])


def set_track_action_in_group(group: DuplicateGroup, filepath: str, action: FileAction):
    """
    Updates the action (KEEP / DELETE / UNSET) for a track in a group
    and refreshes the space savings.
    """
    for t in group.tracks:
        if t.filepath == filepath:
            t.action = action
            break
    group.recalculate_space_saving()


def auto_apply_recommendations(groups: List[DuplicateGroup]) -> int:
    """
    Sets recommended best track to KEEP and all others to DELETE across all groups.
    Ignores groups requiring manual review.
    
    Returns:
        int: Number of groups successfully modified.
    """
    modified = 0
    for group in groups:
        if getattr(group, "requires_manual_review", False):
            continue
        if not group.best_track_path:
            continue

        changed = False
        for t in group.tracks:
            target_action = FileAction.KEEP if t.filepath == group.best_track_path else FileAction.DELETE
            if t.action != target_action:
                t.action = target_action
                changed = True

        if changed:
            group.recalculate_space_saving()
            modified += 1

    return modified


class FileOperationService:
    """
    Single source of truth for all duplicate file modifications (Backup, Trash, Permanent Deletion).

    Mandatory Safety Invariants:
    1. Prohibido eliminar/mover la única copia restante del grupo: Al menos una pista debe quedar conservada.
    2. Inmunidad para pistas [CONSERVAR]: Jamás se permite el borrado de archivos con acción KEEP.
    3. Protección de revisión manual Fail-Closed: Grupos con requires_manual_review jamás se procesan
       a menos que allow_manual_review_bypass sea True explícitamente.
    4. Sincronización durable y Journaling: Operaciones en disco se registran en operation_journal.db independiente.
    5. No reportar éxito falso: Si la operación en disco triunfa pero la base de datos falla, se reporta como PARTIAL_FAILURE.
    """

    @classmethod
    def reconcile_pending_operations(
        cls,
        db: Optional[Database] = None,
        journal_path: Optional[str] = None
    ) -> List[str]:
        """
        Reconciles operations that completed on filesystem but failed to sync to SQLite.
        Should be called on application startup.
        """
        journal = OperationJournal(db_path=journal_path)
        return journal.reconcile(db=db)

    @classmethod
    def execute_operation(
        cls,
        groups: List[DuplicateGroup],
        mode: str,  # "backup", "trash", "permanent"
        destination_folder: Optional[str] = None,
        db: Optional[Database] = None,
        allow_manual_review_bypass: bool = False,
        pre_operation_hook: Optional[Callable[[str], None]] = None,
        journal_path: Optional[str] = None
    ) -> OperationResult:
        success = 0
        failed = 0
        blocked = 0
        partial_failures = 0
        logs: List[str] = []

        try:
            journal = OperationJournal(db_path=journal_path)
        except Exception as init_err:
            logs.append(f"Error crítico de seguridad: no se pudo inicializar Operation Journal: {init_err}")
            total_delete_requests = sum(
                len([t for t in g.tracks if t.action == FileAction.DELETE])
                for g in groups
            )
            return OperationResult(
                success=0,
                failed=total_delete_requests,
                blocked=total_delete_requests,
                logs=logs,
                status=OperationStatus.BLOCKED,
                reason=f"JOURNAL_INIT_FAILED: {init_err}"
            )

        mode = mode.lower()
        if mode not in {"backup", "trash", "permanent"}:
            return OperationResult(
                success=0, failed=0, logs=[f"Modo de operación desconocido: {mode}"],
                status=OperationStatus.FAILED, reason="UNKNOWN_MODE"
            )
        if mode == "backup":
            if not destination_folder:
                logs.append("Error: No se especificó carpeta destino para el backup.")
                return OperationResult(
                    success=0, failed=0, logs=logs, status=OperationStatus.FAILED, reason="DESTINATION_MISSING"
                )
            os.makedirs(destination_folder, exist_ok=True)

        for group in groups:
            # Regla 3: Aislamiento Fail-Closed por revisión manual
            if getattr(group, "requires_manual_review", False) and not allow_manual_review_bypass:
                blocked += 1
                logs.append(
                    f"⚠️ Grupo {group.group_id}: OPERACIÓN BLOQUEADA por política de seguridad "
                    f"(requires_manual_review=True). No se modificó ningún archivo. "
                    f"Requiere autorización explícita del usuario."
                )
                continue

            # Regla 1: Protección de copia única (debe quedar al menos una pista no marcada para DELETE)
            retained_tracks = [t for t in group.tracks if t.action != FileAction.DELETE]
            if not retained_tracks and len(group.tracks) > 0:
                logs.append(
                    f"⚠️ Grupo {group.group_id}: Operación bloqueada porque ninguna copia está marcada para conservar "
                    f"(se perderían todas las copias)."
                )
                failed += len([t for t in group.tracks if t.action == FileAction.DELETE])
                continue

            # Procesar pistas marcadas DELETE
            for track in list(group.tracks):
                if track.action == FileAction.DELETE:
                    if not os.path.exists(track.filepath):
                        logs.append(f"Archivo no encontrado en disco: {track.filepath}")
                        failed += 1
                        continue

                    if group.primary_type == DuplicateType.ACOUSTIC_DUPLICATE and not group.requires_manual_review:
                        proven = {frozenset(p) for p in group.verified_pairs}
                        verified_retained = [t for t in retained_tracks
                            if frozenset((track.filepath, t.filepath)) in proven and os.path.isfile(t.filepath)]
                        if not verified_retained:
                            blocked += 1
                            logs.append(f"Sin evidencia directa con la copia conservada: {track.filename}. Reescanee o revise el grupo.")
                            continue

                        primary_retained = verified_retained[0]
                    else:
                        primary_retained = next((t for t in retained_tracks if os.path.isfile(t.filepath)), None)
                    if primary_retained is None:
                        blocked += 1
                        logs.append(f"No hay una copia conservada accesible para {track.filename}.")
                        continue

                    # Hook desacoplado (ej. para detener reproducción antes de borrar en Windows)
                    if pre_operation_hook is not None:
                        try:
                            pre_operation_hook(track.filepath)
                        except Exception as hook_err:
                            logs.append(f"Aviso hook previo a operación ({track.filename}): {hook_err}")

                    resolved_target_path: Optional[str] = None
                    temporary_target_path: Optional[str] = None
                    if mode == "backup":
                        target_filename = track.filename
                        candidate_path = os.path.join(destination_folder, target_filename)
                        counter = 1
                        base_name, ext = os.path.splitext(target_filename)
                        while os.path.exists(candidate_path):
                            candidate_path = os.path.join(destination_folder, f"{base_name}_{counter}{ext}")
                            counter += 1
                        resolved_target_path = candidate_path
                    op_id = str(uuid.uuid4())
                    source_claim_path = _source_claim_path(track.filepath, op_id)
                    if resolved_target_path:
                        temporary_target_path = f"{resolved_target_path}.audioclean-{op_id}.partial"

                    expected_sha256 = compute_current_file_sha256(track.filepath)
                    if not expected_sha256:
                        logs.append(f"No fue posible fijar el SHA-256 esperado para {track.filename}.")
                        failed += 1
                        blocked += 1
                        continue

                    # Fail-closed journal: debe registrar PENDING de forma duradera antes de tocar filesystem
                    try:
                        journal.record_pending(
                            op_id,
                            track.filepath,
                            mode,
                            target_path=resolved_target_path,
                            target_tmp_path=temporary_target_path,
                            expected_sha256=expected_sha256,
                            source_claim_path=source_claim_path
                        )
                    except Exception as j_err:
                        logs.append(
                            f"Error crítico de seguridad: Fallo al persistir PENDING en journal para {track.filename}: {j_err}. "
                            f"Operación abortada para este archivo (filesystem intacto)."
                        )
                        failed += 1
                        blocked += 1
                        continue

                    action_ok = False
                    log_msg = ""
                    try:
                        # Hold a Windows sharing lease that denies writers, then
                        # atomically move the scanned path to a private claim. Any
                        # file concurrently recreated at the original name is never
                        # touched by this operation.
                        with _source_lease(track.filepath):
                            if os.path.exists(source_claim_path):
                                raise FileExistsError(f"La reclamación privada ya existe: {source_claim_path}")
                            os.rename(track.filepath, source_claim_path)
                            try:
                                journal.update_state(op_id, "SOURCE_CLAIMED")
                            except Exception:
                                _restore_claim_if_unoccupied(source_claim_path, track.filepath)
                                raise

                            claimed_track = replace(track, filepath=source_claim_path)
                            from core.cache_signature import revalidate_destructive_action
                            is_reval_ok, reval_msg = revalidate_destructive_action(
                                group.primary_type, claimed_track, primary_retained
                            )
                            if not is_reval_ok:
                                if not _restore_claim_if_unoccupied(source_claim_path, track.filepath):
                                    raise RuntimeError(
                                        f"{reval_msg}; el nombre original fue ocupado y la copia reclamada se conservó"
                                    )
                                journal.update_state(op_id, "ABORTED")
                                logs.append(f"Seguridad destructiva: Operación bloqueada para {track.filename}: {reval_msg}")
                                failed += 1
                                blocked += 1
                                continue

                            if mode == "backup":
                                _copy_backup_verified(
                                    source_claim_path, resolved_target_path,
                                    temporary_target_path, expected_sha256
                                )
                                journal.update_state(op_id, "TARGET_VERIFIED")
                                if os.path.exists(track.filepath):
                                    raise RuntimeError("El nombre original fue recreado durante el backup")
                                if compute_current_file_sha256(source_claim_path) != expected_sha256:
                                    raise RuntimeError("El origen cambió durante el backup; se preservó para recuperación")
                                os.remove(source_claim_path)
                                log_msg = f"Movido a backup: {track.filename} -> {os.path.basename(resolved_target_path)}"
                                action_ok = True

                            elif mode == "trash":
                                try:
                                    import send2trash
                                except ImportError as import_error:
                                    raise RuntimeError("El módulo 'send2trash' no está disponible") from import_error
                                if os.path.exists(track.filepath):
                                    raise RuntimeError("El nombre original fue recreado antes de enviar a la Papelera")
                                send2trash.send2trash(source_claim_path)
                                log_msg = f"Movido a Papelera: {track.filename}"
                                action_ok = True

                            elif mode == "permanent":
                                if os.path.exists(track.filepath):
                                    raise RuntimeError("El nombre original fue recreado antes de la eliminación")
                                if compute_current_file_sha256(source_claim_path) != expected_sha256:
                                    raise RuntimeError("El origen cambió durante la operación; no se eliminó")
                                os.remove(source_claim_path)
                                log_msg = f"Eliminado permanentemente: {track.filename}"
                                action_ok = True

                    except Exception as e:
                        restored = False
                        try:
                            restored = _restore_claim_if_unoccupied(source_claim_path, track.filepath)
                        except OSError:
                            restored = False
                        logs.append(f"Error procesando {track.filename}: {e}")
                        if os.path.isfile(source_claim_path) and not restored:
                            logs.append(f"Recuperación conservada en: {source_claim_path}")
                        failed += 1
                        action_ok = False
                        try:
                            journal.update_state(op_id, "FAILED")
                        except Exception:
                            pass

                    # Sincronización solo tras éxito en sistema de archivos
                    if action_ok:
                        fs_done_ok = True
                        try:
                            journal.update_state(op_id, "FS_DONE")
                        except Exception as j_err:
                            fs_done_ok = False
                            partial_failures += 1
                            logs.append(
                                f"⚠️ Error de journal tras modificar filesystem para {track.filename}: {j_err}. "
                                f"Estado PENDING conservado para reconciliación posterior en el arranque."
                            )

                        db_ok = True
                        if db is not None:
                            try:
                                db.delete_track(track.filepath)
                            except Exception as db_err:
                                db_ok = False
                                partial_failures += 1
                                logs.append(
                                    f"⚠️ Aviso SQLite: archivo eliminado en disco pero no se pudo purgar de SQLite ({db_err}). "
                                    f"Estado persistido en Operation Journal para reconciliación automática."
                                )

                        if fs_done_ok and db_ok:
                            try:
                                journal.update_state(op_id, "COMPLETED")
                            except Exception as comp_err:
                                partial_failures += 1
                                logs.append(
                                    f"⚠️ Error al marcar COMPLETED en journal para {track.filename}: {comp_err}. "
                                    f"La próxima reconciliación cerrará el registro idempotentemente."
                                )

                        # Actualizar modelo en memoria
                        try:
                            group.tracks.remove(track)
                        except ValueError:
                            pass

                        # Si la pista eliminada era la principal, actualizar best_track_path
                        if group.best_track_path == track.filepath:
                            group.best_track_path = group.tracks[0].filepath if group.tracks else ""

                        if db_ok and fs_done_ok:
                            logs.append(log_msg)
                            success += 1

            group.recalculate_space_saving()

        # Prune zombie duplicate groups (groups with <= 1 tracks remaining)
        pruned_groups = prune_duplicate_groups(groups)
        groups.clear()
        groups.extend(pruned_groups)

        # Determinar estado global con precedencia estricta
        if partial_failures > 0:
            status = OperationStatus.PARTIAL_FAILURE
            reason = "PARTIAL_FAILURE"
        elif success > 0 and failed > 0:
            status = OperationStatus.PARTIAL_FAILURE
            reason = "MIXED_SUCCESS_AND_FAILURE"
        elif success > 0 and blocked > 0:
            status = OperationStatus.PARTIAL_SUCCESS
            reason = "PARTIAL_SUCCESS"
        elif failed > 0:
            status = OperationStatus.FAILED
            reason = "FS_OPERATION_FAILED"
        elif blocked > 0:
            status = OperationStatus.BLOCKED
            reason = "MANUAL_REVIEW_REQUIRED"
        else:
            status = OperationStatus.SUCCESS
            reason = "OK"

        return OperationResult(
            success=success,
            failed=failed,
            logs=logs,
            blocked=blocked,
            status=status,
            partial_failures=partial_failures,
            reason=reason
        )

    @classmethod
    def backup(
        cls,
        groups: List[DuplicateGroup],
        destination_folder: str,
        db: Optional[Database] = None,
        allow_manual_review_bypass: bool = False,
        pre_operation_hook: Optional[Callable[[str], None]] = None,
        journal_path: Optional[str] = None
    ) -> OperationResult:
        return cls.execute_operation(
            groups, "backup", destination_folder=destination_folder, db=db,
            allow_manual_review_bypass=allow_manual_review_bypass,
            pre_operation_hook=pre_operation_hook,
            journal_path=journal_path
        )

    @classmethod
    def trash(
        cls,
        groups: List[DuplicateGroup],
        db: Optional[Database] = None,
        allow_manual_review_bypass: bool = False,
        pre_operation_hook: Optional[Callable[[str], None]] = None,
        journal_path: Optional[str] = None
    ) -> OperationResult:
        return cls.execute_operation(
            groups, "trash", db=db,
            allow_manual_review_bypass=allow_manual_review_bypass,
            pre_operation_hook=pre_operation_hook,
            journal_path=journal_path
        )

    @classmethod
    def delete_permanently(
        cls,
        groups: List[DuplicateGroup],
        db: Optional[Database] = None,
        allow_manual_review_bypass: bool = False,
        pre_operation_hook: Optional[Callable[[str], None]] = None,
        journal_path: Optional[str] = None
    ) -> OperationResult:
        return cls.execute_operation(
            groups, "permanent", db=db,
            allow_manual_review_bypass=allow_manual_review_bypass,
            pre_operation_hook=pre_operation_hook,
            journal_path=journal_path
        )


def move_marked_duplicates(
    groups: List[DuplicateGroup],
    destination_folder: str,
    db: Optional[Database] = None,
    allow_manual_review_bypass: bool = False,
    pre_operation_hook: Optional[Callable[[str], None]] = None,
    journal_path: Optional[str] = None
) -> OperationResult:
    """
    Moves all tracks marked DELETE to destination_folder.
    Preserves safety: Will NOT move tracks marked KEEP or delete the only remaining track.
    """
    return FileOperationService.backup(
        groups, destination_folder=destination_folder, db=db,
        allow_manual_review_bypass=allow_manual_review_bypass,
        pre_operation_hook=pre_operation_hook,
        journal_path=journal_path
    )


def trash_marked_duplicates(
    groups: List[DuplicateGroup],
    db: Optional[Database] = None,
    allow_manual_review_bypass: bool = False,
    pre_operation_hook: Optional[Callable[[str], None]] = None,
    journal_path: Optional[str] = None
) -> OperationResult:
    """
    Safely sends all tracks marked DELETE to the system Trash / Recycle Bin via Send2Trash.
    Shares the exact same safety invariants as backup and permanent delete.
    """
    return FileOperationService.trash(
        groups, db=db,
        allow_manual_review_bypass=allow_manual_review_bypass,
        pre_operation_hook=pre_operation_hook,
        journal_path=journal_path
    )


def delete_marked_duplicates_permanently(
    groups: List[DuplicateGroup],
    db: Optional[Database] = None,
    allow_manual_review_bypass: bool = False,
    pre_operation_hook: Optional[Callable[[str], None]] = None,
    journal_path: Optional[str] = None
) -> OperationResult:
    """
    Safely deletes all tracks marked DELETE permanently after user confirmation.
    Safety Guard: Never deletes a track marked KEEP or every track in a group.
    """
    return FileOperationService.delete_permanently(
        groups, db=db,
        allow_manual_review_bypass=allow_manual_review_bypass,
        pre_operation_hook=pre_operation_hook,
        journal_path=journal_path
    )
