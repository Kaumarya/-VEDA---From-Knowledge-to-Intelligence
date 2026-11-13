"""
VEDA Candidate Database Subsystem — RFC 8785 Canonical Serialization & Ed25519 Signatures
Phase 4.14.2
"""

import json
import math
import hashlib
from typing import Dict, Any, Tuple, Optional
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from foundation.candidates.exceptions import CryptographicError, InvalidSignatureError


def rfc8785_serialize_string(s: str) -> bytes:
    chunks = ['"']
    for c in s:
        code = ord(c)
        if c == '"':
            chunks.append('\\"')
        elif c == '\\':
            chunks.append('\\\\')
        elif c == '\b':
            chunks.append('\\b')
        elif c == '\f':
            chunks.append('\\f')
        elif c == '\n':
            chunks.append('\\n')
        elif c == '\r':
            chunks.append('\\r')
        elif c == '\t':
            chunks.append('\\t')
        elif code < 0x20:
            chunks.append(f"\\u{code:04x}")
        else:
            chunks.append(c)
    chunks.append('"')
    return "".join(chunks).encode("utf-8")


def rfc8785_format_number(v: float) -> str:
    if math.isnan(v) or math.isinf(v):
        raise ValueError("NaN and Infinity are not valid in RFC 8785 JSON")
    if v == 0.0:
        return "0"

    s = repr(v)
    if "e" in s or "E" in s:
        parts = s.lower().split("e")
        mantissa = parts[0]
        exp = parts[1]
        sign = exp[0]
        if sign == "+":
            exp_val = exp[1:].lstrip("0") or "0"
            return f"{mantissa}e{exp_val}"
        elif sign == "-":
            exp_val = exp[1:].lstrip("0") or "0"
            return f"{mantissa}e-{exp_val}"
        else:
            exp_val = exp.lstrip("0") or "0"
            return f"{mantissa}e{exp_val}"
    else:
        if v.is_integer() and abs(v) < 1e21:
            return str(int(v))
        return s


def canonicalize_rfc8785(obj: Any) -> bytes:
    """
    Serializes an object into deterministic canonical JSON adhering strictly to RFC 8785 (JCS).
    Lexicographical key sorting by UTF-16 code units, no whitespace outside strings, UTF-8 encoding.
    """
    if obj is None:
        return b"null"
    elif isinstance(obj, bool):
        return b"true" if obj else b"false"
    elif isinstance(obj, int):
        return str(obj).encode("utf-8")
    elif isinstance(obj, float):
        return rfc8785_format_number(obj).encode("utf-8")
    elif isinstance(obj, str):
        return rfc8785_serialize_string(obj)
    elif isinstance(obj, (list, tuple)):
        return b"[" + b",".join(canonicalize_rfc8785(x) for x in obj) + b"]"
    elif isinstance(obj, dict):
        sorted_keys = sorted(obj.keys(), key=lambda k: k.encode("utf-16-be"))
        parts = []
        for k in sorted_keys:
            if not isinstance(k, str):
                raise TypeError(f"Dictionary keys must be strings, got {type(k)}")
            parts.append(rfc8785_serialize_string(k) + b":" + canonicalize_rfc8785(obj[k]))
        return b"{" + b",".join(parts) + b"}"
    else:
        raise TypeError(f"Type {type(obj)} is not JSON serializable under RFC 8785")


def canonicalize_json(payload: Dict[str, Any], version: str = "RFC8785_V2") -> bytes:
    """
    Serializes a dictionary into deterministic canonical JSON.
    Supports RFC8785_V2 (strict RFC 8785) and LEGACY_V1 (historical signatures).
    """
    try:
        if version == "RFC8785_V2":
            return canonicalize_rfc8785(payload)
        elif version == "LEGACY_V1":
            return json.dumps(
                payload,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        else:
            raise CryptographicError(f"Unsupported canonicalization version: '{version}'. Must be RFC8785_V2 or LEGACY_V1.")
    except Exception as e:
        if isinstance(e, CryptographicError):
            raise
        raise CryptographicError(f"Failed to canonicalize JSON payload: {e}") from e


def compute_payload_hash(canonical_bytes: bytes) -> str:
    """Computes SHA-256 lowercase hex hash over canonical payload bytes."""
    return hashlib.sha256(canonical_bytes).hexdigest()


class Ed25519SignatureService:
    """
    Handles Ed25519 key generation, signing, and signature verification.
    Uses cryptography library (RFC 8032 compliant).
    """

    @classmethod
    def generate_key_pair(cls) -> Tuple[bytes, str]:
        """
        Generates a new Ed25519 key pair.
        Returns: (private_key_pem_bytes, public_key_hex_string)
        """
        private_key = ed25519.Ed25519PrivateKey.generate()
        pem_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_key = private_key.public_key()
        raw_pub_bytes = pub_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        public_key_hex = raw_pub_bytes.hex().lower()
        return pem_bytes, public_key_hex

    @classmethod
    def sign(cls, private_key_pem: bytes, canonical_bytes: bytes) -> str:
        """
        Signs canonical payload bytes with Ed25519 private key.
        Returns: 128-character lowercase hex signature string (64 bytes).
        """
        try:
            private_key = serialization.load_pem_private_key(private_key_pem, password=None)
            if not isinstance(private_key, ed25519.Ed25519PrivateKey):
                raise CryptographicError("Private key must be Ed25519.")
            sig_bytes = private_key.sign(canonical_bytes)
            return sig_bytes.hex().lower()
        except Exception as e:
            if isinstance(e, CryptographicError):
                raise
            raise CryptographicError(f"Failed to create Ed25519 signature: {e}") from e

    @classmethod
    def verify(cls, public_key_hex: str, canonical_bytes: bytes, signature_hex: str) -> bool:
        """
        Verifies Ed25519 signature over canonical payload bytes.
        Returns: True if valid; raises InvalidSignatureError if invalid.
        """
        try:
            raw_pub = bytes.fromhex(public_key_hex)
            if len(raw_pub) != 32:
                raise CryptographicError("Public key hex must be exactly 32 bytes (64 hex characters).")
            sig_bytes = bytes.fromhex(signature_hex)
            if len(sig_bytes) != 64:
                raise CryptographicError("Signature hex must be exactly 64 bytes (128 hex characters).")

            public_key = ed25519.Ed25519PublicKey.from_public_bytes(raw_pub)
            public_key.verify(sig_bytes, canonical_bytes)
            return True
        except Exception as e:
            raise InvalidSignatureError(f"Cryptographic signature verification failed: {e}") from e

    @classmethod
    def build_canonical_approval_payload(
        cls,
        candidate_id: str,
        decision_id: str,
        decision: str,
        decision_reason: str,
        decision_timestamp: str,
        normalized_content_hash: str,
        source_id: str,
        source_artifact_sha256: str,
        reviewer_id: str,
        reviewer_role: str,
        pipeline_version: str = "v0.4.14",
        payload_schema_version: str = "1.0",
        quarantine_case_id: str = "",
        canonicalization_version: str = "RFC8785_V2",
    ) -> Dict[str, Any]:
        """
        Constructs the authoritative dictionary for canonical serialization.
        """
        payload: Dict[str, Any] = {
            "canonicalization_version": canonicalization_version,
            "candidate_id": candidate_id,
            "decision": decision,
            "decision_id": decision_id,
            "decision_reason": decision_reason,
            "decision_timestamp": decision_timestamp,
            "normalized_content_hash": normalized_content_hash,
            "payload_schema_version": payload_schema_version,
            "pipeline_version": pipeline_version,
            "reviewer_id": reviewer_id,
            "reviewer_role": reviewer_role,
            "source_artifact_sha256": source_artifact_sha256,
            "source_id": source_id,
        }
        if quarantine_case_id:
            payload["quarantine_case_id"] = quarantine_case_id
        return payload

