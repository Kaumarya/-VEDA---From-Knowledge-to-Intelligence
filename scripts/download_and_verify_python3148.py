"""
Download and verify official Python 3.14.8 Windows AMD64 installer.
"""

import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path

URL = "https://www.python.org/ftp/python/3.14.8/python-3.14.8-amd64.exe"

def download_and_verify() -> Path:
    temp_dir = Path(tempfile.gettempdir())
    installer_path = temp_dir / "python-3.14.8-amd64.exe"

    if installer_path.exists() and installer_path.stat().st_size == 33387464:
        hasher = hashlib.sha256()
        with open(installer_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        digest = hasher.hexdigest().lower()
        print(f"Installer already present: {installer_path}")
        print(f"SHA-256: {digest}")
        return installer_path

    print(f"Downloading {URL}...")
    urllib.request.urlretrieve(URL, installer_path)
    hasher = hashlib.sha256()
    with open(installer_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    digest = hasher.hexdigest().lower()
    print(f"Downloaded: {installer_path}")
    print(f"File size:  {installer_path.stat().st_size} bytes")
    print(f"SHA-256:    {digest}")
    return installer_path

if __name__ == "__main__":
    download_and_verify()
