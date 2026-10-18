"""Colors and the global stylesheet. Change the look of the whole app here."""

BG = "#0D1016"
PANEL = "#141821"
PANEL_2 = "#1A1F2B"
BORDER = "#252B38"
ROW_LINE = "#1D222D"
TEXT = "#E7EAF0"
MUTED = "#8A93A6"
ACCENT = "#5B8CFF"
OK = "#3DD68C"
WARN = "#F4B942"
BAD = "#F0677A"


def stylesheet():
    return f"""
* {{ font-family: "Segoe UI", "Inter", "Helvetica Neue", Arial, sans-serif; font-size: 13px; color: {TEXT}; }}
QMainWindow, QDialog, QWidget#root, QScrollArea, QScrollArea > QWidget > QWidget {{ background: {BG}; }}
QWidget#sidebar {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
QLabel {{ background: transparent; }}
QLabel#brand {{ font-size: 17px; font-weight: 700; }}
QLabel#brandSub {{ color: {MUTED}; font-size: 12px; }}
QLabel#title {{ font-size: 24px; font-weight: 600; }}
QLabel#subtitle {{ color: {MUTED}; font-size: 13px; }}
QLabel#section {{ font-size: 14px; font-weight: 600; }}
QLabel#caption {{ color: {MUTED}; font-size: 12px; }}
QLabel#cardTitle {{ color: {MUTED}; font-size: 11px; font-weight: 600; }}
QLabel#cardValue {{ font-size: 28px; font-weight: 600; }}
QLabel#bigNumber {{ font-size: 44px; font-weight: 700; }}

QPushButton {{ background: {PANEL_2}; border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 16px; }}
QPushButton:hover {{ background: #212838; border-color: #36405A; }}
QPushButton:pressed {{ background: #181D28; }}
QPushButton:disabled {{ color: #566074; background: {PANEL}; }}
QPushButton#primary {{ background: {ACCENT}; border: 1px solid {ACCENT}; color: #FFFFFF; font-weight: 600; }}
QPushButton#primary:hover {{ background: #7AA2FF; border-color: #7AA2FF; }}
QPushButton#primary:disabled {{ background: #2A3550; border-color: #2A3550; color: #7C88A6; }}
QPushButton#danger {{ color: {BAD}; border: 1px solid rgba(240,103,122,90); background: transparent; }}
QPushButton#danger:hover {{ background: rgba(240,103,122,32); }}
QPushButton#nav {{ text-align: left; padding: 11px 16px; border: none; border-radius: 8px;
                   background: transparent; color: {MUTED}; font-size: 14px; }}
QPushButton#nav:hover {{ background: {PANEL_2}; color: {TEXT}; }}
QPushButton#nav:checked {{ background: rgba(91,140,255,36); color: #FFFFFF; font-weight: 600; }}

QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#divider {{ background: {BORDER}; max-height: 1px; min-height: 1px; border: none; }}

QLineEdit, QComboBox, QDateEdit {{ background: {BG}; border: 1px solid {BORDER}; border-radius: 8px;
                                   padding: 8px 12px; selection-background-color: {ACCENT}; }}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{ border-color: {ACCENT}; }}
QLineEdit:read-only {{ color: {MUTED}; }}
QComboBox::drop-down, QDateEdit::drop-down {{ border: none; width: 26px; }}
QComboBox QAbstractItemView {{ background: {PANEL_2}; border: 1px solid {BORDER}; outline: 0;
                               selection-background-color: rgba(91,140,255,60); }}
QCalendarWidget QWidget {{ background: {PANEL_2}; }}
QCalendarWidget QAbstractItemView:disabled {{ color: #4A5368; }}

QTableWidget {{ background: transparent; border: none; outline: 0; gridline-color: transparent;
                selection-background-color: rgba(91,140,255,40); }}
QTableWidget::item {{ padding: 0 12px; border-bottom: 1px solid {ROW_LINE}; }}
QTableWidget::item:selected {{ background: rgba(91,140,255,40); color: {TEXT}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{ background: transparent; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
                        padding: 10px 12px; font-size: 11px; font-weight: 600; text-align: left; }}
QTableCornerButton::section {{ background: transparent; border: none; }}

QListWidget {{ background: transparent; border: none; outline: 0; }}
QListWidget::item {{ padding: 10px 4px; border-bottom: 1px solid {ROW_LINE}; }}
QListWidget::item:selected {{ background: transparent; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #2C3445; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #3A4560; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #2C3445; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: none; width: 0; height: 0; }}

QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: #FFFFFF; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }}

QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3A4560; background: {BG}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QProgressBar {{ background: {BORDER}; border: none; border-radius: 4px; max-height: 8px; min-height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}

QStatusBar {{ background: {PANEL}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QStatusBar::item {{ border: none; }}
QToolTip {{ background: {PANEL_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 6px; }}
QMessageBox {{ background: {PANEL}; }}
QDialog {{ background: {BG}; }}
"""
