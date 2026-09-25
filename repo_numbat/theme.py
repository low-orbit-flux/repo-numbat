"""Dark olive theme, sampled from the reference screenshot (RPCS3-style)."""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

C = {
    "window":   "#3b4438",
    "toolbar":  "#475040",
    "panel":    "#31382c",
    "panel_alt": "#37402f",
    "header":   "#4c5945",
    "log":      "#262924",
    "border":   "#232823",
    "text":     "#d6ddd0",
    "muted":    "#a3b0a7",
    "disabled": "#6f7a68",
    "select":   "#5c6b52",
    "hover":    "#4a5544",
    "ok":       "#1fbb64",
    "warn":     "#fdb527",
    "bad":      "#e5484d",
    "none":     "#7c877a",
}

STYLESHEET = f"""
* {{ font-size: 10pt; }}
QMainWindow, QWidget {{ background: {C['window']}; color: {C['text']}; }}
QMenuBar {{ background: {C['window']}; color: {C['text']}; padding: 1px; }}
QMenuBar::item {{ padding: 4px 8px; background: transparent; }}
QMenuBar::item:selected {{ background: {C['select']}; }}
QMenu {{ background: {C['panel']}; color: {C['text']}; border: 1px solid {C['border']}; }}
QMenu::item {{ padding: 5px 24px 5px 20px; }}
QMenu::item:selected {{ background: {C['select']}; }}
QMenu::item:disabled {{ color: {C['disabled']}; }}
QMenu::separator {{ height: 1px; background: {C['border']}; margin: 4px 6px; }}
QMenu::indicator {{ width: 12px; height: 12px; margin-left: 4px; }}

QToolBar {{ background: {C['toolbar']}; border: none; border-bottom: 1px solid {C['border']}; padding: 2px 4px; spacing: 2px; }}
QToolBar > QWidget {{ background: transparent; }}
QToolBar QLineEdit {{ background: {C['panel']}; }}
QToolBar::separator {{ width: 1px; background: {C['border']}; margin: 6px 6px; }}
QToolButton {{ background: transparent; color: {C['text']}; border: 1px solid transparent; border-radius: 3px; padding: 3px 6px; }}
QToolButton:hover {{ background: {C['hover']}; border-color: {C['border']}; }}
QToolButton:pressed, QToolButton:checked {{ background: {C['panel']}; border-color: {C['border']}; }}
QToolButton:disabled {{ color: {C['disabled']}; }}

QLineEdit {{ background: {C['panel']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 2px; padding: 5px 8px; selection-background-color: {C['select']}; }}
QLineEdit:focus {{ border-color: {C['header']}; }}
QComboBox, QSpinBox {{ background: {C['panel']}; color: {C['text']}; border: 1px solid {C['border']}; padding: 3px 6px; }}
QComboBox QAbstractItemView {{ background: {C['panel']}; color: {C['text']}; selection-background-color: {C['select']}; }}

QHeaderView {{ background: {C['header']}; }}
QHeaderView::section {{ background: {C['header']}; color: {C['text']}; padding: 4px 6px; border: none; border-right: 1px solid {C['border']}; border-bottom: 1px solid {C['border']}; }}
QHeaderView::section:hover {{ background: {C['hover']}; }}
QHeaderView::down-arrow, QHeaderView::up-arrow {{ width: 10px; height: 10px; }}
QTableView, QTreeView, QListView {{
    background: {C['panel']}; alternate-background-color: {C['panel_alt']}; color: {C['text']};
    border: none; gridline-color: {C['panel']}; selection-background-color: {C['select']}; selection-color: {C['text']};
    outline: none; }}
QTableView::item {{ padding: 2px 6px; border: none; }}
QTableView::item:selected {{ background: {C['select']}; }}
QTableView::item:hover {{ background: {C['hover']}; }}
QTableCornerButton::section {{ background: {C['header']}; border: none; }}

QTabWidget::pane {{ border: none; border-top: 1px solid {C['border']}; background: {C['log']}; }}
QTabBar {{ background: {C['window']}; }}
QTabBar::tab {{ background: {C['window']}; color: {C['muted']}; padding: 4px 18px; border: 1px solid {C['border']}; border-bottom: none; }}
QTabBar::tab:selected {{ background: {C['log']}; color: {C['text']}; }}
QTabBar::tab:hover {{ background: {C['hover']}; }}
QPlainTextEdit, QTextEdit {{ background: {C['log']}; color: {C['muted']}; border: none; selection-background-color: {C['select']}; }}

QSplitter::handle {{ background: {C['window']}; }}
QSplitter::handle:vertical {{ height: 5px; }}
QSplitter::handle:horizontal {{ width: 5px; }}

QStatusBar {{ background: {C['window']}; color: {C['muted']}; border-top: 1px solid {C['border']}; }}
QStatusBar::item {{ border: none; }}
QProgressBar {{ background: {C['panel']}; border: 1px solid {C['border']}; border-radius: 2px; text-align: center; color: {C['text']}; max-height: 14px; }}
QProgressBar::chunk {{ background: {C['ok']}; }}

QScrollBar:vertical {{ background: {C['panel']}; width: 12px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {C['header']}; min-height: 24px; border-radius: 3px; margin: 2px; }}
QScrollBar::handle:vertical:hover {{ background: {C['select']}; }}
QScrollBar:horizontal {{ background: {C['panel']}; height: 12px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {C['header']}; min-width: 24px; border-radius: 3px; margin: 2px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QPushButton {{ background: {C['header']}; color: {C['text']}; border: 1px solid {C['border']}; border-radius: 3px; padding: 5px 14px; }}
QPushButton:hover {{ background: {C['select']}; }}
QPushButton:pressed {{ background: {C['panel']}; }}
QPushButton:default {{ border-color: {C['ok']}; }}
QCheckBox, QLabel {{ color: {C['text']}; background: transparent; }}
QCheckBox::indicator {{ width: 14px; height: 14px; border: 1px solid {C['border']}; background: {C['panel']}; }}
QCheckBox::indicator:checked {{ background: {C['ok']}; }}
QDialog {{ background: {C['window']}; }}
QToolTip {{ background: {C['panel']}; color: {C['text']}; border: 1px solid {C['border']}; padding: 4px; }}
QMessageBox {{ background: {C['window']}; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")  # consistent base on every platform
    pal = QPalette()
    roles = {
        QPalette.ColorRole.Window: C["window"], QPalette.ColorRole.WindowText: C["text"],
        QPalette.ColorRole.Base: C["panel"], QPalette.ColorRole.AlternateBase: C["panel_alt"],
        QPalette.ColorRole.Text: C["text"], QPalette.ColorRole.Button: C["header"],
        QPalette.ColorRole.ButtonText: C["text"], QPalette.ColorRole.Highlight: C["select"],
        QPalette.ColorRole.HighlightedText: C["text"], QPalette.ColorRole.ToolTipBase: C["panel"],
        QPalette.ColorRole.ToolTipText: C["text"], QPalette.ColorRole.PlaceholderText: C["disabled"],
        QPalette.ColorRole.Link: C["ok"],
    }
    for role, color in roles.items():
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(C["disabled"]))
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(C["disabled"]))
    app.setPalette(pal)
    app.setStyleSheet(STYLESHEET)
