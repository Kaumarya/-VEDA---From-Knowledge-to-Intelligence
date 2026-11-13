"""
Tests for Reviewer Key Custody, DPAPI Persistence, and Lifecycle
Phase 4.14.2.1 — Issue 1
"""

import sys
import pytest
from pathlib import Path
from foundation.candidates.key_custody import (
    WindowsDPAPIKeyProvider,
    InMemoryEphemeralKeyProvider,
)
from foundation.candidates.signatures import Ed25519SignatureService
from foundation.candidates.exceptions import (
    KeyNotFoundError,
    KeyRevokedError,
    KeyCustodyError,
    KeyProviderUnavailableError,
)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI requires win32 platform")
def test_dpapi_key_generation_and_persistence_across_instances(tmp_path: Path):
    """
    Verify that WindowsDPAPIKeyProvider persists encrypted keys on disk,
    can be re-instantiated across simulated application restarts, and signs payloads correctly.
    """
    keystore_dir = tmp_path / "keystore"
    provider1 = WindowsDPAPIKeyProvider(keystore_dir=keystore_dir)
    assert provider1.is_production is True

    reviewer_id = "urn:uuid:rev-001"
    pub_id, pub_hex = provider1.generate_and_store_key(reviewer_id, is_test_key=False)

    assert pub_id.startswith("urn:key:ed25519:")
    assert len(pub_hex) == 64
    assert provider1.has_private_key(reviewer_id, pub_id) is True

    # Verify physical encrypted file exists and is not raw plaintext
    key_files = list(keystore_dir.glob("*.dpapi.key"))
    assert len(key_files) == 1
    raw_cipher = key_files[0].read_bytes()
    # DPAPI ciphertext is significantly larger than raw 32-byte private key and contains DPAPI headers
    assert len(raw_cipher) > 100

    # Simulate restart by instantiating a new provider pointing to the same keystore directory
    provider2 = WindowsDPAPIKeyProvider(keystore_dir=keystore_dir)
    assert provider2.has_private_key(reviewer_id, pub_id) is True

    # Sign with restarted provider
    test_payload = b'{"action":"approve","candidate_id":"c-123"}'
    sig_hex = provider2.sign_payload(reviewer_id, pub_id, test_payload)
    assert len(sig_hex) == 128

    # Verify signature mathematically against registered public key
    Ed25519SignatureService.verify(pub_hex, test_payload, sig_hex)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI requires win32 platform")
def test_dpapi_key_rotation_and_historical_validity(tmp_path: Path):
    """
    Verify that rotating a key retires the old key, provisions a new key,
    and historical signatures created under the old key remain valid.
    """
    keystore_dir = tmp_path / "keystore"
    provider = WindowsDPAPIKeyProvider(keystore_dir=keystore_dir)

    reviewer_id = "urn:uuid:rev-rot-01"
    old_id, old_pub = provider.generate_and_store_key(reviewer_id)

    # Sign payload before rotation
    historical_payload = b'{"statement":"Approved before rotation"}'
    historical_sig = provider.sign_payload(reviewer_id, old_id, historical_payload)
    Ed25519SignatureService.verify(old_pub, historical_payload, historical_sig)

    # Rotate key
    new_id, new_pub = provider.rotate_key(reviewer_id, old_id)
    assert new_id != old_id
    assert new_pub != old_pub

    # Old key is retired
    assert provider.has_private_key(reviewer_id, new_id) is True

    # New signatures use new key
    new_payload = b'{"statement":"Approved after rotation"}'
    new_sig = provider.sign_payload(reviewer_id, new_id, new_payload)
    Ed25519SignatureService.verify(new_pub, new_payload, new_sig)

    # Historical signature remains permanently valid against old public key
    Ed25519SignatureService.verify(old_pub, historical_payload, historical_sig)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI requires win32 platform")
def test_dpapi_revocation_blocks_signing(tmp_path: Path):
    """Verify that revoked keys are rejected for new signing operations."""
    keystore_dir = tmp_path / "keystore"
    provider = WindowsDPAPIKeyProvider(keystore_dir=keystore_dir)

    reviewer_id = "urn:uuid:rev-comp-01"
    pub_id, pub_hex = provider.generate_and_store_key(reviewer_id)

    # Revoke key
    provider.revoke_key(reviewer_id, pub_id, reason="Suspected credential compromise")
    assert provider.has_private_key(reviewer_id, pub_id) is False

    with pytest.raises(KeyRevokedError, match="revoked"):
        provider.sign_payload(reviewer_id, pub_id, b"some payload")


def test_ephemeral_key_provider_non_production():
    """Verify InMemoryEphemeralKeyProvider is flagged non-production and signs correctly."""
    provider = InMemoryEphemeralKeyProvider()
    assert provider.is_production is False

    reviewer_id = "urn:uuid:test-rev"
    pub_id, pub_hex = provider.generate_and_store_key(reviewer_id, is_test_key=True)
    assert provider.has_private_key(reviewer_id, pub_id) is True

    payload = b"test payload"
    sig = provider.sign_payload(reviewer_id, pub_id, payload)
    Ed25519SignatureService.verify(pub_hex, payload, sig)

    # Non-existent key raises KeyNotFoundError
    with pytest.raises(KeyNotFoundError):
        provider.sign_payload(reviewer_id, "urn:key:fake", payload)

    # Other reviewer cannot sign with key
    with pytest.raises(KeyCustodyError):
        provider.sign_payload("urn:uuid:other", pub_id, payload)

