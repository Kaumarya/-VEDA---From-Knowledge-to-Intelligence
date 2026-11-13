"""
Tests for Raw Text Preservation, Byte Contracts, and Legal Retention/Expungement
Phase 4.14.2.1 — Issue 7
"""

import hashlib
from pathlib import Path
import pytest

from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.retention import RetentionManager
from foundation.candidates.models import CandidateSourceRecord
from foundation.candidates.exceptions import ValidationError


@pytest.fixture
def text_env(tmp_path: Path):
    """Sets up an environment for text preservation and retention testing."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        repo = CandidateRepository(db)
        retention = RetentionManager(db)

        repo.upsert_source(
            CandidateSourceRecord(
                source_id="src_text_01",
                name="Text Contract Source",
                version="1.0",
                licensing_status="VERIFIED PERMITTED",
                license_name="CC0-1.0",
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256="3" * 64,
                registry_entry_sha256="4" * 64,
            )
        )

        yield {
            "db": db,
            "repo": repo,
            "retention": retention,
        }


def test_raw_byte_preservation_and_utf8_contract(text_env):
    """
    Verify that raw bytes and raw byte SHA-256 are persisted,
    and combining characters / non-BMP characters are handled deterministically.
    """
    repo = text_env["repo"]

    # Complex Unicode: combining accent (e + combining acute) and non-BMP character (mathematical bold A: U+1D400)
    # Decomposed: 'e\u0301' + '\U0001D400'
    unicode_sample = "cafe\u0301 \U0001D400 model training text."
    raw_bytes = unicode_sample.encode("utf-8")
    expected_byte_sha256 = hashlib.sha256(raw_bytes).hexdigest()

    cand = repo.submit_candidate(
        original_text=unicode_sample,
        source_id="src_text_01",
        source_document_id="doc_unicode_01",
        raw_bytes=raw_bytes,
    )

    assert cand.raw_bytes == raw_bytes
    assert cand.raw_byte_sha256 == expected_byte_sha256
    # Deterministic NFC normalization composes e + \u0301 into single code point 'é'
    import unicodedata
    assert cand.normalized_text == unicodedata.normalize("NFC", cand.normalized_text)

    # Retrieval from DB confirms byte-exact preservation
    fetched = repo.get_candidate(cand.candidate_id)
    assert fetched.raw_bytes == raw_bytes
    assert fetched.raw_byte_sha256 == expected_byte_sha256


def test_mismatched_raw_bytes_rejected(text_env):
    """Verify that providing raw_bytes that do not decode to original_text raises ValidationError."""
    repo = text_env["repo"]

    original_text = "Expected English statement."
    corrupted_bytes = "Completely different text.".encode("utf-8")

    with pytest.raises(ValidationError, match="Supplied raw_bytes decoded with UTF-8 does not match original_text"):
        repo.submit_candidate(
            original_text=original_text,
            source_id="src_text_01",
            source_document_id="doc_err_01",
            raw_bytes=corrupted_bytes,
        )


def test_redact_raw_text_masks_and_nulls_raw_bytes(text_env):
    """
    Verify that redact_raw_text masks original/normalized text and sets raw_bytes to NULL,
    while preserving raw and normalized content hashes for audit integrity.
    """
    repo = text_env["repo"]
    retention = text_env["retention"]

    original = "Verbatim sensitive private statement."
    raw_bytes = original.encode("utf-8")
    cand = repo.submit_candidate(original, "src_text_01", "doc_redact_01", raw_bytes=raw_bytes)

    orig_raw_hash = cand.raw_content_hash
    orig_norm_hash = cand.normalized_content_hash

    # Execute lawful redaction
    retention.redact_raw_text(
        candidate_id=cand.candidate_id,
        authorized_by="legal_counsel_01",
        legal_basis="GDPR Article 17 Right to Erasure Notice #412",
    )

    # Inspect modified candidate record
    updated = repo.get_candidate(cand.candidate_id)
    assert updated.original_text == "[REDACTED UNDER LEGAL ORDER]"
    assert updated.normalized_text == "[REDACTED UNDER LEGAL ORDER]"
    assert updated.raw_bytes is None
    # Cryptographic hashes MUST remain unchanged for audit non-repudiation
    assert updated.raw_content_hash == orig_raw_hash
    assert updated.normalized_content_hash == orig_norm_hash

    # Verify active restriction
    assert retention.has_active_restriction(cand.candidate_id) is True


def test_expunge_under_legal_order_creates_audit_record(text_env):
    """
    Verify that expunge_under_legal_order creates an EXPUNGE_LEGAL_ORDER decision,
    masks text, nulls raw_bytes, and preserves cryptographic hashes.
    """
    repo = text_env["repo"]
    retention = text_env["retention"]
    db = text_env["db"]

    original = "Proprietary third-party trade secret text."
    cand = repo.submit_candidate(original, "src_text_01", "doc_expunge_01")
    orig_raw_hash = cand.raw_content_hash

    retention.expunge_under_legal_order(
        candidate_id=cand.candidate_id,
        authorized_by="chief_compliance_officer",
        legal_basis="Federal Court Injunction Order Case 26-cv-881",
    )

    updated = repo.get_candidate(cand.candidate_id)
    assert updated.original_text == "[EXPUNGED UNDER COURT ORDER]"
    assert updated.normalized_text == "[EXPUNGED UNDER COURT ORDER]"
    assert updated.raw_bytes is None
    assert updated.raw_content_hash == orig_raw_hash

    # Verify retention decision row
    dec_row = db.fetchone(
        "SELECT * FROM retention_decisions WHERE candidate_id = ? AND decision_type = 'EXPUNGE_LEGAL_ORDER';",
        (cand.candidate_id,),
    )
    assert dec_row is not None
    assert "Federal Court Injunction" in dec_row["legal_basis"]

