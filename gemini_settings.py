"""
gemini_settings.py
Shared Gemini API key storage and settings dialog for TestSphere.

Stores the key in:  %LOCALAPPDATA%/TestSphere/gemini_key.json
"""

import json
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDialogButtonBox, QMessageBox
)
from PyQt5.QtCore import Qt

COL_BG_1 = "#1E1E2E"
COL_BG_2 = "#232538"
COL_TXT = "#E6E6E9"
COL_MUTED = "#A7A9B4"
ACCENT = "#00CFFF"

try:
    from update_handler import get_app_data_dir
    _KEY_FILE = get_app_data_dir() / "gemini_key.json"
except Exception:
    _KEY_FILE = Path.home() / "gemini_key.json"


def load_gemini_key() -> str:
    """Load the saved Gemini API key. Returns empty string if not set."""
    try:
        if _KEY_FILE.exists():
            with open(_KEY_FILE, "r") as f:
                return json.load(f).get("api_key", "")
    except Exception:
        pass
    return ""


def save_gemini_key(key: str):
    """Persist the Gemini API key to disk."""
    _KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_KEY_FILE, "w") as f:
        json.dump({"api_key": key.strip()}, f)


class GeminiKeyDialog(QDialog):
    """Small dialog to enter / update the Gemini API key."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gemini API Key")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"""
            QDialog {{ background: {COL_BG_1}; color: {COL_TXT}; }}
            QLabel  {{ color: {COL_TXT}; font-size: 12px; }}
            QLineEdit {{
                background: #1B1D2A;
                border: 1px solid rgba(255,255,255,0.10);
                border-radius: 8px;
                padding: 8px 10px;
                color: {COL_TXT};
                font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT}; }}
            QPushButton {{
                background: #1B2030;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
                padding: 7px 18px;
                color: {COL_TXT};
                font-size: 12px;
            }}
            QPushButton:hover {{ background: {ACCENT}; color: #000; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        info = QLabel(
            "Enter your <b>Gemini API key</b> from "
            "<a href='https://aistudio.google.com/app/apikey' style='color:#00CFFF;'>Google AI Studio</a>.<br>"
            "The key is stored locally on your machine only."
        )
        info.setOpenExternalLinks(True)
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {COL_MUTED}; font-size: 12px;")
        layout.addWidget(info)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("AIza…")
        self.key_input.setEchoMode(QLineEdit.Password)
        self.key_input.setText(load_gemini_key())
        layout.addWidget(self.key_input)

        show_btn = QPushButton("👁  Show / Hide")
        show_btn.setCheckable(True)
        show_btn.setFixedWidth(120)
        show_btn.clicked.connect(self._toggle_visibility)

        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._save_and_accept)
        btn_box.rejected.connect(self.reject)

        row = QHBoxLayout()
        row.addWidget(show_btn)
        row.addStretch()
        row.addWidget(btn_box)
        layout.addLayout(row)

    def _toggle_visibility(self, checked):
        self.key_input.setEchoMode(
            QLineEdit.Normal if checked else QLineEdit.Password
        )

    def _save_and_accept(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Empty Key", "Please enter a valid API key.")
            return
        save_gemini_key(key)
        self.accept()
