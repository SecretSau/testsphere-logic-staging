"""
TestSphere — Enterprise UI
PyQt5 · Splash + Sidebar + Dashboard + Config + Accounts + Updates
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime
import logic_updater
import logic  # populated by logic_updater.get_logic() during splash
import json
import re

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import (
    QApplication, QDateEdit, QWidget, QVBoxLayout, QPushButton,
    QListWidget, QTextEdit, QFileDialog, QMessageBox, QHBoxLayout,
    QLabel, QShortcut, QComboBox, QGroupBox, QFormLayout, QLineEdit,
    QSpinBox, QCheckBox, QPlainTextEdit, QToolButton, QDialog,
    QDialogButtonBox, QInputDialog
)
from PyQt5.QtGui import QKeySequence, QPixmap, QFont, QPainter
from PyQt5.QtCore import Qt, QTimer, QDate, QDateTime, QLoggingCategory
from PyQt5.QtChart import QChart, QChartView, QPieSeries

from update_handler import (
    get_current_version, cleanup_old_updater, get_app_root_dir, UpdateHandler
)
from accounts_manager import AccountsManager
from ai_config_chat import AIChatPanel
from gemini_settings import GeminiKeyDialog
from QSS import (
    QSS, COL_BG_1, COL_BG_2, COL_PANEL, COL_TXT,
    COL_MUTED, ACCENT, ACCENT_2, ACCENT_HOVER
)

# Suppress QWebEngine / JS console noise
QLoggingCategory.setFilterRules("js=false")

APP_NAME      = "TestSphere"
DOCUMENTS_PATH = Path.home() / "Documents"


# ── Helpers ───────────────────────────────────────────────────────────────────

def appdata_dir() -> Path:
    log_dir = get_app_root_dir() / "Logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir


# ── Splash ────────────────────────────────────────────────────────────────────

class Splash(QtWidgets.QSplashScreen):
    def __init__(self):
        w, h = 640, 340
        pm = QtGui.QPixmap(w, h)
        pm.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pm)
        grad = QtGui.QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QtGui.QColor(COL_BG_1))
        grad.setColorAt(1, QtGui.QColor(COL_BG_1))
        painter.fillRect(0, 0, w, h, grad)
        painter.setPen(QtGui.QPen(QtGui.QColor(ACCENT)))
        painter.setFont(QtGui.QFont("Segoe UI", 18, QtGui.QFont.DemiBold))
        painter.drawText(QtCore.QRect(0, 110, w, 40), QtCore.Qt.AlignHCenter, APP_NAME)
        painter.setPen(QtGui.QColor(COL_MUTED))
        painter.setFont(QtGui.QFont("Segoe UI", 10))
        painter.drawText(QtCore.QRect(0, 145, w, 24), QtCore.Qt.AlignHCenter, "Initializing components…")
        painter.end()
        super().__init__(pm)
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.progress = QtWidgets.QProgressBar(self)
        self.progress.setGeometry(160, h - 80, w - 320, 20)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)

    def advance(self, v):
        self.progress.setValue(v)


# ── Card ──────────────────────────────────────────────────────────────────────

class Card(QtWidgets.QGroupBox):
    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 6)
        shadow.setColor(QtGui.QColor(0, 0, 0, 120))
        self.setGraphicsEffect(shadow)


# ── Command registry ──────────────────────────────────────────────────────────

COMMANDS = [
    "Link:", "Login:", "Text:", "click:", "Button:",
    "Dropdown:", "Calendar:", "Checkbox:",
    "rating:", "upload:", "icon:",
    "sleep:",
]

COMMAND_SNIPPETS = {
    "Link:":     "Link: https://example.com",
    "Login:":    'Login: "field_name", "value"',
    "Text:":     'Text: "field_name", "text_to_type"',
    "click:":    'click: "element_text"',
    "Button:":   'Button: "button_text"',
    "Dropdown:": 'Dropdown: "field_name", "option_to_select"',
    "Calendar:": 'Calendar: "field_name", "YYYY-MM-DD"',
    "Checkbox:": 'Checkbox: "label_text", ON',
    "rating:":   'rating: "field_name", 4',
    "upload:":   'upload: "field_name", "C:/path/to/file.pdf"',
    "icon:":     'icon: "icon-name"',
    "sleep:":    "sleep: 1",
}


# ── History / Autocomplete ────────────────────────────────────────────────────

class HistoryManager:
    def __init__(self, history_file):
        self.history_file = history_file
        self.history = self._load()

    def _load(self):
        try:
            with open(self.history_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"commands": {}, "values": {}}

    def save_history(self):
        with open(self.history_file, "w") as f:
            json.dump(self.history, f, indent=2)

    def add_command(self, command_line):
        if not command_line.strip():
            return
        parts = command_line.split(":")
        cmd = parts[0].strip() + ":"
        if cmd not in COMMANDS:
            return
        self.history["commands"][cmd] = self.history["commands"].get(cmd, 0) + 1
        if len(parts) > 1:
            args = re.split(r",\s*(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", parts[1].strip())
            for i, arg in enumerate(args):
                arg = arg.strip().strip('"')
                key = f"{cmd}_{i}"
                if key not in self.history["values"]:
                    self.history["values"][key] = {}
                self.history["values"][key][arg] = (
                    self.history["values"][key].get(arg, 0) + 1
                )
        self.save_history()

    def get_command_suggestions(self):
        suggestions = list(COMMANDS)
        learned = sorted(
            self.history["commands"], key=self.history["commands"].get, reverse=True
        )
        for cmd in learned:
            if cmd in suggestions:
                suggestions.remove(cmd)
        return learned + suggestions

    def get_value_suggestions(self, command, arg_index):
        key = f"{command}_{arg_index}"
        if key in self.history["values"]:
            return sorted(
                self.history["values"][key],
                key=self.history["values"][key].get,
                reverse=True,
            )
        return []


class Completer(QtWidgets.QCompleter):
    def __init__(self, history_manager, parent=None):
        super().__init__(parent)
        self.history_manager = history_manager
        self.setCaseSensitivity(Qt.CaseInsensitive)
        self.update_model_for_commands()

    def update_model_for_commands(self):
        self.setModel(
            QtCore.QStringListModel(
                self.history_manager.get_command_suggestions(), self
            )
        )

    def update_model_for_values(self, command, arg_index):
        self.setModel(
            QtCore.QStringListModel(
                self.history_manager.get_value_suggestions(command, arg_index), self
            )
        )


class ConfigEditor(QTextEdit):
    COMMAND_MODE, SNIPPET_MODE = 0, 1

    def __init__(self, history_manager, parent=None):
        super().__init__(parent)
        self._completer = None
        self.history_manager = history_manager
        self.set_mode(self.COMMAND_MODE)

    def set_mode(self, mode):
        self.mode = mode
        if self._completer and self.mode == self.COMMAND_MODE:
            self._completer.update_model_for_commands()

    def setCompleter(self, completer):
        self._completer = completer
        self._completer.setWidget(self)
        self._completer.setCompletionMode(QtWidgets.QCompleter.PopupCompletion)
        self._completer.activated.connect(self.insert_completion)

    def insert_completion(self, completion):
        tc = self.textCursor()
        if self.mode == self.SNIPPET_MODE:
            tc.select(QtGui.QTextCursor.WordUnderCursor)
            tc.insertText(completion)
            self.select_next_placeholder()
        else:
            snippet = COMMAND_SNIPPETS.get(completion, completion)
            tc.select(QtGui.QTextCursor.WordUnderCursor)
            tc.insertText(snippet)
            self.set_mode(self.SNIPPET_MODE)
            self.select_next_placeholder()

    def find_placeholders(self, text):
        command_part = text.split(":")[0] + ":"
        text_after = text[len(command_part):]
        pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_-]+)|(".*?")')
        return list(pattern.finditer(text_after))

    def select_next_placeholder(self):
        tc       = self.textCursor()
        line     = tc.block().text()
        line_pos = tc.block().position()
        placeholders = self.find_placeholders(line)
        cur_end  = tc.selectionEnd() - line_pos
        prefix_len = len(line.split(":")[0]) + 1
        for m in placeholders:
            m_start = m.start() + prefix_len
            if cur_end < m_start:
                start = m.start() + prefix_len
                end   = m.end()   + prefix_len
                tc.setPosition(line_pos + start)
                tc.setPosition(line_pos + end, QtGui.QTextCursor.KeepAnchor)
                self.setTextCursor(tc)
                self.trigger_value_suggestions()
                return
        tc.movePosition(QtGui.QTextCursor.EndOfLine)
        self.setTextCursor(tc)
        self.set_mode(self.COMMAND_MODE)

    def trigger_value_suggestions(self):
        tc   = self.textCursor()
        line = tc.block().text()
        cmd  = line.split(":")[0] + ":"
        before = line[: tc.selectionStart() - tc.block().position()]
        idx  = before.count(",")
        self._completer.update_model_for_values(cmd, idx)
        self.show_completer_popup()

    def show_completer_popup(self):
        prefix = self.textCursor().selectedText()
        if not prefix:
            tc = self.textCursor()
            tc.select(QtGui.QTextCursor.WordUnderCursor)
            prefix = tc.selectedText()
        self._completer.setCompletionPrefix(prefix)
        cr = self.cursorRect()
        cr.setWidth(
            self._completer.popup().sizeHintForColumn(0)
            + self._completer.popup().verticalScrollBar().sizeHint().width()
        )
        self._completer.complete(cr)

    def keyPressEvent(self, e):
        if self._completer and self._completer.popup().isVisible():
            if e.key() in (Qt.Key_Enter, Qt.Key_Return):
                self.insert_completion(self._completer.currentCompletion())
                self._completer.popup().hide()
                e.accept()
                return
            if e.key() in (Qt.Key_Tab, Qt.Key_Backtab):
                e.ignore()
                return
        if self.mode == self.SNIPPET_MODE and e.key() == Qt.Key_Tab:
            self.select_next_placeholder()
            e.accept()
            return
        super().keyPressEvent(e)
        tc   = self.textCursor()
        line = tc.block().text()
        colon_pos = line.find(":")
        if colon_pos != -1 and tc.positionInBlock() > colon_pos:
            if self.mode == self.COMMAND_MODE:
                self.set_mode(self.SNIPPET_MODE)
        else:
            if self.mode == self.SNIPPET_MODE:
                self.set_mode(self.COMMAND_MODE)
        if self.mode == self.COMMAND_MODE:
            tc.select(QtGui.QTextCursor.WordUnderCursor)
            if tc.selectedText():
                self.show_completer_popup()
            else:
                self._completer.popup().hide()
        else:
            self.trigger_value_suggestions()


# ── Account selection dialog ──────────────────────────────────────────────────

class AccountSelectionDialog(QDialog):
    def __init__(self, accounts_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Account")
        self.accounts_data = accounts_data
        self.setMinimumWidth(400)
        layout      = QVBoxLayout(self)
        form_layout = QFormLayout()
        self.account_combo = QComboBox()
        self.env_combo     = QComboBox()
        self.name_edit     = QLineEdit()
        self.name_edit.setPlaceholderText("Leave blank to auto-generate")
        self.account_combo.addItems(self.accounts_data.keys())
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        self.account_combo.currentIndexChanged.connect(self.update_environments)
        form_layout.addRow("Account:", self.account_combo)
        form_layout.addRow("Environment:", self.env_combo)
        form_layout.addRow("Config Name:", self.name_edit)
        layout.addLayout(form_layout)
        layout.addWidget(btn_box)
        self.update_environments()

    def get_config_name(self) -> str:
        """Return the sanitized custom config name (no extension), or ''
        if the field was left blank — callers should fall back to the
        existing auto-generated naming scheme in that case."""
        raw = self.name_edit.text().strip()
        if not raw:
            return ""
        if raw.lower().endswith(".txt"):
            raw = raw[:-4].strip()
        # Strip characters that aren't valid in Windows filenames
        safe = re.sub(r'[\\/:*?"<>|]', "_", raw).strip()
        return safe

    def update_environments(self):
        self.env_combo.clear()
        name = self.account_combo.currentText()
        if name:
            envs = [
                r[0] for r in self.accounts_data.get(name, []) if r and r[0]
            ]
            self.env_combo.addItems(envs)

    def get_selected_data(self):
        name = self.account_combo.currentText()
        env  = self.env_combo.currentText()
        if not name or not env:
            return None
        for row in self.accounts_data.get(name, []):
            if row and row[0] == env:
                return {
                    "Link: ":         row[1] if len(row) > 1 else "",
                    "Login: ":        row[2] if len(row) > 2 else "",
                    "Password: ":     row[3] if len(row) > 3 else "",
                    "Account Code: ": row[4] if len(row) > 4 else "",
                }
        return None


# ── Main Window ───────────────────────────────────────────────────────────────

class MainWindow(QtWidgets.QWidget):
    def __init__(self, channel: str = "production"):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Console")
        self.setMinimumSize(1180, 720)
        self.history_manager    = HistoryManager(get_app_root_dir() / "history.json")
        self.current_config_path = None
        self.channel             = channel  # "production" or "staging" — from logic_updater's channel_override.json

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        self.topbar = self.build_topbar()
        root.addWidget(self.topbar)

        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)
        root.addLayout(body, 1)

        self.sidebar = self.build_sidebar()
        body.addWidget(self.sidebar, 0)

        self.stack = QtWidgets.QStackedWidget()
        body.addWidget(self.stack, 1)

        self.page_dashboard = self.build_dashboard()
        self.page_accounts  = AccountsManager()
        self.page_config    = self.build_config()
        self.page_updates   = self.build_updates()

        self.stack.addWidget(self.page_dashboard)
        self.stack.addWidget(self.page_config)
        self.stack.addWidget(self.page_accounts)
        self.stack.addWidget(self.page_updates)

        self.switch_page(0)

    # ── Top bar ───────────────────────────────────────────────────────────────

    def build_topbar(self):
        bar = QtWidgets.QFrame()
        bar.setObjectName("TopBar")
        lay = QtWidgets.QHBoxLayout(bar)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        mark = QtWidgets.QLabel()
        mark.setFixedSize(12, 12)
        pm = QtGui.QPixmap(12, 12)
        pm.fill(QtCore.Qt.transparent)
        p = QtGui.QPainter(pm)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        grad = QtGui.QConicalGradient(6, 6, 0)
        grad.setColorAt(0.0, QtGui.QColor(ACCENT))
        grad.setColorAt(0.5, QtGui.QColor(ACCENT_2))
        grad.setColorAt(1.0, QtGui.QColor(ACCENT))
        p.setBrush(grad)
        p.setPen(QtCore.Qt.NoPen)
        p.drawEllipse(0, 0, 12, 12)
        p.end()
        mark.setPixmap(pm)

        title = QtWidgets.QLabel(APP_NAME)
        title.setProperty("role", "title")
        if self.channel != "production":
            meta = QtWidgets.QLabel(f"v1 · ⚠ {self.channel.upper()} CHANNEL · Not Production")
            meta.setStyleSheet("color: #FF8A00; font-weight: 600;")
        else:
            meta = QtWidgets.QLabel("v1 · Secure · Ready")
        meta.setProperty("role", "meta")

        lay.addWidget(mark)
        lay.addWidget(title)
        lay.addSpacing(6)
        lay.addWidget(meta)
        lay.addStretch(1)

        # AI Settings button
        btn_ai = QtWidgets.QPushButton("🔑  AI Settings")
        btn_ai.clicked.connect(lambda: GeminiKeyDialog(self).exec_())
        btn_ai.setStyleSheet(
            "QPushButton{background:#1B2030;border:1px solid rgba(255,255,255,0.08);"
            "padding:5px 12px;border-radius:8px;color:#E6E6E9;font-size:11px;}"
            "QPushButton:hover{background:#00CFFF;color:#000;}"
        )

        btn_min = QtWidgets.QToolButton()
        btn_min.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarMinButton))
        btn_min.clicked.connect(self.showMinimized)
        btn_close = QtWidgets.QToolButton()
        btn_close.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_TitleBarCloseButton))
        btn_close.clicked.connect(self.close)

        lay.addWidget(btn_ai)
        lay.addWidget(btn_min)
        lay.addWidget(btn_close)
        return bar

    # ── Sidebar ───────────────────────────────────────────────────────────────

    def build_sidebar(self):
        frame = QtWidgets.QFrame()
        frame.setObjectName("SideBar")
        frame.setFixedWidth(220)
        v = QtWidgets.QVBoxLayout(frame)
        v.setContentsMargins(10, 10, 10, 10)
        v.setSpacing(6)

        self.nav_group = QtWidgets.QButtonGroup(self)
        self.nav_group.setExclusive(True)

        btn_dash     = self.nav_button("Dashboard",     QtWidgets.QStyle.SP_ComputerIcon)
        btn_cfg      = self.nav_button("Configuration", QtWidgets.QStyle.SP_FileDialogDetailedView)
        btn_accounts = self.nav_button("Accounts",      QtWidgets.QStyle.SP_DirIcon)
        btn_upd      = self.nav_button("Updates",       QtWidgets.QStyle.SP_BrowserReload)

        for i, b in enumerate((btn_dash, btn_cfg, btn_accounts, btn_upd)):
            self.nav_group.addButton(b, i)
            v.addWidget(b)

        v.addStretch(1)
        self.nav_group.buttonClicked[int].connect(self.switch_page)
        return frame

    def nav_button(self, text, sp_icon):
        b = QtWidgets.QToolButton()
        b.setProperty("nav", True)
        b.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
        b.setIcon(self.style().standardIcon(sp_icon))
        b.setText(text)
        b.setCheckable(True)
        b.setAutoExclusive(True)
        b.setCursor(QtCore.Qt.PointingHandCursor)
        b.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        return b

    def switch_page(self, idx):
        self.stack.setCurrentIndex(idx)
        for i, b in enumerate(self.nav_group.buttons()):
            active = i == idx
            b.setProperty("active", active)
            b.setChecked(active)
            b.style().unpolish(b)
            b.style().polish(b)

    # ── Dashboard ─────────────────────────────────────────────────────────────

    def build_dashboard(self):
        page   = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(12)

        # Filter bar
        self.filter_bar = QtWidgets.QWidget()
        self.filter_bar.setObjectName("TopFilterBar")
        fl = QtWidgets.QHBoxLayout(self.filter_bar)
        fl.setContentsMargins(10, 6, 10, 6)
        fl.setSpacing(8)

        font9 = QFont(); font9.setPointSize(9)
        lbl_from = QLabel("From"); lbl_from.setFont(font9)
        lbl_to   = QLabel("To");   lbl_to.setFont(font9)

        self.btn_from = QDateEdit(); self.btn_from.setCalendarPopup(True)
        self.btn_from.setDate(QDate.currentDate())
        self.btn_to   = QDateEdit(); self.btn_to.setCalendarPopup(True)
        self.btn_to.setDate(QDate.currentDate())

        self.btn_apply = QPushButton("Apply")
        self.btn_apply.setProperty("primary", True)
        self.btn_apply.clicked.connect(self.filter_execution_by_date)
        btn_reset = QPushButton("Reset")
        btn_reset.clicked.connect(self.reset_dashboard_filters)

        title_lbl = QLabel("Execution Filters"); title_lbl.setProperty("role", "title")
        fl.addWidget(title_lbl); fl.addSpacing(12)
        fl.addWidget(lbl_from); fl.addWidget(self.btn_from)
        fl.addWidget(lbl_to);   fl.addWidget(self.btn_to)
        fl.addStretch()
        fl.addWidget(self.btn_apply); fl.addWidget(btn_reset)
        layout.addWidget(self.filter_bar)
        self.filter_bar.setVisible(False)

        # Info cards
        grid = QtWidgets.QGridLayout(); grid.setSpacing(12)
        layout.addLayout(grid)
        self.label_total_executed  = QLabel("0")
        self.label_total_passed    = QLabel("0")
        self.label_total_failed    = QLabel("0")
        self.label_tests_per_hour  = QLabel("0")
        grid.addWidget(self._create_info_card("Test Cases Done",        self.label_total_executed),  0, 0)
        grid.addWidget(self._create_info_card("Passed Executions",      self.label_total_passed),    0, 1)
        grid.addWidget(self._create_info_card("Failed Executions",      self.label_total_failed),    1, 0)
        grid.addWidget(self._create_info_card("Test Cases Per Hour",    self.label_tests_per_hour),  1, 1)

        # Quick actions
        actions_card   = Card("Quick Actions")
        actions_layout = QtWidgets.QHBoxLayout(actions_card)
        btn_configure  = QtWidgets.QPushButton("Configure & Create Tests")
        btn_configure.setProperty("primary", True)
        btn_configure.clicked.connect(lambda: self.switch_page(1))
        btn_accounts_  = QtWidgets.QPushButton("Accounts Management")
        btn_accounts_.clicked.connect(lambda: self.switch_page(2))
        btn_updates_   = QtWidgets.QPushButton("Check for Updates")
        btn_updates_.clicked.connect(lambda: self.switch_page(3))
        btn_filter_    = QtWidgets.QPushButton("Filter by Date")
        btn_filter_.clicked.connect(
            lambda: self.filter_bar.setVisible(not self.filter_bar.isVisible())
        )
        actions_layout.addWidget(btn_configure)
        actions_layout.addWidget(btn_accounts_)
        actions_layout.addWidget(btn_updates_)
        actions_layout.addWidget(btn_filter_)
        actions_layout.addStretch(1)
        layout.addWidget(actions_card)
        layout.addStretch(1)

        self._update_dashboard_cards()
        return page

    def _create_info_card(self, title, label_widget):
        card   = Card(title)
        layout = QVBoxLayout(card)
        label_widget.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        label_widget.setStyleSheet("font-size: 36px; font-weight: bold;")
        layout.addWidget(label_widget)
        return card

    def _update_dashboard_cards(self):
        f = get_app_root_dir() / "dashboard.json"
        if not f.exists():
            return
        with open(f) as fh:
            data = json.load(fh)
        s = data.get("summary", {})
        self.label_total_executed.setText(str(s.get("total_executed", 0)))
        self.label_total_passed.setText(str(s.get("total_passed", 0)))
        self.label_total_failed.setText(str(s.get("total_failed", 0)))
        key = datetime.now().strftime("%Y-%m-%d %H:00")
        self.label_tests_per_hour.setText(str(s.get("per_hour", {}).get(key, 0)))

    def reset_dashboard_filters(self):
        self.btn_from.setDate(QDate.currentDate())
        self.btn_to.setDate(QDate.currentDate())
        self._update_dashboard_cards()

    def filter_execution_by_date(self):
        f = get_app_root_dir() / "dashboard.json"
        from_d = self.btn_from.date().toString("yyyy-MM-dd")
        to_d   = self.btn_to.date().toString("yyyy-MM-dd")
        if from_d > to_d:
            QMessageBox.warning(self, "Invalid Range", "'From' cannot be later than 'To'.")
            return
        try:
            with open(f) as fh:
                data = json.load(fh)
            execs   = data.get("executions", [])
            filtered = [e for e in execs if from_d <= e.get("date", "") <= to_d]
            self.label_total_executed.setText(str(len(filtered)))
            self.label_total_passed.setText(str(sum(1 for e in filtered if e.get("status") == "passed")))
            self.label_total_failed.setText(str(sum(1 for e in filtered if e.get("status") == "failed")))
            self.label_tests_per_hour.setText("N/A")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # ── Config page ───────────────────────────────────────────────────────────

    def build_config(self):
        page   = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(12)

        # Left — accounts list
        left_panel = Card("Accounts")
        left_panel.setFixedWidth(220)
        left_layout = QVBoxLayout(left_panel)
        self.config_account_list = QListWidget()
        self.config_account_list.itemClicked.connect(self.populate_configs_for_account)
        btn_manage = QPushButton("Manage Accounts")
        btn_manage.clicked.connect(lambda: self.switch_page(2))
        left_layout.addWidget(QLabel("Select an Account:"))
        left_layout.addWidget(self.config_account_list)
        left_layout.addWidget(btn_manage)

        # Centre — config list + editor
        right_panel  = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        manage_card   = Card("Configurations")
        manage_layout = QVBoxLayout(manage_card)
        self.config_file_list = QListWidget()
        self.config_file_list.itemClicked.connect(self.load_selected_config)
        cfg_btns = QHBoxLayout()
        btn_add  = QPushButton("Add New Configuration"); btn_add.clicked.connect(self.create_new_config)
        btn_del  = QPushButton("Delete Configuration");  btn_del.clicked.connect(self.delete_config)
        btn_shr  = QPushButton("Share Config");          btn_shr.clicked.connect(self.share_config)
        cfg_btns.addWidget(btn_add); cfg_btns.addWidget(btn_del)
        cfg_btns.addWidget(btn_shr); cfg_btns.addStretch()
        manage_layout.addWidget(self.config_file_list)
        manage_layout.addLayout(cfg_btns)

        edit_card   = Card("Edit Configuration")
        edit_layout = QVBoxLayout(edit_card)
        self.text_edit = ConfigEditor(self.history_manager)
        completer = Completer(self.history_manager)
        self.text_edit.setCompleter(completer)
        self.text_edit.setPlaceholderText("Select an account and configuration to edit.")
        self.text_edit.setFont(QFont("Consolas", 11))
        self.text_edit.setReadOnly(True)
        edit_btns = QHBoxLayout()
        btn_save  = QPushButton("Save"); btn_save.clicked.connect(self.save_current_config)
        self.btn_run = QPushButton("Run This Config")
        self.btn_run.setProperty("primary", True)
        self.btn_run.setEnabled(False)
        self.btn_run.clicked.connect(self.run_config)
        edit_btns.addStretch()
        edit_btns.addWidget(btn_save)
        edit_btns.addWidget(self.btn_run)
        edit_layout.addWidget(self.text_edit)
        edit_layout.addLayout(edit_btns)

        right_layout.addWidget(manage_card)
        right_layout.addWidget(edit_card, 1)

        # Right — AI chat panel
        chat_box = QGroupBox("AI Config Assistant")
        chat_box.setFixedWidth(450)
        chat_box_layout = QVBoxLayout(chat_box)
        chat_box_layout.setContentsMargins(8, 12, 8, 8)
        self.ai_chat_panel = AIChatPanel()
        self.ai_chat_panel.config_generated.connect(self._on_ai_config_generated)
        chat_box_layout.addWidget(self.ai_chat_panel)

        layout.addWidget(left_panel)
        layout.addWidget(right_panel, 1)
        layout.addWidget(chat_box)

        # Sync account list changes
        self.page_accounts.account_list.model().rowsInserted.connect(self.populate_config_accounts)
        self.page_accounts.account_list.model().rowsRemoved.connect(self.populate_config_accounts)
        self.populate_config_accounts()

        save_sc = QShortcut(QKeySequence("Ctrl+S"), self)
        save_sc.activated.connect(self.save_current_config)
        return page

    # ── Updates page ─────────────────────────────────────────────────────────

    def build_updates(self):
        page = QtWidgets.QWidget()
        v    = QtWidgets.QVBoxLayout(page)
        v.setSpacing(12)
        card = Card("Updates")
        form = QtWidgets.QFormLayout(card)
        self.le_current = QtWidgets.QLineEdit(get_current_version())
        self.le_current.setReadOnly(True)
        self.le_latest  = QtWidgets.QLineEdit("N/A")
        self.le_latest.setReadOnly(True)
        form.addRow("Current Version:", self.le_current)
        form.addRow("Latest Available:", self.le_latest)
        info = QLabel("Click 'Check for Updates' to get the latest version.")
        info.setStyleSheet(f"font-style:italic;color:{COL_MUTED};")
        hl  = QtWidgets.QHBoxLayout()
        btn = QtWidgets.QPushButton("Check for Updates")
        btn.setProperty("primary", True)
        self.update_handler = UpdateHandler(self, self.le_latest)
        btn.clicked.connect(self.update_handler.check_update)
        hl.addWidget(btn); hl.addStretch(1)
        v.addWidget(card); v.addWidget(info); v.addLayout(hl); v.addStretch(1)
        return page

    # ── Config utilities ──────────────────────────────────────────────────────

    def populate_config_accounts(self):
        self.config_account_list.clear()
        self.config_file_list.clear()
        self.text_edit.clear()
        self.text_edit.setReadOnly(True)
        all_accounts = list(self.page_accounts.accounts_data.keys())
        accounts_with_configs = set()
        config_dir = DOCUMENTS_PATH / "config_folder"
        if config_dir.exists():
            for f in config_dir.glob("config_*.txt"):
                try:
                    accounts_with_configs.add(f.stem.split("_")[1])
                except IndexError:
                    pass
        for acc in all_accounts:
            item = QtWidgets.QListWidgetItem(acc)
            if acc in accounts_with_configs:
                font = item.font(); font.setBold(True); item.setFont(font)
            self.config_account_list.addItem(item)

    def populate_configs_for_account(self, item):
        account_name = item.text()
        self.config_file_list.clear()
        self.text_edit.clear()
        self.text_edit.setReadOnly(True)
        self.current_config_path = None
        self.btn_run.setEnabled(False)

        config_dir = DOCUMENTS_PATH / "config_folder"
        if config_dir.exists():
            for f in config_dir.glob(f"config_{account_name}_*.txt"):
                self.config_file_list.addItem(f.name)

        # ── Pass real account data to AI chat panel ──
        account_rows = self.page_accounts.accounts_data.get(account_name, [])
        if account_rows:
            first_row = account_rows[0]
            env_name  = first_row[0] if len(first_row) > 0 else ""
            account_data = {
                "Link: ":         first_row[1] if len(first_row) > 1 else "",
                "Login: ":        first_row[2] if len(first_row) > 2 else "",
                "Password: ":     first_row[3] if len(first_row) > 3 else "",
                "Account Code: ": first_row[4] if len(first_row) > 4 else "",
            }
            self.ai_chat_panel.set_account(account_name, env_name, account_data)
        else:
            self.ai_chat_panel.clear_account()

    def _on_ai_config_generated(self, account_name, env_name, config_text):
        config_dir = DOCUMENTS_PATH / "config_folder"
        config_dir.mkdir(parents=True, exist_ok=True)
        counter   = 1
        file_name = f"config_{account_name}_{env_name}_AI_{counter}.txt"
        path      = config_dir / file_name
        while path.exists():
            counter  += 1
            file_name = f"config_{account_name}_{env_name}_AI_{counter}.txt"
            path      = config_dir / file_name
        try:
            path.write_text(config_text, encoding="utf-8")
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Could not save AI config: {e}")
            return
        self.populate_configs_for_account(self.config_account_list.currentItem())
        for i in range(self.config_file_list.count()):
            if self.config_file_list.item(i).text() == file_name:
                self.config_file_list.setCurrentRow(i)
                self.load_selected_config(self.config_file_list.item(i))
                break

    def create_new_config(self):
        if not self.config_account_list.currentItem():
            QMessageBox.warning(self, "Error", "Please select an account first.")
            return
        account_name = self.config_account_list.currentItem().text()
        scoped       = {account_name: self.page_accounts.accounts_data.get(account_name, [])}
        dialog       = AccountSelectionDialog(scoped, self)
        if dialog.exec_() != QDialog.Accepted:
            return
        selected = dialog.get_selected_data()
        env_name = dialog.env_combo.currentText()
        if not selected or not env_name:
            QMessageBox.warning(self, "Error", "No valid environment selected.")
            return
        config_dir = DOCUMENTS_PATH / "config_folder"
        config_dir.mkdir(parents=True, exist_ok=True)

        custom_name = dialog.get_config_name()
        if custom_name:
            file_name = f"{custom_name}.txt"
            path      = config_dir / file_name
            suffix    = 2
            while path.exists():
                # Never silently overwrite an existing config — suffix instead.
                file_name = f"{custom_name}_{suffix}.txt"
                path      = config_dir / file_name
                suffix   += 1
        else:
            counter   = 1
            file_name = f"config_{account_name}_{env_name}_{counter}.txt"
            path      = config_dir / file_name
            while path.exists():
                counter  += 1
                file_name = f"config_{account_name}_{env_name}_{counter}.txt"
                path      = config_dir / file_name
        content = (
            f"Link: {selected.get('Link: ', '')}\n"
            f"Login: E-Mail, {selected.get('Login: ', '')}\n"
            f"Login: Password, {selected.get('Password: ', '')}\n"
            f"Text: Account, {selected.get('Account Code: ', '')}\n"
        )
        try:
            path.write_text(content)
            QMessageBox.information(self, "Success", f"Config created: {path.name}")
            self.populate_configs_for_account(self.config_account_list.currentItem())
            for i in range(self.config_file_list.count()):
                if self.config_file_list.item(i).text() == file_name:
                    self.config_file_list.setCurrentRow(i)
                    self.load_selected_config(self.config_file_list.item(i))
                    break
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to create file:\n{e}")

    def load_selected_config(self, item):
        if not item:
            return
        path = DOCUMENTS_PATH / "config_folder" / item.text()
        self.current_config_path = path
        try:
            self.text_edit.setPlainText(path.read_text())
            self.text_edit.setReadOnly(False)
            self.btn_run.setEnabled(True)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to read file:\n{e}")
            self.text_edit.clear()
            self.text_edit.setReadOnly(True)
            self.current_config_path = None
            self.btn_run.setEnabled(False)

    def save_current_config(self):
        if not self.current_config_path:
            QMessageBox.warning(self, "Save Error", "No config file loaded to save.")
            return
        try:
            self.current_config_path.write_text(self.text_edit.toPlainText())
        except Exception as e:
            QMessageBox.warning(self, "Save Error", f"Could not save file:\n{e}")

    def delete_config(self):
        if not self.config_file_list.currentItem():
            QMessageBox.warning(self, "Error", "Please select a configuration to delete.")
            return
        file_name = self.config_file_list.currentItem().text()
        path      = DOCUMENTS_PATH / "config_folder" / file_name
        reply = QMessageBox.question(
            self, "Confirm", f"Delete '{file_name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                path.unlink()
                self.config_file_list.takeItem(self.config_file_list.currentRow())
                self.text_edit.clear(); self.text_edit.setReadOnly(True)
                self.current_config_path = None; self.btn_run.setEnabled(False)
                QMessageBox.information(self, "Deleted", f"Deleted {file_name}.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not delete: {e}")

    def share_config(self):
        if not self.config_file_list.currentItem():
            QMessageBox.warning(self, "Error", "Please select a configuration to share.")
            return
        file_name = self.config_file_list.currentItem().text()
        dialog    = QDialog(self)
        dialog.setWindowTitle("Share Configuration")
        dialog.setMinimumWidth(400)
        lay  = QVBoxLayout(dialog)
        lay.addWidget(QLabel(f"Share: <b>{file_name}</b>"))
        grp  = QGroupBox("Choose method:")
        glay = QVBoxLayout(grp)
        b1   = QPushButton("Copy File Path to Clipboard")
        b1.clicked.connect(lambda: self._copy_config_path(file_name))
        b2   = QPushButton("Export Configuration")
        b2.clicked.connect(lambda: self._export_config(file_name))
        b3   = QPushButton("View Configuration Content")
        b3.clicked.connect(lambda: self._show_config_content(file_name))
        glay.addWidget(b1); glay.addWidget(b2); glay.addWidget(b3)
        grp.setLayout(glay)
        close = QPushButton("Close"); close.clicked.connect(dialog.accept)
        lay.addWidget(grp); lay.addWidget(close)
        dialog.exec_()

    def _copy_config_path(self, file_name):
        path = str(DOCUMENTS_PATH / "config_folder" / file_name)
        QtWidgets.QApplication.clipboard().setText(path)
        QMessageBox.information(self, "Copied", f"Path copied:\n{path}")

    def _export_config(self, file_name):
        src = DOCUMENTS_PATH / "config_folder" / file_name
        if not src.exists():
            QMessageBox.warning(self, "Error", f"File not found: {file_name}")
            return
        dst, _ = QFileDialog.getSaveFileName(
            self, "Export", str(DOCUMENTS_PATH / file_name), "Text Files (*.txt);;All (*)"
        )
        if dst:
            import shutil
            shutil.copy2(src, dst)
            QMessageBox.information(self, "Exported", f"Saved to:\n{dst}")

    def _show_config_content(self, file_name):
        path = DOCUMENTS_PATH / "config_folder" / file_name
        if not path.exists():
            QMessageBox.warning(self, "Error", f"File not found: {file_name}")
            return
        try:
            content = path.read_text()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e)); return
        dlg  = QDialog(self)
        dlg.setWindowTitle(f"Config: {file_name}")
        dlg.setMinimumSize(600, 400)
        lay  = QVBoxLayout(dlg)
        te   = QPlainTextEdit(); te.setPlainText(content)
        te.setReadOnly(True); te.setFont(QFont("Consolas", 10))
        btn  = QPushButton("Copy All")
        btn.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(content))
        lay.addWidget(te); lay.addWidget(btn)
        dlg.exec_()

    # ── Execution ─────────────────────────────────────────────────────────────

    def _record_test_execution(self, status):
        f = get_app_root_dir() / "dashboard.json"
        if not f.exists():
            data = {"executions": [], "summary": {
                "total_executed": 0, "total_passed": 0,
                "total_failed": 0, "per_hour": {}
            }}
        else:
            with open(f) as fh: data = json.load(fh)
        now = datetime.now()
        data["executions"].append({
            "timestamp": now.isoformat(timespec="seconds"),
            "date":      now.strftime("%Y-%m-%d"),
            "status":    status.lower()
        })
        data["summary"]["total_executed"] += 1
        if status.lower() == "pass":
            data["summary"]["total_passed"] += 1
        else:
            data["summary"]["total_failed"] += 1
        key = now.strftime("%Y-%m-%d %H:00")
        data["summary"]["per_hour"][key] = data["summary"]["per_hour"].get(key, 0) + 1
        with open(f, "w") as fh: json.dump(data, fh, indent=2)

    def run_config(self):
        if not self.current_config_path or not self.current_config_path.exists():
            QMessageBox.warning(self, "Error", "No valid config file selected.")
            return
        self.save_current_config()
        with open(self.current_config_path) as f:
            for line in f:
                self.history_manager.add_command(line.strip())
        try:
            results, judgment, screenshot = logic.automate_from_config(self.current_config_path)
            self._record_test_execution(judgment.get("status", "UNKNOWN"))
            self._update_dashboard_cards()

            ai_status = judgment.get("status", "UNKNOWN")
            ai_reason = judgment.get("reason", "No reason provided.")
            msg = QMessageBox(self)
            msg.setWindowTitle("AI Judgment")
            msg.setText(f"<b>AI judged this run as {ai_status}.</b>")
            msg.setInformativeText(f"Reason: {ai_reason}\n\nDo you agree?")
            msg.setIcon(QMessageBox.Information if ai_status == "PASS" else QMessageBox.Warning)
            agree_btn    = msg.addButton("Agree",    QMessageBox.YesRole)
            override_btn = msg.addButton("Override", QMessageBox.NoRole)
            msg.exec_()

            user_override = {"applied": False}
            if msg.clickedButton() == override_btn:
                new_status = "PASS" if ai_status == "FAIL" else "FAIL"
                reason, ok = QInputDialog.getText(
                    self, "Override Reason",
                    f"Reason for overriding to '{new_status}':"
                )
                if ok and reason:
                    user_override = {"applied": True, "final_status": new_status, "reason": reason}

            folder = QFileDialog.getExistingDirectory(
                self, "Save PDF Report", str(Path.home() / "Documents")
            )
            if not folder:
                QMessageBox.warning(self, "Aborted", "No folder selected.")
                return
            pdf = logic.create_pdf_report(
                results=results, overall_judgment=judgment,
                user_override=user_override, screenshot=screenshot, folder=folder
            )
            QMessageBox.information(self, "Report Saved", f"PDF saved to:\n{pdf}")
        except Exception as e:
            QMessageBox.critical(self, "Execution Error", f"Critical error:\n{e}")


# ── App bootstrap ─────────────────────────────────────────────────────────────

class App(QtWidgets.QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName(APP_NAME)
        self.setOrganizationName(APP_NAME)
        self.setStyleSheet(QSS)
        self.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    def launch(self):
        cleanup_old_updater()
        appdata_dir()
        splash = Splash()
        splash.show()

        # Phase 1: Intro (0-20%)
        for i in range(0, 21, 2):
            QtWidgets.qApp.processEvents()
            splash.advance(i)
            QtCore.QThread.msleep(10)

        # Phase 2: Logic update check (20-95%)
        _logic_updated = False
        _logic_status  = "ok"
        _logic_message = ""
        _logic_channel = "production"

        def _progress(pct, msg):
            mapped = 20 + int(pct * 0.75)
            splash.advance(min(mapped, 95))
            QtWidgets.qApp.processEvents()

        try:
            result = logic_updater.get_logic(progress_callback=_progress)
            _logic_updated = result.updated
            _logic_status  = result.status
            _logic_message = result.message
            _logic_channel = result.channel

            # Critical: `import logic` at the top of this file bound the
            # name to whatever was importable at process start (the copy
            # bundled in the exe). get_logic() correctly swaps
            # sys.modules['logic'], but that does NOT retroactively fix
            # this module's already-bound `logic` name — without this
            # explicit rebind, every logic.automate_from_config(...) call
            # below would keep running the exe's original bundled copy
            # forever, no matter how many successful updates occur.
            global logic
            logic = result.logic_module
        except Exception as e:
            _logic_status  = "error"
            _logic_message = str(e)

        # Phase 3: Build window (95-100%)
        for i in range(95, 101):
            QtWidgets.qApp.processEvents()
            splash.advance(i)
            QtCore.QThread.msleep(8)

        win = MainWindow(channel=_logic_channel)
        win.showMaximized()
        splash.finish(win)

        # Notify user of update or error
        if _logic_channel != "production":
            QMessageBox.warning(
                win, "Non-Production Channel Active",
                f"TestSphere is running logic.py/vision.py from the "
                f"'{_logic_channel}' channel, not production.\n\n{_logic_message}\n\n"
                f"Delete channel_override.json in %LOCALAPPDATA%\\TestSphere\\ "
                "to return to production."
            )
        elif _logic_updated:
            QMessageBox.information(
                win, "Logic Updated",
                f"logic.py has been updated to the latest version.\n\n{_logic_message}"
            )
        elif _logic_status == "error":
            QMessageBox.warning(
                win, "Logic Load Warning",
                f"Could not load latest logic.py:\n\n{_logic_message}\n\n"
                "The application will use the available cached version."
            )

        return win


if __name__ == "__main__":
    app = App(sys.argv)
    win = app.launch()
    sys.exit(app.exec_())
