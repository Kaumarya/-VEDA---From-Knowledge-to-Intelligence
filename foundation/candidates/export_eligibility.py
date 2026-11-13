"""
VEDA Candidate Database Subsystem — Centralized Export Eligibility & Batch Subsystem
Phase 4.14.2
Enforces 18-point fail-closed predicate, SourceRegistry validation, and release-scoped idempotency.
"""

import json
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.models import ExportBatchRecord, CandidateSubmission
from foundation.candidates.exceptions import (
    ExportEligibilityError,
    GovernancePreflightError,
    DuplicateExportError,
    ValidationError,
)
from foundation.candidates.signatures import (
    Ed25519SignatureService,
    compute_payload_hash,
    canonicalize_json,
)
from foundation.corpus.sources import SourceRegistry, LicensingStatus


class ExportEligibilityService:
    """
    Centralized service evaluating production export eligibility.
    Coordinates between database view v_export_eligible_candidates and
    authoritative SourceRegistry.
    Guarantees fail-closed governance: zero unapproved, quarantined, or disputed candidates can be exported.
    """

    def __init__(
        self,
        connection: CandidateDatabaseConnection,
        repository: CandidateRepository,
        source_registry_path: Path = Path("data/corpus/source_registry.json"),
    ):
        self.conn = connection
        self.repo = repository
        self.source_registry_path = source_registry_path
        self._cached_registry: Optional[SourceRegistry] = None
        self._registry_hash: Optional[str] = None
        self._registry_mtime: Optional[float] = None

    def _get_authoritative_registry(self) -> SourceRegistry:
        """
        Loads and caches the authoritative SourceRegistry using cryptographic SHA-256
        content-hash validation. Treats mtime as optional metadata only.
        """
        if not self.source_registry_path.exists():
            raise GovernancePreflightError(
                f"CRITICAL: Authoritative source registry not found at {self.source_registry_path}."
            )
        try:
            raw_bytes = self.source_registry_path.read_bytes()
        except OSError as e:
            raise GovernancePreflightError(
                f"Failed to read source registry at {self.source_registry_path}: {e}"
            ) from e

        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        if self._cached_registry is not None and self._registry_hash == content_hash:
            return self._cached_registry

        try:
            registry = SourceRegistry.load_from_json(self.source_registry_path)
            self._cached_registry = registry
            self._registry_hash = content_hash
            self._registry_mtime = self.source_registry_path.stat().st_mtime
            return self._cached_registry
        except Exception as e:
            raise GovernancePreflightError(
                f"Failed to parse source registry at {self.source_registry_path}: {e}"
            ) from e

    def verify_source_governance_preflight(self, source_id: str) -> None:
        """
        Validates source permissions against the authoritative SourceRegistry.
        Detects cache staleness, missing sources, expired approvals, or revoked licensing.
        """
        registry = self._get_authoritative_registry()
        # SourceRegistry.sources is a list of CorpusSource
        matching = [s for s in registry.sources if s.source_id == source_id]
        if not matching:
            raise GovernancePreflightError(
                f"Source '{source_id}' does not exist in authoritative SourceRegistry."
            )
        auth_source = matching[0]

        if auth_source.licensing_status != LicensingStatus.VERIFIED_PERMITTED:
            raise GovernancePreflightError(
                f"Source '{source_id}' licensing is '{auth_source.licensing_status}'; must be VERIFIED PERMITTED."
            )

        if auth_source.approval_expiration_date:
            now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if auth_source.approval_expiration_date < now_date:
                raise GovernancePreflightError(
                    f"Source '{source_id}' approval expired on {auth_source.approval_expiration_date}."
                )

        # Check DB cache consistency
        db_src = self.repo.get_source(source_id)
        if not db_src:
            raise GovernancePreflightError(f"Source '{source_id}' missing in candidate database cache.")

        if db_src.artifact_sha256 != auth_source.artifact_sha256:
            raise GovernancePreflightError(
                f"Source '{source_id}' artifact SHA-256 mismatch between DB cache and authoritative registry."
            )

        if db_src.licensing_status != "VERIFIED PERMITTED":
            raise GovernancePreflightError(
                f"Source '{source_id}' DB licensing status is '{db_src.licensing_status}'; must be VERIFIED PERMITTED."
            )

        if db_src.training_permitted_status != "EXPLICITLY_PERMITTED":
            raise GovernancePreflightError(
                f"Source '{source_id}' DB training status is '{db_src.training_permitted_status}'; must be EXPLICITLY_PERMITTED."
            )

    def check_candidate_eligibility(self, candidate_id: str, verify_source: bool = True) -> bool:
        """
        Evaluates the comprehensive 18-point fail-closed export eligibility predicate.
        Cryptographically re-verifies digital signatures at SQLite trust boundaries.
        Returns True if eligible; raises ExportEligibilityError with exact cause if ineligible.
        """
        row = self.conn.fetchone(
            "SELECT * FROM v_export_eligible_candidates WHERE candidate_id = ?;",
            (candidate_id,),
        )
        if not row:
            # Query candidate to identify exact reason for failure
            cand = self.repo.get_candidate(candidate_id)
            if not cand:
                raise ExportEligibilityError(f"Candidate '{candidate_id}' does not exist.")
            if not cand.is_canonical:
                raise ExportEligibilityError(f"Candidate '{candidate_id}' is a non-canonical duplicate.")
            if cand.processing_status != "APPROVED":
                raise ExportEligibilityError(
                    f"Candidate '{candidate_id}' status is '{cand.processing_status}'; must be 'APPROVED'."
                )

            # Check if signed with test key
            test_key_row = self.conn.fetchone(
                """
                SELECT k.is_test_key FROM approval_history ah
                JOIN reviewer_public_keys k ON ah.public_key_id = k.public_key_id
                WHERE ah.candidate_id = ? AND ah.new_status = 'APPROVED'
                LIMIT 1;
                """,
                (candidate_id,),
            )
            if test_key_row and test_key_row["is_test_key"] == 1:
                raise ExportEligibilityError(f"Candidate '{candidate_id}' was approved with a test key (is_test_key = 1).")

            # Check quarantine status
            q_row = self.conn.fetchone(
                "SELECT case_id FROM quarantine_cases WHERE candidate_id = ? AND resolution_decision_id IS NULL;",
                (candidate_id,),
            )
            if q_row:
                raise ExportEligibilityError(f"Candidate '{candidate_id}' has unresolved quarantine case {q_row['case_id']}.")

            raise ExportEligibilityError(
                f"Candidate '{candidate_id}' failed export eligibility predicate (check approval signature, source licensing, or legal retention)."
            )

        # Application-level cryptographic re-verification at SQLite trust boundary
        ah_row = self.conn.fetchone(
            """
            SELECT ah.canonical_payload_json, ah.signature_ed25519, ah.canonical_payload_sha256,
                   ah.reviewer_id, ah.public_key_id,
                   k.public_key_hex, k.key_status, k.is_test_key
            FROM approval_history ah
            JOIN reviewer_public_keys k ON ah.public_key_id = k.public_key_id
            WHERE ah.candidate_id = ? AND ah.new_status = 'APPROVED'
            ORDER BY ah.created_at DESC
            LIMIT 1;
            """,
            (candidate_id,),
        )
        if not ah_row:
            raise ExportEligibilityError(f"Candidate '{candidate_id}' lacks approved history record.")
        if ah_row["is_test_key"] == 1:
            raise ExportEligibilityError(f"Candidate '{candidate_id}' was approved with a test key.")

        # Parse canonical approval payload
        try:
            payload = json.loads(ah_row["canonical_payload_json"])
        except Exception as e:
            raise ExportEligibilityError(f"Corrupted canonical approval payload JSON for candidate '{candidate_id}': {e}") from e

        # 1. Canonicalization Version Handling & Payload Integrity
        canon_version = payload.get("canonicalization_version", "LEGACY_V1")
        if canon_version not in ("LEGACY_V1", "RFC8785_V2"):
            raise ExportEligibilityError(f"Unsupported canonicalization version '{canon_version}' in approval payload.")

        try:
            canonical_bytes = canonicalize_json(payload, version=canon_version)
            calc_hash = compute_payload_hash(canonical_bytes)
            if calc_hash != ah_row["canonical_payload_sha256"]:
                raise ExportEligibilityError(f"Canonical payload SHA-256 mismatch for candidate '{candidate_id}'.")
            Ed25519SignatureService.verify(
                ah_row["public_key_hex"],
                canonical_bytes,
                ah_row["signature_ed25519"],
            )
        except Exception as e:
            if isinstance(e, ExportEligibilityError):
                raise
            raise ExportEligibilityError(f"Cryptographic signature re-verification failed at export trust boundary: {e}") from e

        # 2. Strict Content-Hash Binding (Part 3)
        cand = self.repo.get_candidate(candidate_id)
        if not cand:
            raise ExportEligibilityError(f"Candidate '{candidate_id}' missing in repository during export validation.")

        # Independently recompute normalized text SHA-256
        recomputed_norm_hash = hashlib.sha256(cand.normalized_text.encode("utf-8")).hexdigest()

        # Compare recomputed hash against candidate_submissions table hash
        if recomputed_norm_hash != cand.normalized_content_hash:
            raise ExportEligibilityError(
                f"Candidate content tampering detected: recomputed normalized text hash ({recomputed_norm_hash}) "
                f"does not match candidate table normalized_content_hash ({cand.normalized_content_hash})."
            )

        # Compare recomputed hash against signed approval payload hash
        payload_norm_hash = payload.get("normalized_content_hash")
        if recomputed_norm_hash != payload_norm_hash:
            raise ExportEligibilityError(
                f"Candidate content decoupling detected: recomputed normalized text hash ({recomputed_norm_hash}) "
                f"does not match signed approval payload hash ({payload_norm_hash})."
            )

        # Verify raw content hash if original text is present and unredacted
        if cand.original_text and cand.raw_content_hash and not cand.original_text.startswith("["):
            recomputed_raw_hash = hashlib.sha256(cand.original_text.encode("utf-8")).hexdigest()
            if recomputed_raw_hash != cand.raw_content_hash:
                raise ExportEligibilityError(
                    f"Candidate raw content tampering detected: recomputed original text hash ({recomputed_raw_hash}) "
                    f"does not match candidate raw_content_hash ({cand.raw_content_hash})."
                )

        # 3. Payload Metadata Binding Checks
        if payload.get("candidate_id") != candidate_id:
            raise ExportEligibilityError(
                f"Candidate ID decoupling: payload candidate_id '{payload.get('candidate_id')}' != '{candidate_id}'."
            )
        if payload.get("source_id") != cand.source_id:
            raise ExportEligibilityError(
                f"Source ID decoupling: payload source_id '{payload.get('source_id')}' != candidate source_id '{cand.source_id}'."
            )
        if payload.get("decision") != "APPROVED":
            raise ExportEligibilityError(
                f"Invalid approval decision in payload: expected 'APPROVED', found '{payload.get('decision')}'."
            )
        if payload.get("reviewer_id") != ah_row["reviewer_id"]:
            raise ExportEligibilityError("Reviewer identity in signed payload does not match approval record.")

        # 4. Source Governance & Artifact Binding Preflight
        if verify_source:
            self.verify_source_governance_preflight(cand.source_id)
            reg = self._get_authoritative_registry()
            matching = [s for s in reg.sources if s.source_id == cand.source_id]
            if matching:
                auth_src = matching[0]
                if payload.get("source_artifact_sha256") != auth_src.artifact_sha256:
                    raise ExportEligibilityError(
                        f"Source artifact hash mismatch: payload bound to {payload.get('source_artifact_sha256')}, "
                        f"authoritative source registry is {auth_src.artifact_sha256}."
                    )

        return True

    def list_eligible_candidates(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """Returns rows from v_export_eligible_candidates."""
        rows = self.conn.fetchall(
            "SELECT * FROM v_export_eligible_candidates LIMIT ? OFFSET ?;",
            (limit, offset),
        )
        return [dict(r) for r in rows]

    def create_export_batch(self, corpus_version: str, target_split: str) -> ExportBatchRecord:
        """Initializes a new export batch in PREPARING status."""
        if target_split not in ("train", "dev", "test"):
            raise ValidationError(f"Invalid target_split '{target_split}'; must be train, dev, or test.")

        batch_id = f"urn:uuid:{uuid.uuid4()}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO export_batches (batch_id, corpus_version, target_split, record_count, export_status, created_at)
                VALUES (?, ?, ?, 0, 'PREPARING', ?);
                """,
                (batch_id, corpus_version, target_split, now_iso),
            )
        return ExportBatchRecord(
            batch_id=batch_id,
            corpus_version=corpus_version,
            target_split=target_split,
            record_count=0,
            export_status="PREPARING",
            created_at=now_iso,
        )

    def add_candidate_to_batch(self, batch_id: str, candidate_id: str, verify_source: bool = True) -> None:
        """
        Validates candidate eligibility and release-scoped idempotency before adding to batch.
        """
        batch = self.get_export_batch(batch_id)
        if not batch:
            raise ValidationError(f"Export batch '{batch_id}' not found.")
        if batch.export_status != "PREPARING":
            raise ValidationError(f"Export batch '{batch_id}' is '{batch.export_status}'; cannot add items.")

        # 1. Verify eligibility
        self.check_candidate_eligibility(candidate_id, verify_source=verify_source)

        cand = self.repo.get_candidate(candidate_id)
        assert cand is not None

        # 2. Enforce Release-Scoped Idempotency
        # Check if this candidate is already exported to this same corpus_version and target_split
        existing_export = self.conn.fetchone(
            """
            SELECT eb.batch_id, eb.corpus_version, eb.target_split
            FROM export_batch_items ebi
            JOIN export_batches eb ON ebi.batch_id = eb.batch_id
            WHERE ebi.candidate_id = ? 
              AND eb.corpus_version = ? 
              AND eb.target_split = ?
              AND eb.export_status IN ('PREPARING', 'COMMITTED');
            """,
            (candidate_id, batch.corpus_version, batch.target_split),
        )
        if existing_export:
            raise DuplicateExportError(
                f"Candidate '{candidate_id}' is already exported to release '{batch.corpus_version}' split '{batch.target_split}' (batch {existing_export['batch_id']})."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO export_batch_items (batch_id, candidate_id, normalized_content_hash, exported_at)
                VALUES (?, ?, ?, ?);
                """,
                (batch_id, candidate_id, cand.normalized_content_hash, now_iso),
            )
            c.execute(
                "UPDATE export_batches SET record_count = record_count + 1 WHERE batch_id = ?;",
                (batch_id,),
            )

    def commit_export_batch(self, batch_id: str, manifest_sha256: str, output_path: str) -> ExportBatchRecord:
        """Commits an export batch after successful filesystem write."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                """
                UPDATE export_batches 
                SET export_status = 'COMMITTED', manifest_sha256 = ?, output_path = ?, committed_at = ?
                WHERE batch_id = ?;
                """,
                (manifest_sha256, output_path, now_iso, batch_id),
            )
        return self.get_export_batch(batch_id)

    def fail_export_batch(self, batch_id: str) -> None:
        """Marks an export batch as FAILED during crash recovery."""
        with self.conn.transaction() as c:
            c.execute("UPDATE export_batches SET export_status = 'FAILED' WHERE batch_id = ?;", (batch_id,))

    def get_export_batch(self, batch_id: str) -> Optional[ExportBatchRecord]:
        """Retrieves export batch metadata."""
        row = self.conn.fetchone("SELECT * FROM export_batches WHERE batch_id = ?;", (batch_id,))
        if not row:
            return None
        return ExportBatchRecord(
            batch_id=row["batch_id"],
            corpus_version=row["corpus_version"],
            target_split=row["target_split"],
            record_count=row["record_count"],
            export_status=row["export_status"],
            manifest_sha256=row["manifest_sha256"],
            output_path=row["output_path"],
            created_at=row["created_at"],
            committed_at=row["committed_at"],
        )

