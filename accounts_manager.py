import json
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QStackedWidget, QTableWidget, QTableWidgetItem, QAbstractItemView,
    QInputDialog, QMessageBox, QHeaderView, QMenu, QComboBox, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer
from update_handler import get_app_root_dir

# Design Tokens (consistent with ui.py)
COL_BG_1 = "#1E1E2E"
COL_BG_2 = "#232538"
COL_PANEL = COL_BG_2
COL_TXT = "#E2E2EE"
COL_MUTED = "#A7A9B4"
ACCENT = "#00CFFF"
ACCENT_HOVER = "#00BFFF"

ACCOUNTS_FILE = get_app_root_dir() / "TestSphere_accounts.json"

class AccountsManager(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.accounts_data = {}
        self._loaded = False

        # Main layout
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(12)

        # Left panel for account list
        left_panel = QWidget()
        left_panel.setStyleSheet(f"background-color: {COL_PANEL}; border-radius: 14px;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        left_layout.setSpacing(10)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search accounts...")
        self.search_bar.textChanged.connect(self.filter_accounts)
        self.account_list = QListWidget()
        self.account_list.itemClicked.connect(self.switch_account_view)
        self.account_list.itemDoubleClicked.connect(self.rename_account)
        self.account_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.account_list.customContextMenuRequested.connect(self.show_account_context_menu)

        btn_add_account = QPushButton("Add Account")
        btn_add_account.clicked.connect(self.add_account)
        btn_add_account.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {COL_BG_1};
                border: none;
                border-radius: 7px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """)
        btn_rename_account = QPushButton("Rename Account")
        btn_rename_account.clicked.connect(self.rename_account)
        btn_rename_account.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {COL_BG_1};
                border: none;
                border-radius: 7px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """)
        btn_remove_account = QPushButton("Remove Account")
        btn_remove_account.clicked.connect(self.remove_account)
        btn_remove_account.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {COL_BG_1};
                border: none;
                border-radius: 7px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """)
        left_layout.addWidget(self.search_bar)
        left_layout.addWidget(self.account_list)
        left_layout.addWidget(btn_add_account)
        left_layout.addWidget(btn_rename_account)
        left_layout.addWidget(btn_remove_account)

        # Right panel for tables
        self.table_stack = QStackedWidget()

        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(self.table_stack, 3)

        # Defer account loading to prevent blocking UI
        QTimer.singleShot(100, self.load_accounts)

    def filter_accounts(self,text):
        search_text = text.lower()
        for i in range(self.account_list.count()):
            item = self.account_list.item(i)
            name = item.text().lower()
            item.setHidden(search_text not in name)

    def load_accounts(self):
        """Load accounts with error handling. Only load once."""
        if self._loaded:
            return
        
        self._loaded = True
        
        if not ACCOUNTS_FILE.exists():
            return
        
        try:
            with open(ACCOUNTS_FILE, 'r') as f:
                self.accounts_data = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Corrupted accounts file, starting fresh")
            self.accounts_data = {}  # Start fresh on error
        except IOError as e:
            print(f"Warning: Could not read accounts file: {e}")
            self.accounts_data = {}

        try:
            self.rebuild_ui_from_data()
        except Exception as e:
            print(f"Error rebuilding UI from accounts: {e}")
            QMessageBox.warning(self, "Load Error", f"Could not load accounts: {e}")

    def save_accounts(self):
        try:
            ACCOUNTS_FILE.parent.mkdir(exist_ok=True, parents=True)
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump(self.accounts_data, f, indent=4)
        except IOError as e:
            QMessageBox.warning(self, "Save Error", f"Could not save accounts data: {e}")

    def rebuild_ui_from_data(self):
        self.account_list.clear()
        while self.table_stack.count() > 0:
            widget = self.table_stack.widget(0)
            self.table_stack.removeWidget(widget)
            widget.deleteLater()

        for account_name, data in self.accounts_data.items():
            self.account_list.addItem(account_name)
            table = AccountTable(account_name, self)
            table.load_data(data)
            self.table_stack.addWidget(table)

        if self.account_list.count() > 0:
            self.account_list.setCurrentRow(0)
            self.table_stack.setCurrentIndex(0)

    def add_account(self):
            dialog = QInputDialog(self)
            dialog.setWindowTitle("Add Account")
            dialog.setLabelText("Enter account name: ")
            dialog.resize(400, 120)

            ok = dialog.exec_()
            name = dialog.textValue()
            if ok and name:
                self.accounts_data[name] = []
                self.account_list.addItem(name)
                table = AccountTable(name, self)
                self.table_stack.addWidget(table)
                self.account_list.setCurrentRow(self.account_list.count() - 1)
                self.table_stack.setCurrentWidget(table)
                self.save_accounts()

    def remove_account(self):
        current_item = self.account_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "Warning", "Please select an account to remove.")
            return

        reply = QMessageBox.question(self, 'Confirm Deletion',
                                     f"Are you sure you want to delete the account '{current_item.text()}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            account_name = current_item.text()
            row = self.account_list.row(current_item)

            # Remove from data
            del self.accounts_data[account_name]

            # Remove from UI
            self.account_list.takeItem(row)
            widget_to_remove = self.table_stack.widget(row)
            self.table_stack.removeWidget(widget_to_remove)
            widget_to_remove.deleteLater()

            self.save_accounts()

    def rename_account(self, item=None):
        """Rename the selected/clicked account. Triggered by the Rename
        button, double-clicking a list item, or the right-click context menu."""
        if not isinstance(item, QListWidgetItem):
            item = self.account_list.currentItem()

        if not item:
            QMessageBox.warning(self, "Warning", "Please select an account to rename.")
            return

        old_name = item.text()
        new_name, ok = QInputDialog.getText(
            self, "Rename Account", "Enter new account name:",
            QLineEdit.Normal, old_name
        )
        if not ok:
            return

        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "Warning", "Account name cannot be empty.")
            return
        if new_name == old_name:
            return
        if new_name in self.accounts_data:
            QMessageBox.warning(self, "Warning",
                                 f"An account named '{new_name}' already exists.")
            return

        # Move the account's data under the new key
        self.accounts_data[new_name] = self.accounts_data.pop(old_name)
        item.setText(new_name)

        # Keep the corresponding table's internal name in sync so future
        # edits (add row, delete row, etc.) save under the new key instead
        # of silently recreating the old one.
        row = self.account_list.row(item)
        table = self.table_stack.widget(row)
        if isinstance(table, AccountTable):
            table.account_name = new_name

        self.save_accounts()

    def show_account_context_menu(self, pos):
        item = self.account_list.itemAt(pos)
        if not item:
            return

        menu = QMenu()
        rename_action = menu.addAction("Rename Account")
        remove_action = menu.addAction("Remove Account")
        action = menu.exec_(self.account_list.mapToGlobal(pos))

        if action == rename_action:
            self.rename_account(item)
        elif action == remove_action:
            self.account_list.setCurrentItem(item)
            self.remove_account()

    def switch_account_view(self, item):
        row = self.account_list.row(item)
        self.table_stack.setCurrentIndex(row)

class AccountTable(QWidget):
    def __init__(self, account_name, parent=None):
        super().__init__(parent)
        self.account_name = account_name
        self.manager = parent  # The AccountsManager instance

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Create the table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Environment", "Link", "Email", "Password", "Account Code"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setStyleSheet(f"""
                                                    QHeaderView::section{{
                                                    color: {COL_TXT};
                                                    background-color: {COL_BG_2};
                                                    font-weight: bold;
                                                    border: none;
                                                    padding: 6px;
                                                    }}""")
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemChanged.connect(self.handle_item_changed)
        layout.addWidget(self.table)

        # Create buttons for table actions
        button_layout = QHBoxLayout()
        btn_add_row = QPushButton("Add New Row")
        btn_add_row.clicked.connect(self.add_row)
        btn_add_row.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {COL_BG_1};
                border: none;
                border-radius: 7px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """)
        button_layout.addWidget(btn_add_row)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        btn_delete_row = QPushButton("Delete Selected Row")
        btn_delete_row.clicked.connect(self.delete_selected_row)
        btn_delete_row.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT};
                color: {COL_BG_1};
                border: none;
                border-radius: 7px;
                padding: 6px 12px;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_HOVER};
            }}
        """)
        button_layout.addWidget(btn_delete_row)

    def delete_selected_row(self):
        selected_rows = sorted(set(index.row() for index in self.table.selectedIndexes()), reverse=True)
        if not selected_rows:
            QMessageBox.warning(self, "Warning", "Please select a row to delete.")
            return
        for row in selected_rows:
            self.table.removeRow(row)
        self.handle_item_changed()

    def load_data(self, data):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for row_data in data:
            row_position = self.table.rowCount()
            self.table.insertRow(row_position)
            for col, value in enumerate(row_data):
                self.table.setItem(row_position, col, QTableWidgetItem(str(value)))
        self.table.blockSignals(False)

    def get_data(self):
        data = []
        for row in range(self.table.rowCount()):
            row_data = [self.table.item(row, col).text() if self.table.item(row, col) else "" for col in range(self.table.columnCount())]
            data.append(row_data)
        return data

    def add_row(self):
        row_position = self.table.rowCount()
        self.table.insertRow(row_position)
        self.handle_item_changed() # Trigger a save

    def handle_item_changed(self, item=None):
        if self.manager:
            self.manager.accounts_data[self.account_name] = self.get_data()
            self.manager.save_accounts()

    def show_context_menu(self, pos):
        menu = QMenu()
        delete_row_action = menu.addAction("Delete Row")
        clear_cell_action = menu.addAction("Clear Cell Content")

        action = menu.exec_(self.table.mapToGlobal(pos))

        if action == delete_row_action:
            rows = sorted(list(set(index.row() for index in self.table.selectedIndexes())), reverse=True)
            if not rows:
                QMessageBox.warning(self, "Warning", "Please select a row to delete.")
                return
            for row in rows:
                self.table.removeRow(row)
            self.handle_item_changed()
        elif action == clear_cell_action:
            for item in self.table.selectedItems():
                item.setText("")
            # handle_item_changed will be triggered automatically