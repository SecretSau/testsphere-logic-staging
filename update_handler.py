import os
import sys
import requests
import zipfile
import tempfile
import subprocess
from pathlib import Path
import shutil

from PyQt5.QtWidgets import QProgressDialog, QMessageBox, QApplication
from PyQt5.QtCore import Qt

APP_NAME = "TestSphere"
GITHUB_REPO = "SecretSau/TestSphere_V1_releases_apk_QA"
OLD_ASSETS_DIR_NAME = ".assets_for_testsphere"

# ---------------------------------
# Helpers & Backend Functions
# ---------------------------------

def get_app_data_dir() -> Path:
    """Gets the root directory for app data in %LOCALAPPDATA% and ensures it exists."""
    path = Path(os.path.expandvars(r"%LOCALAPPDATA%")) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

# Alias for backward compatibility with older clients that import this name
get_app_root_dir = get_app_data_dir

def get_current_version():
    """
    Reads the current version from version.txt.
    It checks the new location (app root) first, then falls back to the old
    assets directory for backward compatibility.
    """
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    new_version_file = os.path.join(app_dir, 'version.txt')

    old_assets_path = Path(os.path.expandvars(r"%LOCALAPPDATA%")) / OLD_ASSETS_DIR_NAME
    old_version_file = old_assets_path / 'version.txt'

    version_path_to_use = None
    if os.path.exists(new_version_file):
        version_path_to_use = new_version_file
    elif os.path.exists(old_version_file):
        version_path_to_use = old_version_file

    if version_path_to_use:
        try:
            with open(version_path_to_use, 'r') as f:
                return f.read().strip()
        except Exception as e:
            print(f"Error reading version file at {version_path_to_use}: {e}")
            return "0.0.0"
    else:
        print(f"Warning: version.txt not found in new or old locations. Defaulting to version 0.0.0")
        return "0.0.0"

def parse_version(version_str):
    """
    Parse a semantic version string into a tuple of integers for proper comparison.
    Strips 'v' prefix if present.
    Example: "v1.0.10" -> (1, 0, 10)
    """
    version_str = version_str.lstrip('v')
    try:
        return tuple(int(x) for x in version_str.split('.'))
    except ValueError:
        # Fallback for non-standard versions
        return (0, 0, 0)

def get_latest_release():
    """Fetch latest release info from GitHub API."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        assets = data.get("assets", [])
        release_notes = data.get("body", "No release notes provided.")
        for asset in assets:
            if asset["name"].endswith(".zip"):
                return data["tag_name"], asset["browser_download_url"], release_notes
    except requests.exceptions.RequestException as e:
        print(f"Error fetching latest release: {e}")
    return None, None, None

def download_file(url, dest, parent=None):
    """Download file from GitHub with a progress dialog."""
    try:
        r = requests.get(url, stream=True)
        r.raise_for_status()
        total_size = int(r.headers.get('content-length', 0))
        progress = None
        if parent:
            progress = QProgressDialog("Downloading update...", "Cancel", 0, total_size, parent)
            progress.setWindowModality(Qt.WindowModal)
            progress.show()

        downloaded = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(1024):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress and progress.wasCanceled(): return None
                    if progress: progress.setValue(downloaded)
                    QApplication.processEvents()
        if progress: progress.close()
        return dest
    except requests.exceptions.RequestException as e:
        print(f"Error downloading file: {e}")
        if progress: progress.close()
        QMessageBox.critical(parent, "Download Error", f"Failed to download update: {e}")
    return None

def cleanup_old_updater():
    """
    This function is kept for backward compatibility to prevent crashes
    for users updating from an old version that still calls this.
    The new update process does not create an 'updater.exe.old' file,
    so this function can safely do nothing.
    """
    pass


def launch_updater(update_source_dir):
    """
    Launches the updater script to apply the update.
    It checks for the updater in the new location (app root) first, then falls
    back to the old assets directory for backward compatibility.
    """
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    exe_name = os.path.basename(sys.argv[0])

    # --- Look for updater in new and old locations ---
    updater_path_py = os.path.join(app_dir, "updater.py")
    updater_path_exe = os.path.join(app_dir, "updater.exe")

    old_assets_path = Path(os.path.expandvars(r"%LOCALAPPDATA%")) / OLD_ASSETS_DIR_NAME
    old_updater_path_exe = old_assets_path / "updater.exe"

    updater_to_run = []
    if os.path.exists(updater_path_py):
        # Development environment: run with python
        updater_to_run = [sys.executable, updater_path_py, update_source_dir, app_dir, exe_name]
    elif os.path.exists(updater_path_exe):
        # New location for frozen application
        updater_to_run = [updater_path_exe, update_source_dir, app_dir, exe_name]
    elif os.path.exists(old_updater_path_exe):
        # Old location (backward compatibility for one update cycle)
        # The old updater was not designed to work with the new batch script method.
        # However, the *new* updater logic is what's needed.
        # The first update will have placed the *new* updater in the *old* location.
        # So we can run it from there with the new arguments.
        updater_to_run = [str(old_updater_path_exe), update_source_dir, app_dir, exe_name]

    if updater_to_run:
        subprocess.Popen(updater_to_run)
        # Exit the main application so the updater can replace files
        sys.exit(0)
    else:
        QMessageBox.critical(None, "Update Error", "Could not find updater.py or updater.exe in new or old locations.")
        return

class UpdateHandler:
    def __init__(self, parent, le_latest):
        self.parent = parent
        self.le_latest = le_latest

    def check_update(self):
        current_version = get_current_version()
        latest_version_tag, download_url, release_notes = get_latest_release()
        if not latest_version_tag:
            QMessageBox.information(self.parent, "Update Check Failed", "Could not fetch release information.\nPlease check your internet connection or the GITHUB_REPO configuration.")
            return

        self.le_latest.setText(latest_version_tag)

        # Use proper semantic version comparison instead of string comparison
        current_ver_tuple = parse_version(current_version)
        latest_ver_tuple = parse_version(latest_version_tag)

        if latest_ver_tuple > current_ver_tuple:
            msg_box = QMessageBox(self.parent)
            msg_box.setIcon(QMessageBox.Information)
            msg_box.setWindowTitle("Update Available")
            msg_box.setText(f"A new version (<b>{latest_version_tag}</b>) is available!")
            msg_box.setInformativeText("Do you want to download and install it now?")

            formatted_notes = release_notes.replace("\r\n", "<br/>").replace("###", "<b>").replace("##", "<h2>").replace("#", "<h1>")
            msg_box.setDetailedText(formatted_notes)

            msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg_box.setDefaultButton(QMessageBox.Yes)
            msg_box.setStyleSheet("QMessageBox { min-width: 450px; }")

            reply = msg_box.exec_()

            if reply == QMessageBox.Yes and download_url:
                # 1. Download the zip file to a temporary location
                temp_zip_path = os.path.join(tempfile.gettempdir(), "update.zip")
                if not download_file(download_url, temp_zip_path, self.parent):
                    return # Download failed or was canceled

                # 2. Create a temporary directory to extract the update
                update_dir = tempfile.mkdtemp(prefix="testsphere_update_")

                # 3. Extract the zip file
                try:
                    with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                        zip_ref.extractall(update_dir)
                except zipfile.BadZipFile:
                    QMessageBox.critical(self.parent, "Update Error", "Failed to extract update files. The downloaded file may be corrupt.")
                    shutil.rmtree(update_dir) # Clean up
                    os.remove(temp_zip_path)
                    return

                # 4. Clean up the downloaded zip file
                os.remove(temp_zip_path)

                # 5. Launch the updater with the path to the extracted files
                QMessageBox.information(self.parent, "Updating", "The application will now close to apply the update.")
                launch_updater(update_dir)
        else:
            QMessageBox.information(self.parent, "No Updates", f"You are using the latest version ({current_version}).")
