"""
VEDA Candidate Database Subsystem — Reviewer Key Custody & Persistent Signing
Phase 4.14.2.1 — Issue 1
Provides hardware/OS-backed persistent Ed25519 signing key custody via Windows DPAPI,
with separation of test and production keys and zero private-key exposure in SQLite or Git.
"""

import sys
import os
import json
import uuid
import ctypes
from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple, Optional, Dict, Any
from ctypes import wintypes

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from foundation.candidates.signatures import Ed25519SignatureService
from foundation.candidates.exceptions import (
    KeyCustodyError,
    KeyStorageError,
    KeyDecryptionError,
    KeyProviderUnavailableError,
    KeyNotFoundError,
    KeyRevokedError,
)


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class ReviewerKeyProvider(ABC):
    """
    Abstract interface for reviewer private-key custody and digital signing.
    Enforces that private keys are managed outside SQLite and ordinary logs.
    """

    @property
    @abstractmethod
    def is_production(self) -> bool:
        """True if the provider is backed by secure persistent hardware/OS storage."""
        pass

    @abstractmethod
    def generate_and_store_key(self, reviewer_id: str, is_test_key: bool = False) -> Tuple[str, str]:
        """
        Generates an Ed25519 key pair, securely stores the private key,
        and returns (public_key_id, public_key_hex).
        """
        pass

    @abstractmethod
    def sign_payload(self, reviewer_id: str, public_key_id: str, payload_bytes: bytes) -> str:
        """
        Signs the canonical payload bytes using the reviewer's private key.
        Returns 128-character hex signature.
        """
        pass

    @abstractmethod
    def has_private_key(self, reviewer_id: str, public_key_id: str) -> bool:
        """Returns True if the private key is held by this provider."""
        pass

    @abstractmethod
    def rotate_key(self, reviewer_id: str, old_key_id: str) -> Tuple[str, str]:
        """Rotates a reviewer key, retiring the old one and generating a new active key."""
        pass

    @abstractmethod
    def revoke_key(self, reviewer_id: str, public_key_id: str, reason: str) -> None:
        """Revokes a key, permanently disabling it for new signatures."""
        pass


class WindowsDPAPIKeyProvider(ReviewerKeyProvider):
    """
    Production-grade reviewer key custody provider utilizing the Windows Data Protection API (DPAPI).
    Private keys are encrypted at rest using user-scoped CryptProtectData.
    Ciphertext is stored in keystore_dir (excluded from Git).
    Decryption occurs strictly in-memory during signature execution.
    """

    # CryptProtectData flags: CRYPTPROTECT_UI_FORBIDDEN = 0x1
    CRYPTPROTECT_UI_FORBIDDEN = 0x1

    def __init__(self, keystore_dir: Path = Path("data/candidates/keystore")):
        if sys.platform != "win32":
            raise KeyProviderUnavailableError("WindowsDPAPIKeyProvider requires Windows operating system.")

        self.keystore_dir = keystore_dir
        self.keystore_dir.mkdir(parents=True, exist_ok=True)
        self._crypt32 = ctypes.windll.crypt32
        self._kernel32 = ctypes.windll.kernel32

    @property
    def is_production(self) -> bool:
        return True

    def _encrypt_bytes(self, plaintext: bytes, description: str = "VEDA Reviewer Key") -> bytes:
        """Encrypts plaintext bytes using Windows DPAPI CryptProtectData."""
        in_blob = DATA_BLOB(
            len(plaintext),
            ctypes.cast(ctypes.create_string_buffer(plaintext), ctypes.POINTER(ctypes.c_byte)),
        )
        out_blob = DATA_BLOB()
        try:
            res = self._crypt32.CryptProtectData(
                ctypes.byref(in_blob),
                description,
                None,
                None,
                None,
                self.CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(out_blob),
            )
            if not res:
                raise KeyStorageError("CryptProtectData failed to encrypt private key bytes.")
            ciphertext = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return ciphertext
        finally:
            if out_blob.pbData:
                self._kernel32.LocalFree(out_blob.pbData)

    def _decrypt_bytes(self, ciphertext: bytes) -> bytes:
        """Decrypts DPAPI-encrypted ciphertext using CryptUnprotectData."""
        in_blob = DATA_BLOB(
            len(ciphertext),
            ctypes.cast(ctypes.create_string_buffer(ciphertext), ctypes.POINTER(ctypes.c_byte)),
        )
        out_blob = DATA_BLOB()
        try:
            res = self._crypt32.CryptUnprotectData(
                ctypes.byref(in_blob),
                None,
                None,
                None,
                None,
                self.CRYPTPROTECT_UI_FORBIDDEN,
                ctypes.byref(out_blob),
            )
            if not res:
                raise KeyDecryptionError("CryptUnprotectData failed to decrypt private key. Incorrect user or corrupted keystore.")
            plaintext = ctypes.string_at(out_blob.pbData, out_blob.cbData)
            return plaintext
        finally:
            if out_blob.pbData:
                self._kernel32.LocalFree(out_blob.pbData)

    def generate_and_store_key(self, reviewer_id: str, is_test_key: bool = False) -> Tuple[str, str]:
        """Generates an Ed25519 key pair, encrypts private key with DPAPI, and saves to keystore."""
        priv_key = ed25519.Ed25519PrivateKey.generate()
        priv_raw_bytes = priv_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_key = priv_key.public_key()
        pub_raw_bytes = pub_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        public_key_hex = pub_raw_bytes.hex().lower()
        public_key_id = f"urn:key:ed25519:{uuid.uuid4()}"

        try:
            # 1. Encrypt private raw bytes with DPAPI
            cipher_bytes = self._encrypt_bytes(priv_raw_bytes, description=f"VEDA Key: {public_key_id}")

            # 2. Store encrypted blob
            key_file = self.keystore_dir / f"{public_key_id.replace(':', '_')}.dpapi.key"
            with open(key_file, "wb") as f:
                f.write(cipher_bytes)

            # 3. Store public metadata
            meta_file = self.keystore_dir / f"{public_key_id.replace(':', '_')}.meta.json"
            meta = {
                "public_key_id": public_key_id,
                "public_key_hex": public_key_hex,
                "reviewer_id": reviewer_id,
                "is_test_key": is_test_key,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "revoked_at": None,
                "revocation_reason": None,
            }
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            return public_key_id, public_key_hex
        finally:
            # Explicitly overwrite raw private key buffer in memory
            priv_raw_bytes = b"\x00" * len(priv_raw_bytes)

    def _get_key_files(self, public_key_id: str) -> Tuple[Path, Path]:
        safe_id = public_key_id.replace(":", "_")
        return self.keystore_dir / f"{safe_id}.dpapi.key", self.keystore_dir / f"{safe_id}.meta.json"

    def has_private_key(self, reviewer_id: str, public_key_id: str) -> bool:
        key_file, meta_file = self._get_key_files(public_key_id)
        if not key_file.exists() or not meta_file.exists():
            return False
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        return meta.get("reviewer_id") == reviewer_id and meta.get("revoked_at") is None

    def sign_payload(self, reviewer_id: str, public_key_id: str, payload_bytes: bytes) -> str:
        """Decrypts private key in-memory via DPAPI, signs payload, and scrubs plaintext buffer."""
        key_file, meta_file = self._get_key_files(public_key_id)
        if not key_file.exists() or not meta_file.exists():
            raise KeyNotFoundError(f"Key '{public_key_id}' not found in DPAPI keystore.")

        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        if meta.get("reviewer_id") != reviewer_id:
            raise KeyCustodyError(f"Key '{public_key_id}' is owned by another reviewer.")
        if meta.get("revoked_at") is not None:
            raise KeyRevokedError(f"Key '{public_key_id}' was revoked on {meta.get('revoked_at')}: {meta.get('revocation_reason')}")

        with open(key_file, "rb") as f:
            cipher_bytes = f.read()

        plain_bytes = self._decrypt_bytes(cipher_bytes)
        try:
            priv_key = ed25519.Ed25519PrivateKey.from_private_bytes(plain_bytes)
            signature = priv_key.sign(payload_bytes)
            return signature.hex().lower()
        finally:
            # Memory scrub
            plain_bytes = b"\x00" * len(plain_bytes)

    def rotate_key(self, reviewer_id: str, old_key_id: str) -> Tuple[str, str]:
        """Retires old key and provisions new active key."""
        old_key_file, old_meta_file = self._get_key_files(old_key_id)
        if not old_meta_file.exists():
            raise KeyNotFoundError(f"Old key '{old_key_id}' not found for rotation.")

        with open(old_meta_file, "r", encoding="utf-8") as f:
            old_meta = json.load(f)

        # Mark rotated
        old_meta["rotated_at"] = datetime.now(timezone.utc).isoformat()
        with open(old_meta_file, "w", encoding="utf-8") as f:
            json.dump(old_meta, f, indent=2)

        # Provision new key
        new_id, new_pub = self.generate_and_store_key(reviewer_id, is_test_key=old_meta.get("is_test_key", False))
        return new_id, new_pub

    def revoke_key(self, reviewer_id: str, public_key_id: str, reason: str) -> None:
        """Permanently revokes a key in the keystore."""
        key_file, meta_file = self._get_key_files(public_key_id)
        if not meta_file.exists():
            raise KeyNotFoundError(f"Key '{public_key_id}' not found for revocation.")

        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)

        meta["revoked_at"] = datetime.now(timezone.utc).isoformat()
        meta["revocation_reason"] = reason

        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)


class InMemoryEphemeralKeyProvider(ReviewerKeyProvider):
    """
    Ephemeral in-memory key provider strictly for isolated unit testing.
    Flagged as non-production (is_production = False).
    """

    def __init__(self):
        self._keys: Dict[str, Dict[str, Any]] = {}

    @property
    def is_production(self) -> bool:
        return False

    def generate_and_store_key(self, reviewer_id: str, is_test_key: bool = True) -> Tuple[str, str]:
        priv_pem, pub_hex = Ed25519SignatureService.generate_key_pair()
        public_key_id = f"urn:key:ed25519:test:{uuid.uuid4()}"
        self._keys[public_key_id] = {
            "priv_pem": priv_pem,
            "pub_hex": pub_hex,
            "reviewer_id": reviewer_id,
            "is_test_key": is_test_key,
            "revoked": False,
            "revocation_reason": None,
        }
        return public_key_id, pub_hex

    def has_private_key(self, reviewer_id: str, public_key_id: str) -> bool:
        key = self._keys.get(public_key_id)
        return key is not None and key["reviewer_id"] == reviewer_id and not key["revoked"]

    def sign_payload(self, reviewer_id: str, public_key_id: str, payload_bytes: bytes) -> str:
        key = self._keys.get(public_key_id)
        if not key:
            raise KeyNotFoundError(f"Ephemeral key '{public_key_id}' not found.")
        if key["reviewer_id"] != reviewer_id:
            raise KeyCustodyError("Key owned by different reviewer.")
        if key["revoked"]:
            raise KeyRevokedError(f"Key '{public_key_id}' is revoked.")
        return Ed25519SignatureService.sign(key["priv_pem"], payload_bytes)

    def rotate_key(self, reviewer_id: str, old_key_id: str) -> Tuple[str, str]:
        if old_key_id in self._keys:
            self._keys[old_key_id]["rotated"] = True
        return self.generate_and_store_key(reviewer_id, is_test_key=True)

    def revoke_key(self, reviewer_id: str, public_key_id: str, reason: str) -> None:
        key = self._keys.get(public_key_id)
        if not key:
            raise KeyNotFoundError(f"Ephemeral key '{public_key_id}' not found.")
        key["revoked"] = True
        key["revocation_reason"] = reason

