"""Small off-screen smoke benchmark for the dynamic theme path."""

import argparse
import json
import os
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=os.path.dirname(os.path.dirname(__file__)))
    parser.add_argument("--groups", type=int, default=50)
    parser.add_argument("--page-size", type=int, default=0)
    parser.add_argument("--screenshot", default="")
    parser.add_argument("--skip-component-refresh", action="store_true")
    args = parser.parse_args()

    project = os.path.abspath(args.project)
    sys.path.insert(0, project)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    from PyQt6.QtWidgets import QApplication
    from core.models import AudioTrack, DuplicateGroup, DuplicateType, FileAction
    from gui.app import AudioDuplicateDetectorApp
    from gui.styles import apply_theme

    app = QApplication.instance() or QApplication([])
    apply_theme("dark", app)

    # The benchmark supplies deterministic synthetic groups and does not need
    # session recovery or a real music folder.
    AudioDuplicateDetectorApp._load_saved_session = lambda self, initial_folder=None: None
    window = AudioDuplicateDetectorApp()
    if args.page_size:
        window.PAGE_SIZE = args.page_size
    groups = []
    for index in range(args.groups):
        tracks = [
            AudioTrack(
                filepath=f"C:/music/{index}/original.wav",
                format="WAV",
                duration=180.0,
                filesize=20_000_000,
                bitrate=1411,
                samplerate=44100,
                bit_depth=16,
                quality_score=84.0,
                action=FileAction.KEEP,
            ),
            AudioTrack(
                filepath=f"C:/music/{index}/copy.wav",
                format="WAV",
                duration=180.0,
                filesize=20_000_000,
                bitrate=1411,
                samplerate=44100,
                bit_depth=16,
                quality_score=80.0,
                action=FileAction.DELETE,
            ),
        ]
        groups.append(
            DuplicateGroup(
                group_id=f"group_{index}",
                primary_type=DuplicateType.EXACT_HASH,
                tracks=tracks,
                best_track_path=tracks[0].filepath,
            )
        )

    render_started = time.perf_counter()
    window.all_groups = groups
    window._refresh_view()
    window.resize(1280, 860)
    window.show()
    app.processEvents()
    render_ms = (time.perf_counter() - render_started) * 1000

    if args.skip_component_refresh:
        window._refresh_all_theme_components = lambda: None

    timings = []
    for theme in ("light", "dark", "light"):
        started = time.perf_counter()
        window._set_theme(theme)
        app.processEvents()
        timings.append(round((time.perf_counter() - started) * 1000, 2))

    if args.screenshot:
        window.grab().save(os.path.abspath(args.screenshot))

    print(json.dumps({
        "project": project,
        "requested_groups": args.groups,
        "rendered_cards": min(args.groups, window.PAGE_SIZE),
        "initial_render_ms": round(render_ms, 2),
        "theme_switch_ms": timings,
        "theme_switch_avg_ms": round(sum(timings) / len(timings), 2),
    }))
    window.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
