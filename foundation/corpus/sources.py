"""
VEDA Source Registry Management (Phase 4.2 — Training Source Selection & Governance)

Provides a machine-readable, strongly-typed source registry implementation for
evaluating, cataloging, validating, and querying candidate training sources
under VEDA's strict four-state licensing governance model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from foundation.corpus.schemas import CorpusSource, LicensingStatus


class GovernanceGateError(RuntimeError):
    """Authoritative error raised when an unapproved, unverified, or non-compliant source attempts ingestion."""
    pass


class StaleApprovalError(GovernanceGateError):
    """Raised when a source approval has expired or passed its re-review trigger date."""
    pass


class UnapprovedSourceError(GovernanceGateError):
    """Raised when a source is not in VERIFIED_PERMITTED state or not found in registry."""
    pass


class SourceRegistry:
    """
    Authoritative catalog of external training corpus sources.
    Enforces governance boundaries and provides structured auditing of
    licenses, provenance, checksums, and machine learning training eligibility.

    NOTICE:
    The VEDA Data Governance Engine is an automated engineering gating system
    and technical provenance ledger. It does not constitute legal advice,
    a formal legal opinion, or an absolute legal determination of copyright status.
    """

    def __init__(self, sources: Optional[List[CorpusSource]] = None) -> None:
        self._sources: Dict[str, CorpusSource] = {}
        if sources:
            for s in sources:
                self.register(s)

    def register(self, source: CorpusSource) -> None:
        """Registers a candidate source in the registry."""
        if not isinstance(source, CorpusSource):
            raise TypeError(f"Expected CorpusSource instance, got {type(source).__name__}")
        if source.source_id in self._sources:
            raise ValueError(f"Duplicate source_id in registry: {source.source_id!r}")
        self._sources[source.source_id] = source

    def get(self, source_id: str) -> Optional[CorpusSource]:
        """Retrieves a source by its stable source_id."""
        return self._sources.get(source_id)

    def __getitem__(self, source_id: str) -> CorpusSource:
        src = self.get(source_id)
        if src is None:
            raise KeyError(f"Source {source_id!r} not found in SourceRegistry")
        return src

    def __len__(self) -> int:
        return len(self._sources)

    def __iter__(self):
        return iter(self._sources.values())

    @property
    def sources(self) -> List[CorpusSource]:
        """Returns sorted list of all registered sources."""
        return sorted(self._sources.values(), key=lambda s: s.source_id)

    def permitted_sources(self) -> List[CorpusSource]:
        """Returns only sources with active VERIFIED_PERMITTED governance status."""
        return [
            s for s in self.sources
            if s.is_permitted_for_training
        ]

    def sources_by_status(self, status: Union[LicensingStatus, str]) -> List[CorpusSource]:
        """Filters sources by exact governance state."""
        target_status = LicensingStatus(status) if not isinstance(status, LicensingStatus) else status
        return [s for s in self.sources if s.licensing_status == target_status]

    def validate_source_governance(self, source: CorpusSource, strict_evidence: bool = False) -> List[str]:
        """
        Conducts audit checks against source governance requirements.
        Returns a list of issue descriptions (empty list if fully compliant).
        """
        issues: List[str] = []
        if not source.name or not source.version:
            issues.append("Missing source name or version identifier")
        if not source.url_or_path or not source.url_or_path.startswith("http"):
            issues.append("Source URL must be an official HTTP/HTTPS URL")
        if not source.license:
            issues.append("License name must be specified")
        if not source.license_url:
            issues.append("Official license URL must be provided")
        if source.source_hash != "NOT_VERIFIED" and len(source.source_hash) != 64:
            issues.append("Source checksum must be a 64-character SHA-256 hash or 'NOT_VERIFIED'")
        if source.licensing_status not in LicensingStatus:
            issues.append(f"Invalid licensing status: {source.licensing_status}")
        if source.licensing_status == LicensingStatus.EXCLUDED:
            issues.append(f"Source {source.source_id!r} is explicitly EXCLUDED from corpus ingestion")
        if source.licensing_status == LicensingStatus.VERIFIED_PERMITTED:
            art_hash = getattr(source, "artifact_sha256", None) or source.source_hash
            if not art_hash or art_hash in ("NOT_VERIFIED", "NOT_ACQUIRED") or len(art_hash) != 64:
                issues.append("VERIFIED_PERMITTED source cannot have unverified artifact (artifact_sha256='NOT_VERIFIED')")
            elif art_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855":
                issues.append("VERIFIED_PERMITTED source cannot have empty-file artifact_sha256 placeholder")
            if not source.training_permitted_status or source.training_permitted_status != "EXPLICITLY_PERMITTED":
                issues.append("VERIFIED_PERMITTED source must have training_permitted_status='EXPLICITLY_PERMITTED'")
            if source.commercial_permitted is None:
                issues.append("Commercial use permission must be explicitly evaluated (True/False)")
            if not source.attribution:
                issues.append("Missing required attribution notice for source")
            if source.is_approval_stale:
                issues.append(f"Source approval has expired or is stale (expiration: {source.approval_expiration_date})")
            if strict_evidence:
                if not source.evidence_retrieval_date:
                    issues.append("Missing evidence_retrieval_date")
                lic_hash = getattr(source, "license_evidence_sha256", None) or source.evidence_checksum
                if not lic_hash or lic_hash in ("NOT_VERIFIED", "NOT_ACQUIRED") or len(lic_hash) != 64:
                    issues.append("Missing or unverified 64-char evidence_checksum / license_evidence_sha256")
                if not source.reviewer_identity:
                    issues.append("Missing reviewer_identity")
                if not source.review_date:
                    issues.append("Missing review_date")
                if not source.re_review_triggers:
                    issues.append("Missing re_review_triggers")
                if not source.work_level_scope:
                    issues.append("Missing work_level_scope")
        return issues

    def assert_permitted_admissible(self, source: CorpusSource, strict_evidence: bool = True) -> None:
        """
        Enforces that a source is fully verified, non-stale, and legally permitted.
        Raises GovernanceGateError if any gate condition fails.
        """
        if source.licensing_status == LicensingStatus.EXCLUDED:
            raise UnapprovedSourceError(
                f"Source {source.source_id!r} is explicitly EXCLUDED from corpus ingestion."
            )
        if source.licensing_status != LicensingStatus.VERIFIED_PERMITTED:
            raise UnapprovedSourceError(
                f"Source {source.source_id!r} is not permitted for ingestion: "
                f"governance status is {source.licensing_status.value}"
            )
        if source.is_approval_stale:
            raise StaleApprovalError(
                f"Source {source.source_id!r} approval is stale or expired "
                f"(expiration: {source.approval_expiration_date})"
            )
        issues = self.validate_source_governance(source, strict_evidence=strict_evidence)
        if issues:
            raise GovernanceGateError(
                f"Source {source.source_id!r} failed governance audit gates: " + "; ".join(issues)
            )

    def verify_source_integrity(self, candidate: CorpusSource) -> None:
        """
        Verifies that candidate source matches the authoritative registry entry bit-for-bit.
        Prevents tampering with metadata after approval.
        """
        registered = self.get(candidate.source_id)
        if registered is None:
            raise UnapprovedSourceError(f"Source {candidate.source_id!r} is not registered in authoritative registry")
        if candidate.to_dict() != registered.to_dict():
            raise GovernanceGateError(
                f"Source {candidate.source_id!r} metadata has been modified after approval. "
                f"Registry integrity violation."
            )

    def summary(self) -> Dict[str, Any]:
        """Generates statistical and governance summary of the registry."""
        by_status: Dict[str, int] = {st.value: 0 for st in LicensingStatus}
        by_type: Dict[str, int] = {}
        for s in self._sources.values():
            by_status[s.licensing_status.value] = by_status.get(s.licensing_status.value, 0) + 1
            by_type[s.source_type] = by_type.get(s.source_type, 0) + 1

        return {
            "total_registered_sources": len(self._sources),
            "verified_permitted_count": by_status.get(LicensingStatus.VERIFIED_PERMITTED.value, 0),
            "requires_review_count": by_status.get(LicensingStatus.REQUIRES_REVIEW.value, 0),
            "unknown_count": by_status.get(LicensingStatus.UNKNOWN.value, 0),
            "excluded_count": by_status.get(LicensingStatus.EXCLUDED.value, 0),
            "by_status": by_status,
            "by_content_type": by_type,
        }

    @classmethod
    def load_from_json(cls, path: Union[str, Path]) -> SourceRegistry:
        """Loads and parses source registry from JSON file."""
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Source registry file not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_list = data if isinstance(data, list) else data.get("sources", [])
        sources = [CorpusSource.from_dict(item) for item in raw_list]
        return cls(sources)

    def to_json(self, path: Union[str, Path], indent: int = 2) -> None:
        """Serializes registry to formatted JSON."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = [s.to_dict() for s in self.sources]
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, indent=indent, ensure_ascii=False)
