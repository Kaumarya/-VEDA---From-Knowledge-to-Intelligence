"""
Tests for RFC 8785 JSON Canonicalization Scheme (JCS) Compliance & Historical Compatibility
Phase 4.14.2.1.2 — Issue 6 & Issue 8
"""

import json
import pytest

from foundation.candidates.signatures import (
    canonicalize_json,
    canonicalize_rfc8785,
    compute_payload_hash,
    Ed25519SignatureService,
)
from foundation.candidates.exceptions import CryptographicError


def test_rfc8785_utf16_surrogate_key_sorting():
    """
    RFC 8785 Section 3.2.3 requires key sorting by UTF-16 code units.
    Characters outside BMP (e.g. U+10000) have surrogate pair (0xD800, 0xDC00),
    which sorts before U+FFFF (0xFFFF), unlike Python code-point order.
    """
    d = {"\uFFFF": "bmp_high", "\U00010000": "non_bmp_surrogate"}
    canonical = canonicalize_rfc8785(d)
    # In UTF-16 BE, \U00010000 is 0xD800 0xDC00 < 0xFFFF
    # So \U00010000 must come FIRST!
    decoded = canonical.decode("utf-8")
    assert decoded.startswith('{"\U00010000":'), f"Expected surrogate key first, got {decoded}"


def test_rfc8785_negative_zero_serialization():
    """RFC 8785 Section 3.2.2.3 requires -0.0 and 0.0 to serialize as '0'."""
    assert canonicalize_rfc8785(-0.0) == b"0"
    assert canonicalize_rfc8785(0.0) == b"0"
    assert canonicalize_rfc8785({"val": -0.0}) == b'{"val":0}'


def test_rfc8785_floating_point_exponent_notation():
    """RFC 8785 Section 3.2.2.3 prohibits '+' sign in exponent notation (e.g. '1e21', not '1e+21')."""
    assert canonicalize_rfc8785(1e21) == b"1e21"
    assert canonicalize_rfc8785(1e-7) == b"1e-7"
    assert canonicalize_rfc8785({"large": 1e21, "small": 1e-7}) == b'{"large":1e21,"small":1e-7}'


def test_rfc8785_integers_and_exact_floats():
    """Floats representing exact integers serialize as integer strings."""
    assert canonicalize_rfc8785(10.0) == b"10"
    assert canonicalize_rfc8785(100) == b"100"
    assert canonicalize_rfc8785(-42) == b"-42"


def test_rfc8785_nan_and_infinity_rejected():
    """RFC 8785 prohibits NaN and Infinity in JSON."""
    with pytest.raises(CryptographicError):
        canonicalize_json({"val": float("nan")})
    with pytest.raises(CryptographicError):
        canonicalize_json({"val": float("inf")})


def test_rfc8785_nested_structures_and_whitespace():
    """RFC 8785 strictly strips all whitespace outside strings."""
    payload = {
        "b": [1, 2, {"nested": True}],
        "a": "hello world",
        "c": None,
        "d": False,
    }
    canonical = canonicalize_json(payload, version="RFC8785_V2")
    expected = b'{"a":"hello world","b":[1,2,{"nested":true}],"c":null,"d":false}'
    assert canonical == expected


def test_historical_signature_verification_backwards_compatibility():
    """
    Ensures that historical approval signatures created under LEGACY_V1
    continue to verify correctly without recanonicalizing.
    """
    priv_pem, pub_hex = Ed25519SignatureService.generate_key_pair()

    legacy_payload = {
        "candidate_id": "cand_hist_01",
        "decision": "APPROVED",
        "canonicalization_version": "LEGACY_V1",
        "reviewer_id": "rev_01",
    }
    # Sign with LEGACY_V1
    legacy_bytes = canonicalize_json(legacy_payload, version="LEGACY_V1")
    legacy_sig = Ed25519SignatureService.sign(priv_pem, legacy_bytes)

    # Verify with LEGACY_V1 succeeds
    assert Ed25519SignatureService.verify(pub_hex, legacy_bytes, legacy_sig) is True


def test_unsupported_canonicalization_version_fails_closed():
    """Unsupported canonicalization versions must be rejected."""
    with pytest.raises(CryptographicError, match="Unsupported canonicalization version"):
        canonicalize_json({"data": 123}, version="UNSUPPORTED_V99")
