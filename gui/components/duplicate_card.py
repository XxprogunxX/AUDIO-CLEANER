"""
Interactive Duplicate Group Card with side-by-side file comparison and action controls for PyQt6.
"""

import os
from typing import Callable, Optional
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

from core.models import DuplicateGroup, AudioTrack, DuplicateType, FileAction
from core.file_manager import open_file_in_explorer
from gui.components.audio_player import AudioPlayer
from gui.components.ab_comparison import ABComparisonDialog
from gui.styles import COLORS, get_theme_colors, get_current_theme
import qtawesome as qta


class DuplicateGroupCard(QFrame):
    def __init__(
        self,
        group: DuplicateGroup,
        on_action_changed: Optional[Callable] = None,
        parent=None
    ):
        super().__init__(parent)
        self.group = group
        self.on_action_changed = on_action_changed
        self.player = AudioPlayer.get_instance()
        self.track_rows = []
        self._track_widgets = {}
        self._theme_icon_buttons = []
        
        # Connect to global player signals
        self.player.playback_changed.connect(self._on_playback_changed)

        # Card base styling
        self.setObjectName("DuplicateGroupCard")
        
        self._build_ui()

    def _build_ui(self):
        c = get_theme_colors(get_current_theme())
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(8)

        # 1. Header Banner
        header = QFrame()
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(10, 8, 10, 8)

        lbl_gid = QLabel(f"Grupo: {self.group.group_id}")
        lbl_gid.setObjectName("subtitle")
        h_layout.addWidget(lbl_gid)

        # Duplicate Type Badge
        _, _, badge_text = self._get_badge_style(self.group.primary_type, c)
        lbl_badge = QLabel(f" {badge_text} ")
        lbl_badge.setObjectName(self._badge_object_name(self.group.primary_type))
        h_layout.addWidget(lbl_badge)

        # Similarity
        lbl_sim = QLabel(f"Similitud: {self.group.average_similarity:.1f}%")
        lbl_sim.setObjectName("similarity_label")
        h_layout.addWidget(lbl_sim)
        
        h_layout.addStretch()

        # Space saving
        savings_mb = self.group.space_saving_bytes / (1024 * 1024)
        lbl_savings = QLabel(f"Ahorro: {savings_mb:.1f} MB")
        lbl_savings.setObjectName("savings_label")
        h_layout.addWidget(lbl_savings)

        # Compare A/B button (only when there are exactly 2 tracks)
        if len(self.group.tracks) == 2:
            btn_ab = QPushButton(" A/B")
            btn_ab.setObjectName("ghost")
            btn_ab.setIcon(qta.icon("fa5s.columns", color=c["cyan"]))
            btn_ab.setFixedHeight(26)
            btn_ab.setToolTip("Comparación espectral A vs B")
            btn_ab.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_ab.clicked.connect(self._open_ab_comparison)
            self._theme_icon_buttons.append((btn_ab, "fa5s.columns", "cyan"))
            h_layout.addWidget(btn_ab)

        main_layout.addWidget(header)

        # 2. Recommendation Banner
        recom_frame = QFrame()
        recom_frame.setObjectName("recom_banner")
        r_layout = QVBoxLayout(recom_frame)
        r_layout.setContentsMargins(12, 8, 12, 8)
        
        best_filename = os.path.basename(self.group.best_track_path)
        lbl_recom = QLabel(f"RECOMENDACIÓN: Conservar '{best_filename}' — {self.group.best_track_reason}")
        lbl_recom.setWordWrap(True)
        lbl_recom.setObjectName("recom_text")
        r_layout.addWidget(lbl_recom)
        
        main_layout.addWidget(recom_frame)

        # 3. Track Columns (A vs B)
        tracks_layout = QHBoxLayout()
        tracks_layout.setSpacing(10)
        
        # Render all tracks, collapsing tracks > 4 by default
        self._extra_track_widgets = []
        for idx, track in enumerate(self.group.tracks):
            col = self._create_track_column(track, is_best=(track.filepath == self.group.best_track_path), colors=c)
            tracks_layout.addWidget(col)
            self.track_rows.append(col)
            if idx >= 4:
                col.hide()
                self._extra_track_widgets.append(col)

        main_layout.addLayout(tracks_layout)

        remaining_tracks = len(self.group.tracks) - 4
        if remaining_tracks > 0:
            self._is_expanded = False
            self.btn_toggle_tracks = QPushButton(f"Mostrar {remaining_tracks} pistas más en este grupo...")
            self.btn_toggle_tracks.setObjectName("ghost")
            self.btn_toggle_tracks.setIcon(qta.icon("fa5s.chevron-down", color=c["cyan"]))
            self.btn_toggle_tracks.setFixedHeight(30)
            self.btn_toggle_tracks.setCursor(Qt.CursorShape.PointingHandCursor)

            def _toggle():
                self._is_expanded = not self._is_expanded
                for w in self._extra_track_widgets:
                    w.setVisible(self._is_expanded)
                if self._is_expanded:
                    self.btn_toggle_tracks.setText("Mostrar menos pistas")
                    self.btn_toggle_tracks.setIcon(qta.icon("fa5s.chevron-up", color=COLORS["cyan"]))
                else:
                    self.btn_toggle_tracks.setText(f"Mostrar {remaining_tracks} pistas más en este grupo...")
                    self.btn_toggle_tracks.setIcon(qta.icon("fa5s.chevron-down", color=COLORS["cyan"]))

            self.btn_toggle_tracks.clicked.connect(_toggle)
            main_layout.addWidget(self.btn_toggle_tracks)

    def _get_badge_style(self, dtype: DuplicateType, colors: dict):
        if dtype == DuplicateType.EXACT_HASH:
            return colors["badge_exact_bg"], colors["badge_exact_text"], "DUPLICADO EXACTO"
        elif dtype == DuplicateType.EXACT_AUDIO:
            return colors["badge_exact_bg"], colors["badge_exact_text"], "AUDIO PCM EXACTO"
        elif dtype == DuplicateType.ACOUSTIC_DUPLICATE:
            return colors["badge_acoustic_bg"], colors["badge_acoustic_text"], "DUPLICADO ACÚSTICO"
        else:
            return colors["badge_possible_bg"], colors["badge_possible_text"], "POSIBLE DUPLICADO"

    @staticmethod
    def _badge_object_name(dtype: DuplicateType) -> str:
        if dtype in (DuplicateType.EXACT_HASH, DuplicateType.EXACT_AUDIO):
            return "badge_exact"
        if dtype == DuplicateType.ACOUSTIC_DUPLICATE:
            return "badge_acoustic"
        return "badge_possible"

    def _create_track_column(self, track: AudioTrack, is_best: bool, colors: dict) -> QFrame:
        col_frame = QFrame()
        col_frame.setObjectName("track_card_best" if is_best else "track_card")
        col_frame.setProperty("is_best", is_best)
        
        col_layout = QVBoxLayout(col_frame)
        col_layout.setContentsMargins(12, 12, 12, 12)
        col_layout.setSpacing(8)

        # Title
        lbl_title = QLabel(track.display_title)
        lbl_title.setObjectName("track_title")
        lbl_title.setWordWrap(True)
        col_layout.addWidget(lbl_title)

        # Path
        lbl_path = QLabel(os.path.basename(os.path.dirname(track.filepath)) + "/" + track.filename)
        lbl_path.setObjectName("path_text")
        lbl_path.setWordWrap(True)
        col_layout.addWidget(lbl_path)
        
        # Specs grid
        specs_text = (
            f"<b>Formato:</b> {track.format}<br>"
            f"<b>Bitrate:</b> {track.bitrate} kbps<br>"
            f"<b>Frecuencia:</b> {track.samplerate}Hz ({track.bit_depth}-bit)<br>"
            f"<b>Duración:</b> {track.formatted_duration}<br>"
            f"<b>Tamaño:</b> {track.formatted_size}"
        )
        from core.spectral_types import SpectralAssessment
        assessment_text = ""
        assessment_style = "assessment_muted"
        if track.spectral_assessment == SpectralAssessment.SUSPECTED_TRANSCODE or track.fake_lossless_confidence > 50.0:
            assessment_text = f"⚠️ Posible transcodificación ({track.fake_lossless_confidence:.0f}%)"
            assessment_style = "assessment_warning"
        elif track.spectral_assessment == SpectralAssessment.NO_LOSSY_EVIDENCE:
            assessment_text = "✓ Sin evidencia lossy detectada"
            assessment_style = "assessment_success"
        elif track.is_lossless:
            assessment_text = f"Contenedor lossless ({track.format}); análisis no concluyente"
            
        lbl_specs = QLabel(specs_text)
        lbl_specs.setObjectName("specs_text")
        lbl_specs.setWordWrap(True)
        col_layout.addWidget(lbl_specs)

        if assessment_text:
            lbl_assessment = QLabel(assessment_text)
            lbl_assessment.setObjectName(assessment_style)
            lbl_assessment.setWordWrap(True)
            col_layout.addWidget(lbl_assessment)
        
        col_layout.addStretch()

        # Controls
        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        btn_play = QPushButton("")
        btn_play.setObjectName("tool_btn")
        btn_play.setIcon(qta.icon("fa5s.play", color=colors["text_main"]))
        btn_play.setToolTip("Escuchar")
        btn_play.setFixedSize(32, 32)
        btn_play.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_play.clicked.connect(lambda checked, p=track.filepath: self._handle_play(p))
        controls_layout.addWidget(btn_play)
        
        self._track_widgets[track.filepath] = {"row": col_frame, "btn": btn_play}

        btn_folder = QPushButton("")
        btn_folder.setObjectName("tool_btn")
        btn_folder.setIcon(qta.icon("fa5s.external-link-alt", color=colors["text_main"]))
        btn_folder.setToolTip("Abrir ubicación")
        btn_folder.setFixedSize(32, 32)
        btn_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_folder.clicked.connect(lambda checked, p=track.filepath, r=col_frame, b=btn_folder: self._handle_open_folder(p, r, b))
        controls_layout.addWidget(btn_folder)
        self._theme_icon_buttons.extend([
            (btn_play, "fa5s.play", "text_main"),
            (btn_folder, "fa5s.external-link-alt", "text_main"),
        ])
        controls_layout.addStretch()

        col_layout.addLayout(controls_layout)

        # Action Button
        btn_action = QPushButton(
            "CONSERVAR" if track.action == FileAction.KEEP else ("ELIMINAR" if track.action == FileAction.DELETE else "REVISAR")
        )
        if track.action == FileAction.KEEP:
            btn_action.setObjectName("action_keep")
        elif track.action == FileAction.DELETE:
            btn_action.setObjectName("action_delete")
        else:
            btn_action.setObjectName("action_review")
            
        btn_action.setFixedHeight(32)
        btn_action.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_action_style(btn_action)
        btn_action.clicked.connect(lambda checked, t=track, btn=btn_action: self._toggle_track_action(t, btn))
        col_layout.addWidget(btn_action)

        return col_frame

    def _reset_all_rows_styling(self):
        for row in self.track_rows:
            self._reset_single_row_styling(row)

    def _reset_single_row_styling(self, row_frame: QFrame):
        is_best = row_frame.property("is_best") is True
        row_frame.setObjectName("track_card_best" if is_best else "track_card")
        row_frame.style().unpolish(row_frame)
        row_frame.style().polish(row_frame)

    def _on_playback_changed(self, filepath: str, is_playing: bool):
        if filepath in self._track_widgets:
            widgets = self._track_widgets[filepath]
            row_frame = widgets["row"]
            btn_play = widgets["btn"]
            c = get_theme_colors(get_current_theme())
            
            if is_playing:
                row_frame.setObjectName("track_card_playing")
                row_frame.style().unpolish(row_frame)
                row_frame.style().polish(row_frame)
                btn_play.setText(" Reproduciendo...")
                btn_play.setIcon(qta.icon("fa5s.volume-up", color=c["accent"]))
            else:
                self._reset_single_row_styling(row_frame)
                btn_play.setText("")
                btn_play.setIcon(qta.icon("fa5s.play", color=c["text_main"]))

    def _handle_play(self, filepath: str):
        self.player.play(filepath)

    def _handle_open_folder(self, filepath: str, row_frame: QFrame, btn_folder: QPushButton):
        open_file_in_explorer(filepath)
        self._reset_all_rows_styling()
        row_frame.setObjectName("track_card_best")
        row_frame.style().unpolish(row_frame)
        row_frame.style().polish(row_frame)
        
        c = get_theme_colors(get_current_theme())
        original_text = btn_folder.text()
        btn_folder.setText(" Abierto")
        btn_folder.setIcon(qta.icon("fa5s.check", color=c["cyan"]))
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: btn_folder.setText(original_text))
        QTimer.singleShot(2000, lambda: btn_folder.setIcon(qta.icon("fa5s.external-link-alt", color=COLORS["text_main"])))
        QTimer.singleShot(2000, lambda: self._reset_single_row_styling(row_frame))

    def _toggle_track_action(self, track: AudioTrack, btn: QPushButton):
        if track.action == FileAction.KEEP or track.action == FileAction.UNSET:
            track.action = FileAction.DELETE
            btn.setText("ELIMINAR")
            btn.setObjectName("action_delete")
        else:
            track.action = FileAction.KEEP
            btn.setText("CONSERVAR")
            btn.setObjectName("action_keep")

        self._apply_action_style(btn)

        self.group.recalculate_space_saving()
        if self.on_action_changed:
            self.on_action_changed(self.group)

    def refresh_theme(self):
        """Refresh only icons and explicit action styles after the global QSS update."""
        for button, icon_name, color_key in self._theme_icon_buttons:
            if button.objectName() == "tool_btn" and "Reproduciendo" in button.text():
                button.setIcon(qta.icon("fa5s.volume-up", color=COLORS["accent"]))
            else:
                button.setIcon(qta.icon(icon_name, color=COLORS[color_key]))
        for button in self.findChildren(QPushButton):
            if button.objectName() in ("action_keep", "action_delete", "action_review"):
                self._apply_action_style(button)

    @staticmethod
    def _apply_action_style(button: QPushButton):
        """Keep action backgrounds and text readable throughout a theme change."""
        name = button.objectName()
        if name == "action_keep":
            bg, hover, fg = COLORS["success"], COLORS["success_hover"], "#FFFFFF"
        elif name == "action_delete":
            bg, hover, fg = COLORS["danger"], COLORS["danger_hover"], "#FFFFFF"
        else:
            bg, hover, fg = COLORS["cyan"], COLORS["primary_hover"], COLORS["primary_text"]
        button.setStyleSheet(
            f"QPushButton {{ background-color: {bg}; color: {fg}; border: none; "
            "border-radius: 6px; font-weight: 700; padding: 6px 14px; }"
            f"QPushButton:hover {{ background-color: {hover}; }}"
        )

    def _open_ab_comparison(self):
        if len(self.group.tracks) >= 2:
            dlg = ABComparisonDialog(
                track_a=self.group.tracks[0],
                track_b=self.group.tracks[1],
                best_path=self.group.best_track_path,
                parent=self.window()
            )
            dlg.exec()
