"""
ai_config_chat.py
AI Config Generator panel for TestSphere.
Uses Gemini API directly — no browser needed.
Model: gemini-2.0-flash (1,500 RPD free tier)
"""

import json
import os
import re
import time
import requests
from pathlib import Path
from datetime import datetime

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QPlainTextEdit, QFrame, QSizePolicy,
    QApplication, QMessageBox, QScrollArea
)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QObject, QTimer

# Design tokens
COL_BG_1     = "#1E1E2E"
COL_BG_2     = "#232538"
COL_PANEL    = COL_BG_2
COL_TXT      = "#E6E6E9"
COL_MUTED    = "#A7A9B4"
ACCENT       = "#00CFFF"
ACCENT_2     = "#9A4DFF"
ACCENT_HOVER = "#00BFFF"

GEMINI_MODEL   = "gemini-2.5-flash"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta"
    f"/models/{GEMINI_MODEL}:generateContent"
)

COOLDOWN_SECONDS = 900  # 15 minutes between generations

PROMPT_TEMPLATE = """I need you to write a test automation config file.

Here are the test steps I want automated:
{test_steps}

The website credentials are:
- URL: {link}
- Email: {email}
- Password: {password}
- Account Code: {account_code}

The config file only accepts these command formats:
- Link: followed by the URL
- Login: followed by field name, then the value
- Text: followed by field name, then the value
- click: followed by the exact text of the element to click
- Dropdown: followed by field name, then the option to select
- Calendar: followed by field name, then the date in YYYY-MM-DD
- Checkbox: followed by label, then ON or OFF
- rating: followed by field name, then the numeric rating value (e.g. rating: Satisfaction, 4)
- upload: followed by field name, then the file path (e.g. upload: Attachment, C:/Users/user/Documents/file.pdf)
- sleep: followed by number of seconds

Rules for the new commands:
- Use rating: when the test involves any rating scale, star rating, NPS score, slider score, or numeric score input
- Use upload: when the test involves attaching a file, uploading a document, or selecting a file
- For rating: the value is always a number representing the score (e.g. 4 out of 5 stars = rating: Stars, 4)
- For upload: always use the full file path or just the filename if in Documents folder

Here is an example of a correctly written config:
Link: https://myapp.com
Login: Email, john@example.com
Login: Password, secret123
sleep: 2
click: Facilities
click: Add New
Text: Location Name, Warehouse A
Dropdown: Type, Storage
rating: Quality Score, 4
upload: Attachment, C:/Users/user/Documents/report.pdf
click: Save

Now write the config for my test steps above. Start with Link: {link} and wrap the result in triple backticks."""


def _load_gemini_key() -> str:
    try:
        key_file = (
            Path(os.path.expandvars(r"%LOCALAPPDATA%"))
            / "TestSphere" / "gemini_key.json"
        )
        if key_file.exists():
            with open(key_file, "r") as f:
                return json.load(f).get("api_key", "")
    except Exception:
        pass
    return ""


# ── Background worker ────────────────────────────────────────────────────────

class ChatWorker(QObject):
    finished      = pyqtSignal(dict)
    error         = pyqtSignal(str)
    retry_waiting = pyqtSignal(int, int, int)  # wait_secs, attempt, max

    def __init__(self, prompt: str, api_key: str):
        super().__init__()
        self.prompt  = prompt
        self.api_key = api_key

    def run(self):
        raw_text = ""
        data     = {}
        payload  = {
            "contents": [
                {"role": "user", "parts": [{"text": self.prompt}]}
            ],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
        }

        MAX_RETRIES  = 5
        INITIAL_WAIT = 15

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = requests.post(
                    f"{GEMINI_API_URL}?key={self.api_key}",
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    timeout=60
                )

                if response.status_code == 429:
                    wait_secs = INITIAL_WAIT * attempt
                    print(f"[AI Chat] 429 — waiting {wait_secs}s "
                          f"(attempt {attempt}/{MAX_RETRIES})")
                    self.retry_waiting.emit(wait_secs, attempt, MAX_RETRIES)
                    time.sleep(wait_secs)
                    continue

                response.raise_for_status()
                data = response.json()

                raw_text = (
                    data["candidates"][0]["content"]["parts"][0]["text"].strip()
                )
                raw_text = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text).strip()
                raw_text = re.sub(r"```$",              "", raw_text).strip()

                # Extract config from response
                config_text = self._extract_config(raw_text)
                summary     = self._extract_summary(raw_text)

                self.finished.emit({
                    "config":  config_text,
                    "summary": summary,
                    "raw":     raw_text,
                })
                return

            except requests.exceptions.HTTPError:
                if response.status_code == 429:
                    continue
                self.error.emit(
                    f"API error {response.status_code}: {response.text[:200]}"
                )
                return
            except requests.exceptions.RequestException as e:
                self.error.emit(f"API request failed: {e}")
                return
            except (KeyError, IndexError) as e:
                self.error.emit(
                    f"Unexpected Gemini response: {e}\n\nRaw: {str(data)[:300]}"
                )
                return
            except Exception as e:
                self.error.emit(str(e))
                return

        self.error.emit(
            f"Rate limit persisted after {MAX_RETRIES} retries. "
            "Please wait a moment and try again."
        )

    def _extract_config(self, text: str) -> str:
        # 1. Inside triple backticks
        fence = re.search(r"```[a-zA-Z]*\n?(.*?)```", text, re.DOTALL)
        if fence:
            block = fence.group(1).strip()
            if re.search(r"(?i)^link:", block, re.MULTILINE):
                return block

        # 2. Scan for Link: block
        lines        = text.splitlines()
        config_lines = []
        in_config    = False
        for line in lines:
            stripped = line.strip()
            if re.match(r"(?i)^link:", stripped):
                in_config    = True
                config_lines = []
            if in_config:
                if not stripped and config_lines:
                    break
                if stripped:
                    config_lines.append(stripped)

        if config_lines:
            return "\n".join(config_lines)

        # 3. Raw text starts with Link:
        if re.match(r"(?i)^link:", text):
            return text

        return text  # return as-is if nothing matched

    def _extract_summary(self, text: str) -> str:
        # Get first non-config sentence as summary
        for line in text.splitlines():
            line = line.strip()
            if line and not re.match(
                r"(?i)^(link:|login:|text:|click:|dropdown:|calendar:|checkbox:|sleep:|```)",
                line
            ):
                return line[:120]
        return "Config generated successfully."


# ── Chat bubble ───────────────────────────────────────────────────────────────

class ChatBubble(QFrame):
    def __init__(self, text: str, is_user: bool, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        bubble.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        if is_user:
            bubble.setStyleSheet(f"""
                QLabel {{
                    background: {ACCENT}22;
                    color: {COL_TXT};
                    border: 1px solid {ACCENT}55;
                    border-radius: 10px;
                    padding: 8px 12px;
                    font-size: 12px;
                }}
            """)
            layout.addStretch()
            layout.addWidget(bubble)
        else:
            bubble.setStyleSheet(f"""
                QLabel {{
                    background: #1B1D2A;
                    color: {COL_TXT};
                    border: 1px solid rgba(255,255,255,0.07);
                    border-radius: 10px;
                    padding: 8px 12px;
                    font-size: 12px;
                }}
            """)
            layout.addWidget(bubble)
            layout.addStretch()


# ── Main panel ────────────────────────────────────────────────────────────────

class AIChatPanel(QWidget):
    """
    AI chat panel for generating TestSphere configs via Gemini API.

    Signals:
        config_generated(account_name, env_name, config_text)
    """
    config_generated = pyqtSignal(str, str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._account_data   = None
        self._account_name   = ""
        self._env_name       = ""
        self._worker         = None
        self._thread         = None
        self._cooldown_left  = 0
        self._cooldown_timer = QTimer()
        self._cooldown_timer.setInterval(1000)
        self._cooldown_timer.timeout.connect(self._tick_cooldown)
        self._setup_ui()

    # ── Public API ───────────────────────────────────────────────────

    def set_account(self, account_name: str, env_name: str, account_data: dict):
        self._account_name = account_name
        self._env_name     = env_name
        self._account_data = account_data
        self._update_header()

    def clear_account(self):
        self._account_name = ""
        self._env_name     = ""
        self._account_data = None
        self._update_header()

    # ── UI ───────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        # Header
        self.header_label = QLabel("💬  AI Config Generator")
        self.header_label.setStyleSheet(
            f"color: {COL_TXT}; font-size: 13px; font-weight: 700; padding: 4px 0;"
        )
        root.addWidget(self.header_label)

        self.account_label = QLabel(
            "No account selected — select an account first."
        )
        self.account_label.setWordWrap(True)
        self.account_label.setStyleSheet(
            f"color: {COL_MUTED}; font-size: 11px; padding: 4px 8px; "
            f"background: rgba(255,255,255,0.03); border-radius: 6px;"
        )
        root.addWidget(self.account_label)

        # Progress bar
        from PyQt5.QtWidgets import QProgressBar
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedHeight(4)
        self.progress.setVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background: #1B1D2A; border-radius: 2px; border: none; }}
            QProgressBar::chunk {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 {ACCENT}, stop:1 {ACCENT_2});
                border-radius: 2px;
            }}
        """)
        root.addWidget(self.progress)

        # Chat history
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 6px; background: transparent; }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.10); border-radius: 3px;
            }
        """)
        self._chat_container = QWidget()
        self._chat_container.setStyleSheet("background: transparent;")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setSpacing(6)
        self._chat_layout.setContentsMargins(4, 4, 4, 4)
        self._chat_layout.addStretch(1)
        scroll.setWidget(self._chat_container)
        self._scroll = scroll
        root.addWidget(scroll, 1)

        # Input area
        input_frame = QFrame()
        input_frame.setStyleSheet(f"""
            QFrame {{
                background: #1B1D2A;
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
            }}
        """)
        input_layout = QVBoxLayout(input_frame)
        input_layout.setContentsMargins(8, 8, 8, 8)
        input_layout.setSpacing(6)

        hint = QLabel(
            "Describe your test steps and expected result in plain English."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet(
            f"color: {COL_MUTED}; font-size: 10px; font-style: italic;"
        )
        input_layout.addWidget(hint)

        self.input_box = QPlainTextEdit()
        self.input_box.setPlaceholderText(
            "Example:\nNavigate to Locations. Click Add Location.\n"
            "Enter 'Main Office' in Name field. Click Save.\n"
            "Expected: Location appears in the list."
        )
        self.input_box.setFixedHeight(90)
        self.input_box.setStyleSheet(f"""
            QPlainTextEdit {{
                background: transparent;
                border: none;
                color: {COL_TXT};
                font-size: 12px;
            }}
        """)
        input_layout.addWidget(self.input_box)

        btn_row = QHBoxLayout()
        self.btn_clear = QPushButton("Clear Chat")
        self.btn_clear.setStyleSheet(self._btn_style(COL_MUTED))
        self.btn_clear.clicked.connect(self._clear_chat)
        self.btn_clear.setFixedHeight(32)

        self.btn_send = QPushButton("⚡  Generate Config")
        self.btn_send.setStyleSheet(self._btn_style(ACCENT))
        self.btn_send.clicked.connect(self._send)
        self.btn_send.setFixedHeight(32)

        btn_row.addWidget(self.btn_clear)
        btn_row.addStretch()
        btn_row.addWidget(self.btn_send)
        input_layout.addLayout(btn_row)
        root.addWidget(input_frame)

    # ── Helpers ──────────────────────────────────────────────────────

    def _btn_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background: {color}22;
                color: {color};
                border: 1px solid {color}55;
                border-radius: 7px;
                padding: 4px 14px;
                font-size: 12px;
                font-weight: 600;
            }}
            QPushButton:hover {{ background: {color}44; }}
            QPushButton:disabled {{ opacity: 0.4; }}
        """

    def _update_header(self):
        if self._account_name and self._env_name:
            self.account_label.setText(
                f"🏢  Account: <b>{self._account_name}</b>  |  "
                f"🌐  Environment: <b>{self._env_name}</b>"
            )
            self.account_label.setStyleSheet(
                f"color: {ACCENT}; font-size: 11px; padding: 4px 8px; "
                f"background: {ACCENT}11; border: 1px solid {ACCENT}33; "
                f"border-radius: 6px;"
            )
        else:
            self.account_label.setText(
                "No account selected — select an account first."
            )
            self.account_label.setStyleSheet(
                f"color: {COL_MUTED}; font-size: 11px; padding: 4px 8px; "
                f"background: rgba(255,255,255,0.03); border-radius: 6px;"
            )

    def _add_bubble(self, text: str, is_user: bool):
        bubble = ChatBubble(text, is_user, self._chat_container)
        self._chat_layout.insertWidget(
            self._chat_layout.count() - 1, bubble
        )
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        )

    def _clear_chat(self):
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    # ── Cooldown ─────────────────────────────────────────────────────

    def _start_cooldown(self):
        self._cooldown_left = COOLDOWN_SECONDS
        self._cooldown_timer.start()
        self._update_send_btn()

    def _tick_cooldown(self):
        self._cooldown_left -= 1
        if self._cooldown_left <= 0:
            self._cooldown_left = 0
            self._cooldown_timer.stop()
            self.btn_send.setEnabled(True)
            self.btn_send.setText("⚡  Generate Config")
            self.btn_send.setStyleSheet(self._btn_style(ACCENT))
        else:
            self._update_send_btn()

    def _update_send_btn(self):
        if self._cooldown_left > 0:
            mins = self._cooldown_left // 60
            secs = self._cooldown_left % 60
            self.btn_send.setText(f"⏳  Ready in {mins:02d}:{secs:02d}")
            self.btn_send.setEnabled(False)
            self.btn_send.setStyleSheet(self._btn_style(COL_MUTED))

    # ── Send ─────────────────────────────────────────────────────────

    def _send(self):
        if not self._account_data:
            self._add_bubble(
                "⚠️  Please select an account first.", is_user=False
            )
            return

        user_text = self.input_box.toPlainText().strip()
        if not user_text:
            return

        api_key = _load_gemini_key()
        if not api_key:
            self._add_bubble(
                "⚠️  Gemini API key not set. Please configure it via AI Settings.",
                is_user=False
            )
            return

        self._add_bubble(user_text, is_user=True)
        self.input_box.clear()
        self.btn_send.setEnabled(False)
        self.input_box.setEnabled(False)
        self.progress.setVisible(True)

        prompt = PROMPT_TEMPLATE.format(
            link         = self._account_data.get("Link: ", ""),
            email        = self._account_data.get("Login: ", ""),
            password     = self._account_data.get("Password: ", ""),
            account_code = self._account_data.get("Account Code: ", ""),
            test_steps   = user_text,
        )

        self._worker = ChatWorker(prompt, api_key)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.retry_waiting.connect(self._on_retry_waiting)
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.start()

    def _on_retry_waiting(self, wait_secs: int, attempt: int, max_retries: int):
        self._add_bubble(
            f"⏳  Rate limit hit — auto-retrying in {wait_secs}s "
            f"(attempt {attempt}/{max_retries})…",
            is_user=False
        )

    def _on_done(self, result: dict):
        self.progress.setVisible(False)
        self.input_box.setEnabled(True)

        config_text = result.get("config", "")
        summary     = result.get("summary", "Config generated.")

        self._add_bubble(
            f"✅  {summary}\n\n📄  Config file created and loaded into the editor.",
            is_user=False
        )

        if config_text:
            self.config_generated.emit(
                self._account_name, self._env_name, config_text
            )

        self._start_cooldown()

    def _on_error(self, msg: str):
        self.progress.setVisible(False)
        self.btn_send.setEnabled(True)
        self.btn_send.setText("⚡  Generate Config")
        self.btn_send.setStyleSheet(self._btn_style(ACCENT))
        self.input_box.setEnabled(True)
        self._add_bubble(f"❌  Error: {msg}", is_user=False)
