"""
Unit tests for the Dynamic Theming System (Dark / Light mode).
Validates palettes, QSS generation, persistence, in-place dictionary updates,
and component integration in PyQt6.
"""

import os
import json
import tempfile
import unittest
from unittest.mock import patch

from gui.styles import (
    THEME_DARK,
    THEME_LIGHT,
    get_theme_colors,
    get_qss,
    load_theme_preference,
    save_theme_preference,
    get_current_theme,
    apply_theme,
    COLORS,
    GLOBAL_QSS,
)


class TestThemingSystem(unittest.TestCase):
    def setUp(self):
        self.orig_theme = get_current_theme()

    def tearDown(self):
        apply_theme(self.orig_theme)

    def test_palettes_structure(self):
        """Ensures dark and light palettes have consistent keys."""
        required_keys = [
            "bg_darkest", "bg_sidebar", "bg_main", "bg_card", "border",
            "cyan", "cyan_dim", "cyan_bg", "primary", "primary_hover",
            "primary_text", "text_main", "text_muted", "text_dim",
            "success", "warning", "danger", "info"
        ]
        for key in required_keys:
            self.assertIn(key, THEME_DARK, f"Key {key} missing in THEME_DARK")
            self.assertIn(key, THEME_LIGHT, f"Key {key} missing in THEME_LIGHT")

        self.assertEqual(THEME_DARK["primary_text"], "#000000")
        self.assertEqual(THEME_LIGHT["primary_text"], "#FFFFFF")

    def test_get_theme_colors(self):
        """Verifies color retrieval for each theme."""
        dark_colors = get_theme_colors("dark")
        light_colors = get_theme_colors("light")
        self.assertEqual(dark_colors["bg_darkest"], "#0D0F12")
        self.assertEqual(light_colors["bg_darkest"], "#F1F5F9")

    def test_get_qss_generation(self):
        """Verifies valid QSS string generation with theme specific tokens."""
        qss_dark = get_qss("dark")
        self.assertIn("QMainWindow", qss_dark)
        self.assertIn("#0D0F12", qss_dark)
        self.assertIn("#00E5FF", qss_dark)

        qss_light = get_qss("light")
        self.assertIn("QMainWindow", qss_light)
        self.assertIn("#F1F5F9", qss_light)
        self.assertIn("#0284C7", qss_light)

    def test_theme_persistence_roundtrip(self):
        """Tests saving and loading theme preference to a temporary file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, "ui_settings.json")
            with patch("gui.styles.get_ui_settings_path", return_value=test_path):
                # Default when file doesn't exist
                self.assertEqual(load_theme_preference(), "dark")

                # Save light
                save_theme_preference("light")
                self.assertTrue(os.path.exists(test_path))
                self.assertEqual(load_theme_preference(), "light")

                # Save dark
                save_theme_preference("dark")
                self.assertEqual(load_theme_preference(), "dark")

                # Corrupt file fallback
                with open(test_path, "w", encoding="utf-8") as f:
                    f.write("INVALID JSON")
                self.assertEqual(load_theme_preference(), "dark")

    def test_apply_theme_in_place_mutation(self):
        """Verifies apply_theme mutates the COLORS reference in-place."""
        apply_theme("light")
        self.assertEqual(get_current_theme(), "light")
        self.assertEqual(COLORS["bg_darkest"], "#F1F5F9")
        self.assertEqual(COLORS["text_main"], "#0F172A")

        apply_theme("dark")
        self.assertEqual(get_current_theme(), "dark")
        self.assertEqual(COLORS["bg_darkest"], "#0D0F12")
        self.assertEqual(COLORS["text_main"], "#F3F4F6")

    def test_apply_theme_skips_reapplying_identical_stylesheet(self):
        """Repeated saves of the active theme must not repolish the whole app."""
        class FakeApplication:
            def __init__(self):
                self.stylesheet = ""
                self.set_calls = 0

            def styleSheet(self):
                return self.stylesheet

            def setStyleSheet(self, stylesheet):
                self.stylesheet = stylesheet
                self.set_calls += 1

        fake_app = FakeApplication()
        with patch("gui.styles.save_theme_preference"):
            apply_theme("dark", fake_app)
            first_count = fake_app.set_calls
            apply_theme("dark", fake_app)

        self.assertEqual(first_count, 1)
        self.assertEqual(fake_app.set_calls, 1)


class TestGUIComponentsTheming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def test_sidebar_refresh_theme(self):
        from gui.components.sidebar import Sidebar
        sidebar = Sidebar()
        
        apply_theme("dark")
        sidebar.refresh_theme()
        self.assertIn("Claro", sidebar.btn_theme_toggle.toolTip())

        apply_theme("light")
        sidebar.refresh_theme()
        self.assertIn("Oscuro", sidebar.btn_theme_toggle.toolTip())

    def test_settings_view_theme_combo(self):
        from unittest.mock import MagicMock
        from gui.components.settings_view import SettingsView
        mock_db = MagicMock()
        mock_db.get_total_tracks_count.return_value = 100
        mock_db.get_database_size_bytes.return_value = 1024 * 1024
        mock_db.db_path = ":memory:"

        settings = SettingsView(db=mock_db)
        apply_theme("dark")
        settings.refresh_theme()
        self.assertEqual(settings.combo_theme.currentData(), "dark")

        apply_theme("light")
        settings.refresh_theme()
        self.assertEqual(settings.combo_theme.currentData(), "light")
        self.assertIn(THEME_LIGHT["bg_card"], settings.styleSheet())

    def test_data_pages_refresh_literal_surfaces_in_both_themes(self):
        """Every non-duplicates page must replace stale card/table colors."""
        from unittest.mock import MagicMock
        from gui.components.library_view import LibraryView
        from gui.components.scanner_view import ScannerView
        from gui.components.quality_view import QualityView

        mock_db = MagicMock()
        mock_db.get_all_tracks.return_value = []
        pages = (LibraryView(mock_db), ScannerView(), QualityView(mock_db))

        for theme, palette in (("dark", THEME_DARK), ("light", THEME_LIGHT)):
            apply_theme(theme)
            for page in pages:
                page.refresh_theme()
                self.assertIn(palette["bg_card"], page.styleSheet())
                self.assertIn(palette["bg_main"], page.styleSheet())

        for button in (
            pages[2].btn_all,
            pages[2].btn_fake,
            pages[2].btn_lossless,
            pages[2].btn_low,
            pages[2].btn_hires,
        ):
            self.assertEqual(button.objectName(), "filter_tab")

    def test_bottom_player_refresh_theme(self):
        from gui.components.bottom_player import BottomPlayerBar
        player = BottomPlayerBar()
        apply_theme("light")
        player.refresh_theme()
        self.assertEqual(player.lbl_title.styleSheet(), f"color: {COLORS['text_main']};")

    def test_stats_bar_refresh_theme(self):
        from gui.components.stats_bar import StatsBar
        stats_bar = StatsBar()
        apply_theme("dark")
        stats_bar.refresh_theme()
        self.assertEqual(stats_bar.card_space.objectName(), "stat_card_large")
        apply_theme("light")
        stats_bar.refresh_theme()
        self.assertEqual(stats_bar.card_space.objectName(), "stat_card_large")

    def test_duplicate_card_theming_and_actions(self):
        from core.models import DuplicateGroup, AudioTrack, DuplicateType, FileAction
        from gui.components.duplicate_card import DuplicateGroupCard
        from PyQt6.QtWidgets import QPushButton

        t1 = AudioTrack(filepath="C:/m/t1.wav", format="WAV", duration=100.0, filesize=1000000,
                        bitrate=1411, samplerate=44100, bit_depth=16, quality_score=84.0, action=FileAction.KEEP)
        t2 = AudioTrack(filepath="C:/m/t2.wav", format="WAV", duration=100.0, filesize=1000000,
                        bitrate=1411, samplerate=44100, bit_depth=16, quality_score=80.0, action=FileAction.DELETE)
        group = DuplicateGroup(group_id="group_1", primary_type=DuplicateType.EXACT_HASH,
                               tracks=[t1, t2], best_track_path="C:/m/t1.wav")

        apply_theme("dark")
        card = DuplicateGroupCard(group)
        self.assertEqual(card.objectName(), "DuplicateGroupCard")

        # Action buttons
        btn_keep = card.findChild(QPushButton, "action_keep")
        btn_delete = card.findChild(QPushButton, "action_delete")
        self.assertIsNotNone(btn_keep)
        self.assertIsNotNone(btn_delete)
        self.assertEqual(btn_keep.text(), "CONSERVAR")
        self.assertEqual(btn_delete.text(), "ELIMINAR")
        self.assertIn(COLORS["success"], btn_keep.styleSheet())
        self.assertIn(COLORS["danger"], btn_delete.styleSheet())

        # Toggle keep -> delete
        btn_keep.click()
        self.assertEqual(btn_keep.text(), "ELIMINAR")
        self.assertEqual(btn_keep.objectName(), "action_delete")

        # Toggle delete -> keep
        btn_keep.click()
        self.assertEqual(btn_keep.text(), "CONSERVAR")
        self.assertEqual(btn_keep.objectName(), "action_keep")
        self.assertIn(COLORS["success"], btn_keep.styleSheet())

    def test_app_toggle_theme_with_active_groups(self):
        from gui.app import AudioDuplicateDetectorApp
        from core.models import DuplicateGroup, AudioTrack, DuplicateType, FileAction
        apply_theme("dark")
        win = AudioDuplicateDetectorApp()
        t1 = AudioTrack(filepath="C:/m/t1.wav", format="WAV", duration=10.0, filesize=1000, action=FileAction.KEEP)
        t2 = AudioTrack(filepath="C:/m/t2.wav", format="WAV", duration=10.0, filesize=1000, action=FileAction.DELETE)
        g = DuplicateGroup(group_id="g1", primary_type=DuplicateType.EXACT_HASH, tracks=[t1, t2], best_track_path="C:/m/t1.wav")
        win.all_groups = [g]
        win._refresh_view()
        self.assertEqual(win.PAGE_SIZE, 20)

        # Started in dark -> button offers switch to Claro
        self.assertIn("Claro", win.sidebar.btn_theme_toggle.toolTip())

        # Toggle to light -> button offers switch to Oscuro
        win._toggle_theme()
        self.assertIn("Oscuro", win.sidebar.btn_theme_toggle.toolTip())

        # Toggle back to dark -> button offers switch to Claro
        win._toggle_theme()
        self.assertIn("Claro", win.sidebar.btn_theme_toggle.toolTip())


if __name__ == "__main__":
    unittest.main()
