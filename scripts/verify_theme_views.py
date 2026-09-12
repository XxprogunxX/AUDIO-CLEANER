"""Render every main page in both themes for fast visual regression checks."""

import argparse
import json
import os
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=os.path.dirname(os.path.dirname(__file__)))
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tracks", type=int, default=100)
    args = parser.parse_args()

    project = os.path.abspath(args.project)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)
    sys.path.insert(0, project)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    from PyQt6.QtWidgets import QApplication
    from core.models import AudioTrack
    from gui.app import AudioDuplicateDetectorApp
    from gui.styles import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme("dark", app)
    AudioDuplicateDetectorApp._load_saved_session = lambda self, initial_folder=None: None

    window = AudioDuplicateDetectorApp()
    window.resize(1600, 900)
    window.show()
    app.processEvents()

    sections = ("Biblioteca", "Escaneo", "Calidad", "Configuración")
    tracks = [
        AudioTrack(
            filepath=f"C:/music/album/pista-{index:03d}.mp3",
            title=f"Pista de prueba {index:03d}",
            artist=f"Artista {index % 8 + 1}",
            album=f"Album {index % 5 + 1}",
            format="FLAC" if index % 9 == 0 else "MP3",
            duration=180.0 + index,
            filesize=8_000_000 + index * 10_000,
            bitrate=900 if index % 9 == 0 else 128 + (index % 4) * 64,
            samplerate=48000 if index % 3 == 0 else 44100,
            bit_depth=24 if index % 9 == 0 else 16,
            quality_score=35.0 + index % 65,
        )
        for index in range(args.tracks)
    ]
    results = []
    for section in sections:
        window._on_nav_changed(section)
        if section == "Biblioteca":
            window.library_view.reload_tracks(tracks)
        elif section == "Calidad":
            window.quality_view.reload_tracks(tracks)
        app.processEvents()
        for theme in ("light", "dark"):
            started = time.perf_counter()
            window._set_theme(theme)
            app.processEvents()
            elapsed_ms = (time.perf_counter() - started) * 1000
            safe_section = section.lower().replace("ó", "o")
            image_path = os.path.join(output_dir, f"{safe_section}-{theme}.png")
            if not window.grab().save(image_path):
                raise RuntimeError(f"No se pudo guardar {image_path}")
            results.append({
                "section": section,
                "theme": theme,
                "switch_ms": round(elapsed_ms, 2),
                "image": image_path,
            })

    print(json.dumps(results, ensure_ascii=False, indent=2))
    window.close()
    app.processEvents()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
