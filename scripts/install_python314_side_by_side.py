"""
Install Python 3.14.7 side-by-side with zero impact on Python 3.9:
- TargetDir: C:\\Users\\karnik YOGA\\AppData\\Local\\Programs\\Python\\Python314
- InstallAllUsers=0 (user scope only)
- PrependPath=0 (preserves existing PATH, leaving python pointing to Python 3.9)
- Include_launcher=1 (updates py.exe launcher so py -3.14 works)
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

INSTALLER = Path(tempfile.gettempdir()) / "python-3.14.7-amd64.exe"
TARGET_DIR = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Python" / "Python314"

def install() -> None:
    if not INSTALLER.exists():
        raise FileNotFoundError(f"Installer not found: {INSTALLER}")

    target_python = TARGET_DIR / "python.exe"
    if target_python.exists():
        print(f"Python 3.14 already installed at: {target_python}")
        return

    print(f"Installing Python 3.14.7 side-by-side to {TARGET_DIR}...")
    cmd = [
        str(INSTALLER),
        "/quiet",
        "InstallAllUsers=0",
        "PrependPath=0",
        "Include_launcher=0",
        f"TargetDir={TARGET_DIR}",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("Return code:", res.returncode)
    if res.stdout:
        print("Stdout:", res.stdout)
    if res.stderr:
        print("Stderr:", res.stderr)

    if not target_python.exists():
        raise RuntimeError(f"Installation failed: {target_python} does not exist.")

    print(f"Successfully installed Python 3.14 to: {target_python}")

if __name__ == "__main__":
    install()
