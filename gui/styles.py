"""
Modern UI Design System — Audio Cleaner
Supports dynamic theming with:
- Dark Mode (Figma Cyber 4-tier dark palette + Neon Cyan accent)
- Light Mode (Clean Slate / Sky palette with high contrast and legibility)
"""

import os
import json
import logging
from typing import Optional, Union, Dict, Any

logger = logging.getLogger(__name__)

# ─── Master Palettes ──────────────────────────────────────────────────────────

THEME_DARK: Dict[str, str] = {
    # Background tiers
    "bg_darkest":   "#0D0F12",   # Window / deepest background
    "bg_sidebar":   "#14161A",   # Left sidebar
    "bg_main":      "#1C1F25",   # Main panel background
    "bg_card":      "#252830",   # Cards / floating surfaces
    "bg_hover":     "#2E3340",   # Hover state for list items
    "bg_input":     "#0D0F12",   # Inputs, spinboxes, line-edits

    # Legacy aliases (keep for compatibility)
    "bg_dark":          "#0D0F12",
    "bg_card_highlight": "#2E3340",
    "bg_surface":       "#1E222A",
    "border":           "#2E3340",

    # Accent
    "cyan":         "#00E5FF",
    "cyan_dim":     "#0099B8",
    "cyan_bg":      "#003340",

    # Primary
    "primary":       "#00E5FF",
    "primary_hover": "#00B8CC",
    "primary_text":  "#000000",

    # Accent purple
    "accent":       "#7C3AED",
    "accent_hover": "#6D28D9",

    # Semantic
    "success":        "#22C55E",   # MEJOR CALIDAD
    "success_bg":     "#052E16",
    "success_hover":  "#16A34A",
    "warning":        "#F97316",   # FAKE LOSSLESS / ADVERTENCIA
    "warning_bg":     "#431407",
    "warning_hover":  "#EA580C",
    "danger":         "#EF4444",   # TRANSCODIFICADO / ELIMINAR PERMANENTE
    "danger_bg":      "#450A0A",
    "danger_hover":   "#DC2626",
    "info":           "#3B82F6",   # ACÚSTICO / INFO
    "info_bg":        "#1E3A8A",
    "purple":         "#A855F7",   # POSIBLE
    "purple_bg":      "#3B0764",

    # Text
    "text_main":  "#F3F4F6",
    "text_muted": "#9CA3AF",
    "text_dim":   "#6B7280",

    # Badge colors
    "badge_exact_bg":     "#003340",
    "badge_exact_text":   "#00E5FF",
    "badge_acoustic_bg":  "#1E3A8A",
    "badge_acoustic_text": "#93C5FD",
    "badge_possible_bg":  "#3B0764",
    "badge_possible_text": "#D8B4FE",
    "keep_bg":     "#052E16",
    "keep_border": "#22C55E",
    "delete_bg":   "#450A0A",
    "delete_border": "#EF4444",
}

THEME_LIGHT: Dict[str, str] = {
    # Background tiers
    "bg_darkest":   "#F1F5F9",   # Window / base background (Slate 100)
    "bg_sidebar":   "#F1F5F9",   # Left sidebar (Slate 100)
    "bg_main":      "#F1F5F9",   # Main panel background (Slate 100 canvas)
    "bg_card":      "#FFFFFF",   # Cards / floating surfaces (Pure white)
    "bg_hover":     "#E2E8F0",   # Hover state for list items (Slate 200)
    "bg_input":     "#FFFFFF",   # Clean white inputs

    # Legacy aliases
    "bg_dark":          "#F1F5F9",
    "bg_card_highlight": "#E2E8F0", # Slate 200 - Soft neutral surface
    "bg_surface":       "#FFFFFF",
    "border":           "#CBD5E1",   # Slate 300 - Clean, crisp, visible borders

    # Accent (Sky 600 - vivid and readable on light backgrounds)
    "cyan":         "#0284C7",
    "cyan_dim":     "#0369A1",
    "cyan_bg":      "#E0F2FE",   # Sky 100 soft background

    # Primary
    "primary":       "#0284C7",
    "primary_hover": "#0369A1",
    "primary_text":  "#FFFFFF",

    # Accent purple
    "accent":       "#7C3AED",
    "accent_hover": "#6D28D9",

    # Semantic
    "success":        "#16A34A",   # Green 600
    "success_bg":     "#DCFCE7",   # Green 100
    "success_hover":  "#15803D",
    "warning":        "#B45309",   # Amber 700 - Deep and high contrast on light
    "warning_bg":     "#FEF3C7",   # Amber 100
    "warning_hover":  "#92400E",
    "danger":         "#DC2626",   # Red 600
    "danger_bg":      "#FEE2E2",   # Red 100
    "danger_hover":   "#B91C1C",
    "info":           "#2563EB",   # Blue 600
    "info_bg":        "#DBEAFE",   # Blue 100
    "purple":         "#9333EA",
    "purple_bg":      "#F3E8FF",

    # Text
    "text_main":  "#0F172A",   # Slate 900 - high contrast dark text
    "text_muted": "#334155",   # Slate 700 - readable secondary labels
    "text_dim":   "#64748B",   # Slate 500 - metadata

    # Badge colors
    "badge_exact_bg":     "#E0F2FE",
    "badge_exact_text":   "#0284C7",
    "badge_acoustic_bg":  "#DBEAFE",
    "badge_acoustic_text": "#2563EB",
    "badge_possible_bg":  "#F3E8FF",
    "badge_possible_text": "#9333EA",
    "keep_bg":     "#DCFCE7",
    "keep_border": "#16A34A",
    "delete_bg":   "#FEE2E2",
    "delete_border": "#DC2626",
}


# ─── Settings Persistence ───────────────────────────────────────────────────

def get_ui_settings_path() -> str:
    """Returns canonical OS path for UI settings JSON."""
    app_data = os.getenv("APPDATA")
    if app_data:
        base_dir = os.path.join(app_data, "AudioDuplicateDetector")
    else:
        base_dir = os.path.join(os.path.expanduser("~"), ".audioduplicatedetector")
    return os.path.join(base_dir, "ui_settings.json")


def load_theme_preference() -> str:
    """Loads saved theme preference ('dark' or 'light'). Defaults to 'dark'."""
    path = get_ui_settings_path()
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                theme = data.get("theme", "dark").lower()
                if theme in ("dark", "light"):
                    return theme
        except Exception as e:
            logger.debug("Could not read ui_settings.json: %s", e)
    return "dark"


def save_theme_preference(theme_name: str):
    """Persists theme preference to disk atomically."""
    path = get_ui_settings_path()
    try:
        parent_dir = os.path.dirname(path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        data = {}
        if os.path.isfile(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["theme"] = theme_name if theme_name in ("dark", "light") else "dark"
        tmp = f"{path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception as e:
        logger.warning("Could not save theme preference: %s", e)


# ─── Dynamic QSS Generator ──────────────────────────────────────────────────

def get_theme_colors(theme_name: str = "dark") -> Dict[str, str]:
    """Returns palette dictionary for given theme name."""
    return dict(THEME_LIGHT if theme_name == "light" else THEME_DARK)


def get_qss(theme_or_colors: Union[str, Dict[str, str]] = "dark") -> str:
    """Generates the full application QSS stylesheet for the specified theme or colors."""
    if isinstance(theme_or_colors, str):
        c = THEME_LIGHT if theme_or_colors == "light" else THEME_DARK
    else:
        c = theme_or_colors

    return f"""
/* ── Window base ─────────────────────────────────────────────── */
QMainWindow, QWidget#main_window {{
    background-color: {c['bg_darkest']};
    color: {c['text_main']};
    font-family: 'Segoe UI', 'Inter', sans-serif;
    font-size: 11pt;
}}
QWidget {{
    font-family: 'Segoe UI', 'Inter', sans-serif;
    color: {c['text_main']};
}}

/* ── Sidebar ─────────────────────────────────────────────────── */
QWidget#sidebar {{
    background-color: {c['bg_sidebar']};
    border-right: 1px solid {c['border']};
}}

/* ── Main panel ──────────────────────────────────────────────── */
QWidget#main_panel {{
    background-color: {c['bg_main']};
}}

/* ── Scroll Areas ────────────────────────────────────────────── */
QScrollArea {{
    border: none;
    background-color: transparent;
}}
QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}
QWidget#results_content {{
    background-color: palette(window);
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {c['bg_card_highlight']};
    min-height: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {c['bg_hover']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* ── Generic Frames ──────────────────────────────────────────── */
QFrame {{
    background-color: transparent;
    border-radius: 8px;
}}
QFrame#card {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 8px;
}}
DuplicateGroupCard, QFrame#DuplicateGroupCard {{
    background-color: {c['bg_card']};
    border: 1px solid {c['border']};
    border-radius: 10px;
}}
QFrame#stat_card_large {{
    background-color: {c['cyan_bg']};
    border: 1px solid {c['cyan_dim']};
    border-radius: 8px;
}}
QFrame#recom_banner {{
    background-color: {c['warning_bg']};
    border: 1px solid {c['warning']};
    border-radius: 6px;
}}
QLabel#recom_text {{
    color: {c['warning']};
    font-size: 9.5pt;
    font-weight: 600;
    border: none;
    background: transparent;
}}
QFrame#track_card {{
    background-color: {c['bg_surface']};
    border: 1px solid {c['border']};
    border-radius: 8px;
}}
QFrame#track_card_best {{
    background-color: {c['bg_surface']};
    border: 2px solid {c['cyan']};
    border-radius: 8px;
}}
QFrame#track_card_playing {{
    background-color: {c['bg_surface']};
    border: 2px solid {c['accent']};
    border-radius: 8px;
}}
QLabel#track_title {{
    font-weight: bold;
    font-size: 10pt;
    color: {c['text_main']};
    border: none;
    background: transparent;
}}
QLabel#path_text {{
    font-size: 9pt;
    color: {c['text_muted']};
    border: none;
    background: transparent;
}}
QLabel#specs_text {{
    color: {c['text_main']};
    font-size: 9pt;
    border: none;
    background: transparent;
}}
QLabel#similarity_label {{
    color: {c['accent']};
    font-weight: bold;
    font-size: 9pt;
    border: none;
    background: transparent;
}}
QLabel#savings_label {{
    color: {c['success']};
    font-weight: bold;
    font-size: 9pt;
    border: none;
    background: transparent;
}}
QLabel#badge_exact {{
    background-color: {c['badge_exact_bg']};
    color: {c['badge_exact_text']};
    font-weight: 700;
    font-size: 9pt;
    border-radius: 4px;
    padding: 2px 6px;
}}
QLabel#badge_acoustic {{
    background-color: {c['badge_acoustic_bg']};
    color: {c['badge_acoustic_text']};
    font-weight: 700;
    font-size: 9pt;
    border-radius: 4px;
    padding: 2px 6px;
}}
QLabel#badge_possible {{
    background-color: {c['badge_possible_bg']};
    color: {c['badge_possible_text']};
    font-weight: 700;
    font-size: 9pt;
    border-radius: 4px;
    padding: 2px 6px;
}}
QLabel#assessment_warning {{
    color: {c['warning']};
    font-weight: 600;
}}
QLabel#assessment_success {{
    color: {c['success']};
    font-weight: 600;
}}
QLabel#assessment_muted {{
    color: {c['text_muted']};
    font-weight: 500;
}}
QFrame#transparent {{
    background-color: transparent;
    border: none;
}}

/* ── Labels ──────────────────────────────────────────────────── */
QLabel {{
    color: {c['text_main']};
    background-color: transparent;
}}
QLabel#title {{
    font-size: 16pt;
    font-weight: bold;
}}
QLabel#subtitle {{
    font-size: 13pt;
    font-weight: bold;
}}
QLabel#section_label {{
    font-size: 8pt;
    font-weight: bold;
    color: {c['text_dim']};
    letter-spacing: 1.5px;
}}
QLabel#muted {{
    color: {c['text_muted']};
}}
QLabel#dim {{
    color: {c['text_dim']};
}}
QLabel#small {{
    font-size: 9pt;
}}
QLabel#mono {{
    font-family: 'JetBrains Mono', 'Consolas', 'Courier New', monospace;
    font-size: 9pt;
    color: {c['text_muted']};
}}
QLabel#cyan {{
    color: {c['cyan']};
    font-weight: bold;
}}

/* ── Buttons ─────────────────────────────────────────────────── */
QPushButton {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
}}
QPushButton:hover {{
    background-color: {c['bg_hover']};
    border-color: {c['text_dim']};
}}
QPushButton:pressed {{
    background-color: {c['bg_sidebar']};
}}
QPushButton:disabled {{
    opacity: 0.45;
}}

QPushButton#primary {{
    background-color: {c['cyan']};
    color: {c['primary_text']};
    border: none;
    font-weight: 700;
}}
QPushButton#primary:hover {{
    background-color: {c['primary_hover']};
}}

QPushButton#success {{
    background-color: {c['success']};
    color: white;
    border: none;
}}
QPushButton#success:hover {{
    background-color: {c['success_hover']};
}}

QPushButton#danger {{
    background-color: {c['danger']};
    color: white;
    border: none;
}}
QPushButton#danger:hover {{
    background-color: {c['danger_hover']};
}}

QPushButton#warning {{
    background-color: transparent;
    color: {c['text_main']};
    border: 1px solid {c['border']};
}}
QPushButton#warning:hover {{
    background-color: {c['bg_hover']};
}}

QPushButton#ghost {{
    background-color: transparent;
    color: {c['text_muted']};
    border: 1px solid {c['border']};
}}
QPushButton#ghost:hover {{
    color: {c['text_main']};
    background-color: {c['bg_hover']};
    border-color: {c['cyan']};
}}

QPushButton#accent {{
    background-color: {c['accent']};
    color: #FFFFFF;
    border: none;
    font-weight: 700;
    border-radius: 6px;
    padding: 6px 14px;
}}
QPushButton#accent:hover {{
    background-color: {c['accent_hover']};
}}

QPushButton#action_keep, QPushButton#success {{
    background-color: {c['success']};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    font-weight: 700;
    padding: 6px 14px;
}}
QPushButton#action_keep:hover, QPushButton#success:hover {{
    background-color: {c['success_hover']};
}}

QPushButton#action_delete, QPushButton#danger {{
    background-color: {c['danger']};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    font-weight: 700;
    padding: 6px 14px;
}}
QPushButton#action_delete:hover, QPushButton#danger:hover {{
    background-color: {c['danger_hover']};
}}

QPushButton#action_review {{
    background-color: {c['cyan']};
    color: {c['primary_text']};
    border: none;
    border-radius: 6px;
    font-weight: 700;
    padding: 6px 14px;
}}
QPushButton#action_review:hover {{
    background-color: {c['primary_hover']};
}}

QPushButton#tool_btn {{
    background-color: {c['bg_card_highlight']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 0px;
}}
QPushButton#tool_btn:hover {{
    background-color: {c['bg_hover']};
    border-color: {c['cyan']};
}}

QPushButton#filter_tab {{
    background-color: {c['bg_card']};
    color: {c['text_muted']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 6px 14px;
    font-weight: 600;
}}
QPushButton#filter_tab:hover {{
    background-color: {c['bg_hover']};
    color: {c['text_main']};
}}
QPushButton#filter_tab:checked {{
    background-color: {c['cyan_bg']};
    color: {c['cyan']};
    border: 1px solid {c['cyan']};
    font-weight: 700;
}}

/* Sidebar nav buttons */
QPushButton#nav_item {{
    background-color: transparent;
    color: {c['text_muted']};
    border: none;
    border-radius: 6px;
    text-align: left;
    padding: 10px 12px;
    font-weight: 500;
}}
QPushButton#nav_item:hover {{
    background-color: {c['bg_hover']};
    color: {c['text_main']};
}}
QPushButton#nav_item:checked, QPushButton#nav_item_active {{
    background-color: {c['bg_card_highlight']};
    color: {c['cyan']};
    border: none;
    border-left: 3px solid {c['cyan']};
    border-radius: 0px 6px 6px 0px;
    text-align: left;
    padding: 10px 12px 10px 9px;
    font-weight: 700;
}}

/* ── Progress Bar ────────────────────────────────────────────── */
QProgressBar {{
    background-color: {c['bg_card_highlight']};
    border: none;
    border-radius: 3px;
    height: 6px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{
    background-color: {c['cyan']};
    border-radius: 3px;
}}

/* ── Line Edit / Search ──────────────────────────────────────── */
QLineEdit {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 7px 12px;
    font-family: 'Segoe UI';
}}
QLineEdit:focus {{
    border: 1px solid {c['cyan']};
}}

/* ── Combo Box ───────────────────────────────────────────────── */
QComboBox {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 6px 10px;
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox QAbstractItemView {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    selection-background-color: {c['cyan_bg']};
    selection-color: {c['cyan']};
    border: 1px solid {c['border']};
    outline: none;
}}

/* ── Tab Bar (filter tabs) ───────────────────────────────────── */
QTabBar::tab {{
    background: transparent;
    color: {c['text_muted']};
    padding: 7px 18px;
    border-bottom: 2px solid transparent;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    color: {c['cyan']};
    border-bottom: 2px solid {c['cyan']};
}}
QTabBar::tab:hover {{
    color: {c['text_main']};
}}
QTabWidget::pane {{
    border: none;
}}

/* ── Table Widget ─────────────────────────────────────────────── */
QTableWidget, QTableView {{
    background-color: {c['bg_main']};
    color: {c['text_main']};
    gridline-color: {c['border']};
    border: 1px solid {c['border']};
    border-radius: 8px;
    selection-background-color: {c['cyan_bg']};
    selection-color: {c['text_main']};
    font-size: 10pt;
}}
QTableWidget::item, QTableView::item {{
    padding: 6px 10px;
    border-bottom: 1px solid {c['border']};
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {c['cyan_bg']};
    color: {c['cyan']};
}}
QHeaderView::section {{
    background-color: {c['bg_sidebar']};
    color: {c['text_muted']};
    padding: 8px 10px;
    font-weight: 700;
    font-size: 8.5pt;
    border: none;
    border-bottom: 2px solid {c['border']};
    letter-spacing: 1px;
}}

/* ── Checkbox & Radio ────────────────────────────────────────── */
QCheckBox {{
    color: {c['text_main']};
    spacing: 8px;
    font-size: 10pt;
}}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid {c['border']};
    background-color: {c['bg_input']};
}}
QCheckBox::indicator:hover {{
    border-color: {c['cyan_dim']};
}}
QCheckBox::indicator:checked {{
    background-color: {c['cyan']};
    border-color: {c['cyan']};
}}

/* ── SpinBox & Slider ────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox {{
    background-color: {c['bg_input']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 6px;
    padding: 5px 10px;
}}
QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {c['cyan']};
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: {c['bg_card_highlight']};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {c['cyan']};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {c['cyan']};
    border: 2px solid #FFFFFF;
    width: 16px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 8px;
}}
QSlider::handle:horizontal:hover {{
    background: #FFFFFF;
}}

/* ── Tooltips ────────────────────────────────────────────────── */
QToolTip {{
    background-color: {c['bg_card']};
    color: {c['text_main']};
    border: 1px solid {c['border']};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ── Message Box ─────────────────────────────────────────────── */
QMessageBox {{
    background-color: {c['bg_card']};
}}
QMessageBox QLabel {{
    color: {c['text_main']};
}}
"""


# ─── Runtime State & Management ─────────────────────────────────────────────

CURRENT_THEME: str = load_theme_preference()
COLORS: Dict[str, str] = dict(THEME_LIGHT if CURRENT_THEME == "light" else THEME_DARK)

# Qt reparses and repolishes every widget whenever QApplication.setStyleSheet
# receives a different string. Using QPalette roles makes the large stylesheet
# theme-neutral, so a switch only changes lightweight palette brushes.
PALETTE_QSS_COLORS: Dict[str, str] = {
    "bg_darkest": "palette(window)",
    # Window is reliably propagated by every supported Qt 6 style. The small
    # dark-theme sidebar tier difference is applied directly by Sidebar.
    "bg_sidebar": "palette(window)",
    "bg_main": "palette(window)",
    "bg_card": "palette(button)",
    "bg_hover": "palette(midlight)",
    "bg_input": "palette(base)",
    "bg_dark": "palette(window)",
    "bg_card_highlight": "palette(midlight)",
    "bg_surface": "palette(alternate-base)",
    "border": "palette(mid)",
    "cyan": "palette(highlight)",
    "cyan_dim": "palette(link)",
    "cyan_bg": "palette(light)",
    "primary": "palette(highlight)",
    "primary_hover": "palette(link)",
    "primary_text": "palette(highlighted-text)",
    "accent": "palette(link-visited)",
    "accent_hover": "palette(link-visited)",
    "success": "palette(accent)",
    "success_bg": "rgba(34, 197, 94, 0.14)",
    "success_hover": "palette(accent)",
    "warning": "palette(shadow)",
    "warning_bg": "rgba(249, 115, 22, 0.12)",
    "warning_hover": "palette(shadow)",
    "danger": "palette(bright-text)",
    "danger_bg": "rgba(239, 68, 68, 0.13)",
    "danger_hover": "palette(bright-text)",
    "info": "palette(link)",
    "info_bg": "rgba(59, 130, 246, 0.14)",
    "purple": "palette(link-visited)",
    "purple_bg": "rgba(168, 85, 247, 0.14)",
    "text_main": "palette(window-text)",
    "text_muted": "palette(placeholder-text)",
    "text_dim": "palette(placeholder-text)",
    "badge_exact_bg": "palette(light)",
    "badge_exact_text": "palette(highlight)",
    "badge_acoustic_bg": "rgba(59, 130, 246, 0.14)",
    "badge_acoustic_text": "palette(link)",
    "badge_possible_bg": "rgba(168, 85, 247, 0.14)",
    "badge_possible_text": "palette(link-visited)",
    "keep_bg": "rgba(34, 197, 94, 0.14)",
    "keep_border": "palette(accent)",
    "delete_bg": "rgba(239, 68, 68, 0.13)",
    "delete_border": "palette(bright-text)",
}
GLOBAL_QSS: str = get_qss(PALETTE_QSS_COLORS)


def get_current_theme() -> str:
    """Returns the name of the currently active theme ('dark' or 'light')."""
    global CURRENT_THEME
    return CURRENT_THEME


def get_qt_palette(theme_name: str):
    """Build a QPalette whose roles back the theme-neutral global QSS."""
    from PyQt6.QtGui import QColor, QPalette

    colors = THEME_LIGHT if theme_name == "light" else THEME_DARK
    palette = QPalette()
    role_colors = {
        QPalette.ColorRole.Window: colors["bg_darkest"],
        QPalette.ColorRole.Dark: colors["bg_sidebar"],
        QPalette.ColorRole.Button: colors["bg_card"],
        QPalette.ColorRole.Midlight: colors["bg_hover"],
        QPalette.ColorRole.Base: colors["bg_input"],
        QPalette.ColorRole.AlternateBase: colors["bg_surface"],
        QPalette.ColorRole.Mid: colors["border"],
        QPalette.ColorRole.WindowText: colors["text_main"],
        QPalette.ColorRole.Text: colors["text_main"],
        QPalette.ColorRole.ButtonText: colors["text_main"],
        QPalette.ColorRole.PlaceholderText: colors["text_muted"],
        QPalette.ColorRole.Highlight: colors["cyan"],
        QPalette.ColorRole.HighlightedText: colors["primary_text"],
        QPalette.ColorRole.Link: colors["cyan_dim"],
        QPalette.ColorRole.LinkVisited: colors["accent"],
        QPalette.ColorRole.Accent: colors["success"],
        QPalette.ColorRole.Shadow: colors["warning"],
        QPalette.ColorRole.BrightText: colors["danger"],
        QPalette.ColorRole.Light: colors["cyan_bg"],
        QPalette.ColorRole.ToolTipBase: colors["bg_card"],
        QPalette.ColorRole.ToolTipText: colors["text_main"],
    }
    for role, color in role_colors.items():
        palette.setColor(role, QColor(color))
    return palette


def apply_theme(theme_name: str, app=None) -> str:
    """
    Applies the requested theme ('dark' or 'light'):
    - Updates CURRENT_THEME
    - Mutates COLORS in-place so existing modules see updated values
    - Re-generates GLOBAL_QSS and updates QApplication stylesheet if available
    - Persists selection to disk
    Returns the new QSS stylesheet string.
    """
    global CURRENT_THEME, GLOBAL_QSS
    if theme_name not in ("dark", "light"):
        theme_name = "dark"

    previous_theme = CURRENT_THEME
    CURRENT_THEME = theme_name
    palette = THEME_LIGHT if theme_name == "light" else THEME_DARK
    COLORS.clear()
    COLORS.update(palette)

    qss = GLOBAL_QSS
    GLOBAL_QSS = qss

    if app is None:
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance()
        except Exception:
            app = None

    # setStyleSheet reparses and repolishes the complete widget tree. Settings
    # can submit the already active theme, so avoid an expensive no-op.
    if app:
        if app.styleSheet() != qss:
            app.setStyleSheet(qss)
        if hasattr(app, "setPalette"):
            app.setPalette(get_qt_palette(theme_name))

    if previous_theme != theme_name:
        save_theme_preference(theme_name)
    return qss
