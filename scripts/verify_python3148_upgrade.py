"""
Install Python 3.14.8 to a safe test location, build a test virtual environment,
recreate the locked dependency set, and run the complete 220-test regression suite.
Preserves existing Python 3.9 and Python 3.14.7 (.venv) environments untouched.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

INSTALLER = Path(tempfile.gettempdir()) / "python-3.14.8-amd64.exe"
TARGET_DIR = Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Python" / "Python3148"
TEST_VENV = Path(".venv_test_3148").resolve()

def test_upgrade() -> None:
    if not INSTALLER.exists():
        raise FileNotFoundError(f"Installer not found: {INSTALLER}")

    # 1. Install 3.14.8 to dedicated test directory
    target_py = TARGET_DIR / "python.exe"
    if not target_py.exists():
        print(f"Installing Python 3.14.8 to {TARGET_DIR}...")
        cmd = [
            str(INSTALLER),
            "/quiet",
            "InstallAllUsers=0",
            "PrependPath=0",
            "Include_launcher=0",
            f"TargetDir={TARGET_DIR}",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        print("Install exit code:", res.returncode)
        if not target_py.exists():
            raise RuntimeError(f"Installation failed: {target_py} missing")
    else:
        print(f"Python 3.14.8 already installed at: {target_py}")

    # Verify version
    ver = subprocess.check_output([str(target_py), "--version"], text=True).strip()
    print("Installed version:", ver)

    # 2. Create test venv
    if TEST_VENV.exists():
        shutil.rmtree(TEST_VENV)
    print(f"Creating isolated test venv at {TEST_VENV}...")
    subprocess.run([str(target_py), "-m", "venv", str(TEST_VENV)], check=True)

    venv_py = TEST_VENV / "Scripts" / "python.exe"
    venv_pytest = TEST_VENV / "Scripts" / "pytest.exe"

    # 3. Install locked dependencies
    lockfile = Path("requirements-lock-py314.txt")
    print(f"Installing from lockfile {lockfile}...")
    subprocess.run([str(venv_py), "-m", "pip", "install", "-r", str(lockfile)], check=True)

    # 4. Run test suite
    print("Running full regression test suite under Python 3.14.8...")
    test_res = subprocess.run([str(venv_pytest), "-q"], capture_output=True, text=True)
    print("Test exit code:", test_res.returncode)
    print("Test output summary:\n", test_res.stdout[-300:] if test_res.stdout else "")
    if test_res.stderr:
        print("Test stderr:\n", test_res.stderr[-300:])

    if test_res.returncode == 0:
        print("\n>>> Python 3.14.8 PASSED all tests and is certified compatible! <<<")
    else:
        print("\n>>> Python 3.14.8 FAILED tests; preserve 3.14.7! <<<")

if __name__ == "__main__":
    test_upgrade()
