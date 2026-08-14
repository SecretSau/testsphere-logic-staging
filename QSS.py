
# ---------------------------------
# Design Tokens (Enterprise + Futuristic) Theme
# ---------------------------------
COL_BG_1 = "#1E1E2E"      # deep slate
COL_BG_2 = "#232538"      # panel bg
COL_PANEL = COL_BG_2
COL_TXT = "#E6E6E9"
COL_MUTED = "#A7A9B4"
ACCENT = "#00CFFF"        # cyber cyan
ACCENT_2 = "#9A4DFF"      # electric purple
ACCENT_HOVER = "#00BFFF" # slightly darker cyan

QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', 'Roboto', sans-serif; }}
QWidget {{ background-color: {COL_BG_1}; color: {COL_TXT}; }}

/* Top bar */
#TopBar {{ background: {COL_PANEL}; border-radius: 12px; }}
#TopBar QLabel[role="title"] {{ font-size: 16px; font-weight: 700; }}
#TopBar QLabel[role="meta"] {{ color: {COL_MUTED}; }}

/* Sidebar */
#SideBar {{ background: {COL_PANEL}; border-radius: 16px; }}
QToolButton[nav="true"] {{
  border: none; border-left: 3px solid transparent;
  margin: 2px; padding: 10px 12px; border-radius: 10px;
  color: {COL_MUTED};
}}
QToolButton[nav="true"]:hover {{ background: rgba(255,255,255,0.04); color: {COL_TXT}; }}
QToolButton[active="true"] {{
  color: {COL_TXT};
  background: rgba(0,0,0,0.10);
  border-left-color: {ACCENT};
}}

/* Cards */
QGroupBox {{
  margin-top: 18px; border: 1px solid rgba(255,255,255,0.06);
  border-radius: 14px; padding: 12px; background: {COL_PANEL};
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 6px; color: {COL_MUTED}; }}

/* Inputs */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
  background: #1B1D2A; border: 1px solid rgba(255,255,255,0.07);
  border-radius: 10px; padding: 8px 10px; color: {COL_TXT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
  border-color: {ACCENT};
}}

/* Buttons */
QPushButton {{
  background: #1B2030; border: 1px solid rgba(255,255,255,0.08);
  padding: 8px 12px; border-radius: 10px; color: {COL_TXT};
}}
QPushButton:hover {{ background: {ACCENT_HOVER}; }}
QPushButton[primary="true"] {{ border-color: {ACCENT}; }}
QPushButton[primary="true"]:hover {{ background: {ACCENT_HOVER}; }}

/* Progress */
QProgressBar {{ height: 14px; background: #1B1D2A; border: 1px solid rgba(255,255,255,0.08); border-radius: 7px; }}
QProgressBar::chunk {{ border-radius: 7px; background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {ACCENT}, stop:1 {ACCENT_2}); }}

/* Logs */
QPlainTextEdit {{ background: #0F1117; border: 1px solid rgba(255,255,255,0.06); border-radius: 10px; color: #C7FCEF; font: 12px 'Consolas','Fira Code',monospace; }}


/* ---------------------------------
   Top Filter Bar (QSS Safe)
---------------------------------- */
QWidget#TopFilterBar {{
  background-color: #232538;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.06);
  padding: 8px;
}}

/* Title */
QWidget#TopFilterBar QLabel[role="title"] {{
  font-weight: 600;
  color: #E6E6E9;
}}

/* Labels */
QWidget#TopFilterBar QLabel {{
  color: #A7A9B4;
}}

/* Date inputs */
QWidget#TopFilterBar QDateEdit {{
  background-color: #1B1D2A;
  border: 1px solid rgba(255,255,255,0.07);
  border-radius: 10px;
  padding: 6px;
  color: #E6E6E9;
  min-width: 120px;
}}

QWidget#TopFilterBar QDateEdit:focus {{
  border: 1px solid #00CFFF;
}}

/* QDateEdit dropdown styling */
QWidget#TopFilterBar QDateEdit::drop-down {{
  border: none;
  width: 24px;
  padding-right: 6px;
  background-color: transparent;
  color: white;
}}

/* Make arrow visible */
QWidget#TopFilterBar QDateEdit::down-arrow {{
  width: 14px;
  height: 14px;
}}

/* Calendar popup */
QCalendarWidget {{
  background-color: #232538;
  border: 1px solid rgba(255,255,255,0.08);
}}

QCalendarWidget QToolButton {{
  background-color: transparent;
  color: #E6E6E9;
}}

QCalendarWidget QAbstractItemView {{
  selection-background-color: #00CFFF;
  selection-color: #000000;
}}

/* Buttons inside filter */
QWidget#TopFilterBar QPushButton {{
  padding: 6px 12px;
  border-radius: 10px;
}}

/* Apply button */
QPushButton[primary="true"] {{
  border: 1px solid #00CFFF;
}}

QPushButton[primary="true"]:hover {{
  background-color: #00BFFF;
  color: #000000;
}}

/* Reset button */
QPushButton[secondary="true"] {{
  background-color: transparent;
  border: 1px solid rgba(255,255,255,0.08);
}}

QPushButton[secondary="true"]:hover {{
  background-color: rgba(255,255,255,0.05);
}}
"""