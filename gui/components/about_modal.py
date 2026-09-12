"""
About Modal — Commercial 'Acerca de Nosotros' dialog for Audio Cleaner Pro.
Displays corporate branding, commercial license status, privacy commitment, and legal terms.
"""

import os
import webbrowser
from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QMessageBox, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import qtawesome as qta

from gui.styles import COLORS


class LegalInfoDialog(QDialog):
    """Auxiliary dialog displaying commercial terms or privacy policy."""
    def __init__(self, title: str, content: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(500, 420)
        self.setModal(True)
        self.setStyleSheet(f"background-color: {COLORS['bg_card']}; color: {COLORS['text_main']};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        lbl_t = QLabel(title)
        lbl_t.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl_t.setStyleSheet(f"color: {COLORS['cyan']};")
        layout.addWidget(lbl_t)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background: transparent;")
        
        lbl_content = QLabel(content)
        lbl_content.setFont(QFont("Segoe UI", 9))
        lbl_content.setStyleSheet(f"color: {COLORS['text_muted']}; line-height: 1.4;")
        lbl_content.setWordWrap(True)
        scroll.setWidget(lbl_content)
        layout.addWidget(scroll, stretch=1)

        btn_close = QPushButton("Entendido")
        btn_close.setObjectName("primary")
        btn_close.setFixedHeight(34)
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)


class AboutModal(QDialog):
    """
    Commercial 'Acerca de Audio Cleaner Pro' Modal.
    Frameless, polished dark UI conforming to the design tokens.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(540, 600)

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
        card_layout.setSpacing(16)

        # ── Header ────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(14)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon("fa5s.fingerprint", color=COLORS["cyan"]).pixmap(32, 32))
        header_row.addWidget(icon_lbl)

        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        title = QLabel("AUDIO CLEANER PRO")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['text_main']}; letter-spacing: 1px;")
        header_text.addWidget(title)

        sub = QLabel("Suite Profesional de Deduplicación y Calidad Acústica")
        sub.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        sub.setStyleSheet(f"color: {COLORS['cyan']};")
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

        # ── Card 1: License Status ────────────────────────────────
        lic_box = QFrame()
        lic_box.setStyleSheet(
            f"background-color: {COLORS['bg_darkest']};"
            f"border: 1px solid {COLORS['border']}; border-radius: 8px;"
        )
        lic_layout = QVBoxLayout(lic_box)
        lic_layout.setContentsMargins(14, 12, 14, 12)
        lic_layout.setSpacing(8)

        lic_top = QHBoxLayout()
        lbl_lic_title = QLabel("ESTADO DE LA LICENCIA COMERCIAL")
        lbl_lic_title.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_lic_title.setStyleSheet(f"color: {COLORS['text_dim']}; letter-spacing: 1px;")
        lic_top.addWidget(lbl_lic_title)
        lic_top.addStretch()

        badge_active = QLabel("● ACTIVA · VITALICIA")
        badge_active.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        badge_active.setStyleSheet(
            f"background-color: {COLORS['success_bg']}; color: {COLORS['success']};"
            f"border: 1px solid {COLORS['success']}; border-radius: 4px; padding: 2px 8px;"
        )
        lic_top.addWidget(badge_active)
        lic_layout.addLayout(lic_top)

        lic_desc = QLabel("Registrado a: Usuario Autorizado / Licencia Comercial Pro\nVersión: 1.0.0 Pro · 64-bit Architecture (Build 2026.09)")
        lic_desc.setFont(QFont("Segoe UI", 8))
        lic_desc.setStyleSheet(f"color: {COLORS['text_muted']};")
        lic_layout.addWidget(lic_desc)

        card_layout.addWidget(lic_box)

        # ── Card 2: Privacy & Acoustic Security Guarantee ─────────
        priv_box = QFrame()
        priv_box.setStyleSheet(
            f"background-color: {COLORS['bg_darkest']};"
            f"border: 1px solid {COLORS['border']}; border-radius: 8px;"
        )
        priv_layout = QVBoxLayout(priv_box)
        priv_layout.setContentsMargins(14, 12, 14, 12)
        priv_layout.setSpacing(6)

        priv_title = QHBoxLayout()
        icon_shield = QLabel()
        icon_shield.setPixmap(qta.icon("fa5s.shield-alt", color=COLORS["cyan"]).pixmap(14, 14))
        priv_title.addWidget(icon_shield)
        lbl_priv = QLabel("GARANTÍA DE PRIVACIDAD Y SEGURIDAD LOCAL")
        lbl_priv.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl_priv.setStyleSheet(f"color: {COLORS['text_dim']}; letter-spacing: 1px;")
        priv_title.addWidget(lbl_priv)
        priv_title.addStretch()
        priv_layout.addLayout(priv_title)

        priv_text = QLabel(
            "• Procesamiento y huellas acústicas 100% locales.\n"
            "• Sin telemetría oculta ni subida de archivos a la nube.\n"
            "• Tu música y metadatos permanecen bajo tu custodia absoluta."
        )
        priv_text.setFont(QFont("Segoe UI", 8))
        priv_text.setStyleSheet(f"color: {COLORS['text_muted']}; line-height: 1.3;")
        priv_layout.addWidget(priv_text)

        card_layout.addWidget(priv_box)

        # ── Card 3: Legal & Corporate Details ──────────────────────
        corp_box = QVBoxLayout()
        corp_box.setSpacing(8)

        lbl_corp = QLabel("© 2026 Audio Cleaner Software Studio. Todos los derechos reservados.")
        lbl_corp.setFont(QFont("Segoe UI", 8))
        lbl_corp.setStyleSheet(f"color: {COLORS['text_dim']};")
        corp_box.addWidget(lbl_corp)

        links_row = QHBoxLayout()
        links_row.setSpacing(8)

        btn_terms = QPushButton("Términos del Servicio")
        btn_terms.setObjectName("ghost")
        btn_terms.setFont(QFont("Segoe UI", 8))
        btn_terms.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_terms.clicked.connect(self._show_terms)
        links_row.addWidget(btn_terms)

        btn_privacy = QPushButton("Política de Privacidad")
        btn_privacy.setObjectName("ghost")
        btn_privacy.setFont(QFont("Segoe UI", 8))
        btn_privacy.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_privacy.clicked.connect(self._show_privacy)
        links_row.addWidget(btn_privacy)

        btn_web = QPushButton("Soporte Comercial")
        btn_web.setObjectName("ghost")
        btn_web.setFont(QFont("Segoe UI", 8))
        btn_web.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_web.clicked.connect(self._show_support_info)
        links_row.addWidget(btn_web)

        links_row.addStretch()
        corp_box.addLayout(links_row)
        card_layout.addLayout(corp_box)

        card_layout.addStretch()

        # ── Bottom Action ─────────────────────────────────────────
        btn_done = QPushButton("Cerrar")
        btn_done.setObjectName("primary")
        btn_done.setFixedHeight(36)
        btn_done.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_done.clicked.connect(self.accept)
        card_layout.addWidget(btn_done)

        outer.addWidget(card)

    def _show_terms(self):
        terms_text = (
            "TÉRMINOS DEL SERVICIO — AUDIO CLEANER PRO\n\n"
            "1. Concesión de Licencia: Audio Cleaner Software Studio otorga al usuario una licencia "
            "comercial no exclusiva e intransferible para usar el software de acuerdo con la edición adquirida.\n\n"
            "2. Integridad de Archivos: El software proporciona recomendaciones basadas en algoritmos acústicos "
            "rigurosos y protecciones de copia única. La confirmación final de eliminación o reubicación de archivos "
            "es responsabilidad del usuario.\n\n"
            "3. Actualizaciones: Las licencias comerciales activas tienen derecho a actualizaciones de mantenimiento "
            "y mejoras de compatibilidad de la versión mayor adquirida.\n\n"
            "4. Soporte Técnico: Los clientes de pago cuentan con atención prioritaria ante incidencias operativas."
        )
        dlg = LegalInfoDialog("Términos del Servicio Comercial", terms_text, self)
        dlg.exec()

    def _show_privacy(self):
        priv_text = (
            "POLÍTICA DE PRIVACIDAD Y PROTECCIÓN DE DATOS\n\n"
            "1. Cero Telemetría Invasiva: Audio Cleaner Pro opera de forma autónoma y fuera de línea en su equipo local. "
            "No se recopilan historiales de reproducción, rutas de carpetas privadas ni nombres de archivos con fines comerciales.\n\n"
            "2. Análisis Local: Las huellas acústicas Chromaprint y los espectros FFT se procesan y almacenan "
            "exclusivamente en la base de datos local SQLite de su equipo.\n\n"
            "3. Comunicaciones de Soporte: La información enviada voluntariamente a través del buzón de sugerencias o correo "
            "de soporte se utiliza únicamente para dar seguimiento a su solicitud."
        )
        dlg = LegalInfoDialog("Garantía de Privacidad y Datos", priv_text, self)
        dlg.exec()

    def _show_support_info(self):
        QMessageBox.information(
            self,
            "Soporte al Cliente",
            "Atención al Cliente y Soporte Técnico Profesional:\n\n"
            "• Correo oficial: support@audiocleaner.app\n"
            "• Horario de atención: Lunes a Viernes (Soporte prioritario para licencias Pro)\n"
            "• Tiempo estimado de respuesta: Menos de 24 horas hábiles"
        )
