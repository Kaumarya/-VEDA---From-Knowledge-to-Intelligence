"""
Download and verify official Python 3.14.7 Windows AMD64 installer.
"""

import hashlib
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

URL = "https://www.python.org/ftp/python/3.14.7/python-3.14.7-amd64.exe"
EXPECTED_SHA256 = "9d9eb2709ef81bf5cd30db3c2096bdbc4ea10087c22e62f27d356b36f6ae9649"

def download_and_verify() -> Path:
    temp_dir = Path(tempfile.gettempdir())
    installer_path = temp_dir / "python-3.14.7-amd64.exe"

    if installer_path.exists():
        hasher = hashlib.sha256()
        with open(installer_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        if hasher.hexdigest().lower() == EXPECTED_SHA256.lower():
            print(f"Installer already present and verified: {installer_path}")
            return installer_path
        else:
            installer_path.unlink()

    print(f"Downloading from {URL} to {installer_path}...")
    urllib.request.urlretrieve(URL, installer_path)

    hasher = hashlib.sha256()
    with open(installer_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    actual_hash = hasher.hexdigest().lower()
    print(f"Actual SHA256:   {actual_hash}")
    print(f"Expected SHA256: {EXPECTED_SHA256.lower()}")

    if actual_hash != EXPECTED_SHA256.lower():
        raise ValueError(f"Checksum mismatch! Expected {EXPECTED_SHA256}, got {actual_hash}")

    print("Integrity check PASSED!")
    return installer_path

if __name__ == "__main__":
    download_and_verify()
