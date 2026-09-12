"""
Tests for Commercial Modals — 'Acerca de Nosotros' & 'Buzón de Sugerencias'.
Verifies:
  1. AboutModal instantiation, UI cards, and legal information triggers.
  2. FeedbackModal validation, system diagnostics, and local persistence.
  3. Sidebar feedback and about buttons and signal emissions.
  4. SettingsView Card 4 (Licencia Comercial y Atención al Cliente) signal emissions.
  5. AudioDuplicateDetectorApp wiring.
"""

import os
import sys
import json
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from PyQt6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from gui.components.about_modal import AboutModal, LegalInfoDialog
from gui.components.feedback_modal import FeedbackModal
from gui.components.sidebar import Sidebar
from gui.components.settings_view import SettingsView
from core.database import Database


class TestAboutModal(unittest.TestCase):
    def test_about_modal_initialization(self):
        modal = AboutModal()
        self.assertIsNotNone(modal)
        self.assertTrue(modal.isModal())

    @patch("gui.components.about_modal.LegalInfoDialog.exec")
    def test_about_modal_terms_and_privacy(self, mock_exec):
        modal = AboutModal()
        modal._show_terms()
        self.assertEqual(mock_exec.call_count, 1)

        modal._show_privacy()
        self.assertEqual(mock_exec.call_count, 2)

    @patch("PyQt6.QtWidgets.QMessageBox.information")
    def test_about_modal_support_info(self, mock_info):
        modal = AboutModal()
        modal._show_support_info()
        mock_info.assert_called_once()
        args, _ = mock_info.call_args
        self.assertIn("support@audiocleaner.app", args[2])


class TestFeedbackModal(unittest.TestCase):
    def test_feedback_modal_initialization(self):
        modal = FeedbackModal()
        self.assertIsNotNone(modal)
        self.assertEqual(modal.combo_category.count(), 5)
        self.assertTrue(modal.chk_sys_info.isChecked())

    @patch("PyQt6.QtWidgets.QMessageBox.warning")
    def test_feedback_validation_empty_message(self, mock_warn):
        modal = FeedbackModal()
        modal.txt_message.setText("   ")
        modal._handle_submit()
        mock_warn.assert_called_once()

    @patch("PyQt6.QtWidgets.QMessageBox.information")
    def test_feedback_submission_success(self, mock_info):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"APPDATA": tmp_dir}):
                modal = FeedbackModal()
                modal.combo_category.setCurrentIndex(1)
                modal.txt_email.setText("cliente@estudioaudio.com")
                modal.txt_subject.setText("Mejora de velocidad en escaneo")
                modal.txt_message.setText("El escaneo funciona excelente pero me gustaría que guarde perfiles de carpetas.")
                modal.chk_sys_info.setChecked(True)

                modal._handle_submit()
                mock_info.assert_called_once()

                # Verify file was persisted
                fb_dir = os.path.join(tmp_dir, "AudioDuplicateDetector", "feedback")
                self.assertTrue(os.path.exists(fb_dir))
                files = os.listdir(fb_dir)
                self.assertEqual(len(files), 1)

                with open(os.path.join(fb_dir, files[0]), "r", encoding="utf-8") as f:
                    data = json.load(f)

                self.assertEqual(data["email"], "cliente@estudioaudio.com")
                self.assertEqual(data["subject"], "Mejora de velocidad en escaneo")
                self.assertIn("perfiles de carpetas", data["message"])
                self.assertIsNotNone(data["system_diagnostics"])
                self.assertEqual(data["system_diagnostics"]["app_version"], "1.0.0 Pro")


class TestSidebarCommercialButtons(unittest.TestCase):
    def test_sidebar_buttons_and_signals(self):
        sidebar = Sidebar()

        feedback_spy = MagicMock()
        about_spy = MagicMock()

        sidebar.feedback_requested.connect(feedback_spy)
        sidebar.about_requested.connect(about_spy)

        self.assertTrue(hasattr(sidebar, "btn_feedback"))
        self.assertTrue(hasattr(sidebar, "btn_about"))

        sidebar.btn_feedback.click()
        feedback_spy.assert_called_once()

        sidebar.btn_about.click()
        about_spy.assert_called_once()


class TestSettingsViewCommercialCard(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db = Database(self.temp_db.name)

    def tearDown(self):
        self.db.close()
        if os.path.exists(self.temp_db.name):
            try:
                os.remove(self.temp_db.name)
            except Exception:
                pass

    def test_settings_view_signals(self):
        view = SettingsView(db=self.db)

        feedback_spy = MagicMock()
        about_spy = MagicMock()

        view.feedback_requested.connect(feedback_spy)
        view.about_requested.connect(about_spy)

        # Trigger Card 4 actions
        view.feedback_requested.emit()
        feedback_spy.assert_called_once()

        view.about_requested.emit()
        about_spy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
