import os
import sys
import tempfile
import subprocess
import logging

# Configure basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_and_launch_batch_script(update_source_dir, app_dir, app_exe_name):
    """
    Creates a batch script to perform the update and then executes it.
    The batch script will wait, copy files, restart the app, and self-destruct.
    """
    batch_script_content = f"""
@echo off
echo Updating TestSphere... Please wait.

REM Wait for the main application to close completely
timeout /t 5 /nobreak > NUL

REM Copy the updated files from the temporary source directory to the application directory
echo Copying new files...
xcopy /s /y "{update_source_dir}" "{app_dir}"

REM Relaunch the main application
echo Relaunching application...
start "" "{os.path.join(app_dir, app_exe_name)}"

REM Clean up the temporary update folder and the batch script itself
echo Cleaning up...
rmdir /s /q "{update_source_dir}"
(goto) 2>nul & del "%~f0"
"""

    # Create the batch file in the system's temporary directory
    temp_dir = tempfile.gettempdir()
    batch_file_path = os.path.join(temp_dir, "update_script.bat")

    try:
        with open(batch_file_path, "w") as f:
            f.write(batch_script_content)
        logging.info(f"Successfully created batch script at {batch_file_path}")

        # Launch the batch script without waiting for it to complete
        subprocess.Popen([batch_file_path], creationflags=subprocess.CREATE_NEW_CONSOLE)
        logging.info("Launched batch script to perform the update.")

    except Exception as e:
        logging.error(f"Failed to create or launch batch script: {e}")
        # As a fallback, try to restart the original application
        original_app_path = os.path.join(app_dir, app_exe_name)
        if os.path.exists(original_app_path):
            subprocess.Popen([original_app_path])
        sys.exit(1)

    # The updater's job is done, it can exit now.
    sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: updater.py <update_source_dir> <app_dir> <app_exe_name>")
        sys.exit(1)

    source_dir_arg = sys.argv[1]
    app_dir_arg = sys.argv[2]
    app_exe_name_arg = sys.argv[3]

    create_and_launch_batch_script(source_dir_arg, app_dir_arg, app_exe_name_arg)
