"""
Audio Duplicate & Acoustic Fingerprinting Detector.
Main entrypoint supporting both Modern Desktop GUI and Headless CLI modes.
"""

import os
import sys
import argparse
import multiprocessing
from typing import Optional


def main():
    # Crucial for Windows PyInstaller executables using multiprocessing / ProcessPoolExecutor
    multiprocessing.freeze_support()

    parser = argparse.ArgumentParser(
        description="Analizador de bibliotecas de música y detector de duplicados acústicos."
    )
    parser.add_argument(
        "--folder", "-f",
        type=str,
        help="Ruta de la carpeta de música a analizar."
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Ejecutar en modo consola / headless sin abrir la interfaz gráfica."
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        help="Ruta personalizada para la base de datos de huellas SQLite."
    )
    parser.add_argument(
        "--auto-move",
        type=str,
        default=None,
        help="Mover automáticamente los duplicados inferiores a la carpeta especificada."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar qué sucedería sin mover o eliminar ningún archivo."
    )
    parser.add_argument(
        "--export-csv",
        type=str,
        default=None,
        help="Ruta para exportar los resultados en formato CSV."
    )

    args = parser.parse_args()

    if args.cli:
        return run_cli_mode(args)
    else:
        from gui.app import run_gui
        run_gui(initial_folder=args.folder)
        return 0


def run_cli_mode(args):
    """Headless CLI execution for scripts or automated servers."""
    if not args.folder or not os.path.isdir(args.folder):
        print("ERROR: Debes especificar una carpeta valida con --folder <ruta>")
        return 2

    from core.scanner import AudioScanner
    from core.database import Database
    from core.file_manager import auto_apply_recommendations, move_marked_duplicates, OperationStatus
    print(f">> Iniciando analisis acustico en: {args.folder}")

    db = Database(db_path=args.db)
    scanner = AudioScanner(db=db)
    exit_code = 0

    def cli_progress(stats):
        pct = (stats.files_scanned / max(1, stats.total_files_found)) * 100
        print(f"\r[{stats.phase}] {stats.files_scanned}/{stats.total_files_found} ({pct:.1f}%) | Duplicados: {stats.exact_duplicates_count + stats.acoustic_duplicates_count + stats.possible_duplicates_count}", end="", flush=True)

    try:
        groups = scanner.scan_directory(args.folder, progress_callback=cli_progress)
        print()

        print(f"\n>> Escaneo finalizado en {scanner.stats.elapsed_seconds:.1f}s")
        if not scanner.stats.is_complete:
            exit_code = 3
            print(f"ADVERTENCIA: cobertura incompleta. Archivos fallidos: {scanner.stats.files_failed}; "
                  f"bloques fallidos: {scanner.stats.worker_failures}; "
                  f"coincidencias candidatas descartadas: {scanner.stats.candidate_pairs_dropped}; "
                  f"huellas con información insuficiente: "
                  f"{getattr(scanner.stats, 'low_information_fingerprints', 0)}.")
        low_information = getattr(scanner.stats, "low_information_fingerprints", 0)
        if low_information:
            print(f"NOTA: {low_information} huella(s) acústica(s) repetitiva(s) no se usaron "
                  "para proponer coincidencias; los hashes exactos y PCM sí se comprobaron.")
        print(f"Total archivos analizados: {scanner.stats.files_scanned}")
        print(f"Duplicados exactos: {scanner.stats.exact_duplicates_count}")
        print(f"Duplicados acusticos: {scanner.stats.acoustic_duplicates_count}")
        print(f"Posibles duplicados: {scanner.stats.possible_duplicates_count}")
        savings_mb = scanner.stats.potential_space_saving / (1024 * 1024)
        print(f"Espacio recuperable: {savings_mb:.2f} MB\n")

        # Display Groups in Table
        for group in groups:
            sep = "-" * 60
            print(sep)
            print(f"Grupo {group.group_id} ({group.primary_type.value}) - Similitud: {group.average_similarity:.1f}%")
            print(sep)
            for track in group.tracks:
                is_best = (track.filepath == group.best_track_path)
                if getattr(group, "requires_manual_review", False):
                    action_tag = "REVISAR"
                else:
                    action_tag = "CONSERVAR" if is_best else "ELIMINAR"
                print(f"  [{action_tag}] {track.filename} | {track.format} | {track.bitrate}k | {track.formatted_duration} | {track.formatted_size} | Q:{track.quality_score}")
            print(f"  Recomendacion: {group.best_track_reason}\n")

        if args.export_csv:
            import csv
            with open(args.export_csv, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Grupo ID", "Tipo Duplicado", "Acción Recomendada", "Ruta Archivo", "Formato", "Bitrate", "Duración", "Tamaño bytes", "Puntaje Calidad", "Razón"])
                for group in groups:
                    for track in group.tracks:
                        is_best = (track.filepath == group.best_track_path)
                        if getattr(group, "requires_manual_review", False):
                            action = "REVISAR"
                        else:
                            action = "CONSERVAR" if is_best else "ELIMINAR"
                        writer.writerow([
                            group.group_id, group.primary_type.value, action, track.filepath,
                            track.format, track.bitrate, track.duration, track.filesize,
                            track.quality_score, group.best_track_reason if is_best else ""
                        ])
            print(f">> Resultados exportados a: {args.export_csv}\n")

        if args.auto_move:
            if args.dry_run:
                print(f"DRY-RUN: Se moverian los duplicados inferiores a: {args.auto_move}")
            else:
                auto_apply_recommendations(groups)
                print(f"Moviendo duplicados a: {args.auto_move}")
                result = move_marked_duplicates(groups, args.auto_move, db=db)
                print(f"Movidos: {result.success}. Errores: {result.failed}. Bloqueados: {result.blocked}")
                for log_line in result.logs:
                    print(f"  {log_line}")
                if result.status != OperationStatus.SUCCESS:
                    exit_code = 4
        return exit_code
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
