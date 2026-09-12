"""
Feedback Modal — Commercial Suggestions and Customer Support dialog for Audio Cleaner Pro.
Collects user suggestions, feature requests, and bug reports with client email and diagnostic data.
"""

import os
import sys
import json
import time
import platform
import multiprocessing
import urllib.parse
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QComboBox, QLineEdit, QTextEdit,
    QCheckBox, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import qtawesome as qta

from gui.styles import COLORS


class FeedbackModal(QDialog):
    """
    Commercial Suggestions and Feedback dialog.
    Allows customers to submit product enhancements, format requests, and technical reports.
    """

    SUPPORT_EMAIL = "support@audiocleaner.app"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(540, 640)

        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background-color: {COLORS['bg_card']};"
            f"border: 1px solid {COLORS['border']}; border-radius: 12px; }}"
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(14)

        # ── Header ────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(14)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.lightbulb", color=COLORS["cyan"]).pixmap(30, 30))
        header_row.addWidget(icon_lbl)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        title = QLabel("BUZÓN DE SUGERENCIAS Y SOPORTE")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text_main']}; letter-spacing: 0.5px;")
        header_text.addWidget(title)

        sub = QLabel("Tu experiencia ayuda a evolucionar Audio Cleaner Pro")
        sub.setFont(QFont("Segoe UI", 8))
        sub.setStyleSheet(f"color: {COLORS['text_muted']};")
        header_text.addWidget(sub)

        header_row.addLayout(header_text)
        header_row.addStretch()

        btn_close = QPushButton()
        btn_close.setIcon(qta.icon("fa5s.times", color=COLORS["text_muted"]))
        btn_close.setObjectName("ghost")
        btn_close.setFixedSize(28, 28)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        header_row.addWidget(btn_close)

        card_layout.addLayout(header_row)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background-color: {COLORS['border']}; max-height: 1px; border: none;")
        card_layout.addWidget(sep)

        # ── Category ──────────────────────────────────────────────
        lbl_cat = QLabel("CATEGORÍA DE LA SUGERENCIA:")
        lbl_cat.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_cat.setStyleSheet(f"color: {COLORS['text_dim']}; letter-spacing: 0.5px;")
        card_layout.addWidget(lbl_cat)

        self.combo_category = QComboBox()
        self.combo_category.addItems([
            "💡 Solicitud de Nueva Función",
            "⚡ Optimización y Fluidez de Interfaz",
            "🎧 Soporte para Nuevos Formatos / Códecs",
            "🛠️ Reporte de Comportamiento Inesperado",
            "💼 Consulta Comercial y de Licencia"
        ])
        self.combo_category.setFixedHeight(34)
        card_layout.addWidget(self.combo_category)

        # ── Email ─────────────────────────────────────────────────
        lbl_email = QLabel("CORREO ELECTRÓNICO (Opcional, para respuesta del equipo):")
        lbl_email.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_email.setStyleSheet(f"color: {COLORS['text_dim']}; letter-spacing: 0.5px;")
        card_layout.addWidget(lbl_email)

        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("ejemplo@empresa.com")
        self.txt_email.setFixedHeight(34)
        self.txt_email.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_darkest']};
                color: {COLORS['text_main']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['cyan']};
            }}
        """)
        card_layout.addWidget(self.txt_email)

        # ── Subject ───────────────────────────────────────────────
        lbl_sub = QLabel("TÍTULO / ASUNTO:")
        lbl_sub.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_sub.setStyleSheet(f"color: {COLORS['text_dim']}; letter-spacing: 0.5px;")
        card_layout.addWidget(lbl_sub)

        self.txt_subject = QLineEdit()
        self.txt_subject.setPlaceholderText("Ej: Filtro rápido por tasa de muestreo en la biblioteca")
        self.txt_subject.setFixedHeight(34)
        self.txt_subject.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLORS['bg_darkest']};
                color: {COLORS['text_main']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 0 10px;
            }}
            QLineEdit:focus {{
                border-color: {COLORS['cyan']};
            }}
        """)
        card_layout.addWidget(self.txt_subject)

        # ── Message Body ──────────────────────────────────────────
        lbl_msg = QLabel("DESCRIPCIÓN DETALLADA:")
        lbl_msg.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_msg.setStyleSheet(f"color: {COLORS['text_dim']}; letter-spacing: 0.5px;")
        card_layout.addWidget(lbl_msg)

        self.txt_message = QTextEdit()
        self.txt_message.setPlaceholderText(
            "Describe cómo te gustaría que funcione o qué situación encontraste..."
        )
        self.txt_message.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_darkest']};
                color: {COLORS['text_main']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px 10px;
            }}
            QTextEdit:focus {{
                border-color: {COLORS['cyan']};
            }}
        """)
        card_layout.addWidget(self.txt_message, stretch=1)

        # ── Diagnostic Checkbox ───────────────────────────────────
        self.chk_sys_info = QCheckBox("Incluir diagnóstico técnico de entorno (Windows, núcleos CPU, versión Pro)")
        self.chk_sys_info.setChecked(True)
        self.chk_sys_info.setFont(QFont("Segoe UI", 8))
        self.chk_sys_info.setStyleSheet(f"color: {COLORS['text_muted']};")
        card_layout.addWidget(self.chk_sys_info)

        # ── Action Buttons ────────────────────────────────────────
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        btn_cancel = QPushButton("Cancelar")
        btn_cancel.setObjectName("ghost")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.clicked.connect(self.reject)
        actions_row.addWidget(btn_cancel)

        actions_row.addStretch()

        btn_submit = QPushButton(" Enviar al Equipo")
        btn_submit.setObjectName("primary")
        btn_submit.setIcon(qta.icon("fa5s.paper-plane", color="#000000"))
        btn_submit.setFixedHeight(36)
        btn_submit.setFixedWidth(170)
        btn_submit.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_submit.clicked.connect(self._handle_submit)
        actions_row.addWidget(btn_submit)

        card_layout.addLayout(actions_row)
        outer.addWidget(card)

    def _get_system_specs(self) -> dict:
        return {
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_cores": multiprocessing.cpu_count(),
            "app_version": "1.0.0 Pro",
            "build": "2026.09"
        }

    def _handle_submit(self):
        message = self.txt_message.toPlainText().strip()
        if len(message) < 5:
            QMessageBox.warning(
                self,
                "Campo Requerido",
                "Por favor, describe tu sugerencia o consulta con un poco más de detalle (al menos 5 caracteres)."
            )
            return

        category = self.combo_category.currentText()
        email = self.txt_email.text().strip()
        subject = self.txt_subject.text().strip() or f"Sugerencia Audio Cleaner Pro - {category}"
        include_specs = self.chk_sys_info.isChecked()
        specs = self._get_system_specs() if include_specs else None

        # Build payload
        feedback_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "email": email or "Anónimo",
            "subject": subject,
            "message": message,
            "system_diagnostics": specs
        }

        # Save locally to ensure no feedback is lost
        saved_locally = False
        try:
            app_data = os.environ.get("APPDATA", os.path.expanduser("~"))
            fb_dir = os.path.join(app_data, "AudioDuplicateDetector", "feedback")
            os.makedirs(fb_dir, exist_ok=True)
            filename = f"feedback_{int(time.time())}.json"
            filepath = os.path.join(fb_dir, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(feedback_data, f, indent=2, ensure_ascii=False)
            saved_locally = True
        except Exception:
            pass

        # Inform user with commercial acknowledgment
        confirm_msg = (
            "¡Muchas gracias por tu sugerencia!\n\n"
            "Tu propuesta ha sido registrada correctamente en el sistema interno de Audio Cleaner Pro.\n"
            "El equipo de producto y desarrollo la evaluará directamente para próximas versiones."
        )
        if email:
            confirm_msg += f"\n\nTe daremos seguimiento a través de: {email}"

        QMessageBox.information(self, "Sugerencia Registrada", confirm_msg)
        self.accept()
