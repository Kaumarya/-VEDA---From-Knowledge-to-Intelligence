"""
VEDA Corpus Pipeline Orchestrator (Phase 4 — Training Corpus Architecture)

Coordinates the end-to-end execution of the corpus curation pipeline:
Governance Gate → Document Deduplication → Segmentation → Normalization →
Quality Filtering → Record Deduplication → Deterministic Splitting → Storage → Manifest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from foundation.characters.registry import CharacterRegistry
from foundation.corpus.budget import PreflightStorageChecker, ResourceBudgetExceededError
from foundation.corpus.deduplication import DeduplicationEngine
from foundation.corpus.filtering import QualityFilter, load_default_registry
from foundation.corpus.manifest import CorpusManifest, ManifestBuilder
from foundation.corpus.normalization import TextNormalizer
from foundation.corpus.schemas import (
    CorpusDocument,
    CorpusRecord,
    CorpusSource,
    DatasetSplit,
    LicensingStatus,
    RecordProvenance,
    RejectionReason,
    RejectionRecord,
)
from foundation.corpus.segmentation import DocumentSegmenter
from foundation.corpus.sources import (
    GovernanceGateError,
    SourceRegistry,
    StaleApprovalError,
    UnapprovedSourceError,
)
from foundation.corpus.splitting import DeterministicSplitter
from foundation.corpus.storage import CorpusWriter


class CorpusPipeline:
    """
    Controlled, end-to-end corpus generation and curation pipeline.
    """

    VERSION = "0.1.0"

    def __init__(
        self,
        corpus_name: str = "veda_corpus_v0.1",
        corpus_version: str = "0.1.0",
        split_seed: str = DeterministicSplitter.DEFAULT_SEED,
        train_ratio: float = 0.90,
        val_ratio: float = 0.05,
        test_ratio: float = 0.05,
        registry: Optional[CharacterRegistry] = None,
    ) -> None:
        self.corpus_name = corpus_name
        self.corpus_version = corpus_version
        self.split_seed = split_seed

        # Initialize pipeline components
        self.registry = registry
        self.normalizer = TextNormalizer()
        self.quality_filter = QualityFilter(registry=self.registry)
        self.segmenter = DocumentSegmenter()
        self.deduplicator = DeduplicationEngine()
        self.preflight_checker = PreflightStorageChecker()
        self.splitter = DeterministicSplitter(
            seed=split_seed,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
        )

    def process_corpus(
        self,
        sources: List[CorpusSource],
        documents: List[CorpusDocument],
        output_dir: Path,
        strict_governance: bool = False,
        enforce_preflight: bool = False,
        estimated_job_bytes: int = 0,
        source_registry: Optional[SourceRegistry] = None,
    ) -> CorpusManifest:
        """
        Executes the corpus pipeline across provided sources and documents.

        Atomic execution:
        - Commits files only on complete success.
        - Publishes manifest.json only after all splits are sealed and verified.
        - Deletes temporary files if any error occurs.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        # 0. Preflight Disk Space Check (Stops before writing any temporary files)
        if enforce_preflight:
            self.preflight_checker.verify_disk_availability(
                target_path=out_path,
                estimated_job_bytes=estimated_job_bytes,
                enforce=True,
            )

        # 0b. Strict Governance Gate Validation
        if strict_governance:
            for s in sources:
                if source_registry:
                    source_registry.verify_source_integrity(s)
                    source_registry.assert_permitted_admissible(s)
                else:
                    if not s.is_permitted_for_training:
                        raise UnapprovedSourceError(
                            f"Source {s.source_id!r} is not permitted for training (status: {s.licensing_status.value})"
                        )
                    if s.is_approval_stale:
                        raise StaleApprovalError(
                            f"Source {s.source_id!r} approval is stale or expired (expiration: {s.approval_expiration_date})"
                        )

        writer = CorpusWriter(out_path)
        manifest_builder = ManifestBuilder(
            corpus_name=self.corpus_name,
            corpus_version=self.corpus_version,
            split_seed=self.split_seed,
            train_ratio=self.splitter.train_ratio,
            val_ratio=self.splitter.val_ratio,
            test_ratio=self.splitter.test_ratio,
        )
        self.deduplicator.reset()

        # Build lookup for sources
        source_map: Dict[str, CorpusSource] = {s.source_id: s for s in sources}
        source_doc_counts: Dict[str, int] = {s.source_id: 0 for s in sources}

        try:
            for doc in documents:
                source = source_map.get(doc.source_id)
                if source is None:
                    raise ValueError(f"Document {doc.document_id} references unknown source_id {doc.source_id!r}")

                source_doc_counts[source.source_id] += 1

                # 1. Data Governance Gate
                if not source.is_permitted_for_training:
                    rejection = RejectionRecord(
                        record_id=f"{doc.document_id}:gov_rejected",
                        document_id=doc.document_id,
                        source_id=source.source_id,
                        rejection_reason=RejectionReason.GOVERNANCE_BLOCKED,
                        rejection_stage="governance",
                        raw_text_sample=f"Source {source.source_id} licensing status: {source.licensing_status.value}",
                        created_at=source.acquisition_date,
                    )
                    writer.write_rejection(rejection)
                    manifest_builder.observe_rejection(RejectionReason.GOVERNANCE_BLOCKED.value)
                    manifest_builder.rejected_documents += 1
                    continue

                # 2. Document-Level Deduplication
                is_doc_dup, canonical_doc_id = self.deduplicator.check_and_register_document(doc)
                if is_doc_dup:
                    rejection = RejectionRecord(
                        record_id=f"{doc.document_id}:doc_dup",
                        document_id=doc.document_id,
                        source_id=source.source_id,
                        rejection_reason=RejectionReason.DUPLICATE,
                        rejection_stage="deduplication",
                        raw_text_sample=f"Duplicate of document {canonical_doc_id}",
                        created_at=source.acquisition_date,
                    )
                    writer.write_rejection(rejection)
                    manifest_builder.observe_duplicate(dup_type="document")
                    manifest_builder.rejected_documents += 1
                    continue

                # 3. Document-Level Deterministic Split Assignment (Prevents Data Leakage via Related-Work Grouping)
                doc_split = self.splitter.assign_document_split(doc.document_id, group_id=doc.group_id)

                # 4. Document Segmentation
                segments = self.segmenter.segment_document(doc)
                if not segments:
                    rejection = RejectionRecord(
                        record_id=f"{doc.document_id}:empty_doc",
                        document_id=doc.document_id,
                        source_id=source.source_id,
                        rejection_reason=RejectionReason.EMPTY_TEXT,
                        rejection_stage="segmentation",
                        raw_text_sample=doc.raw_text[:100],
                        created_at=source.acquisition_date,
                    )
                    writer.write_rejection(rejection)
                    manifest_builder.observe_rejection(RejectionReason.EMPTY_TEXT.value)
                    manifest_builder.rejected_documents += 1
                    continue

                # Process each segment
                doc_has_retained_record = False
                for seg in segments:
                    # 5. Text Normalization
                    norm_result = self.normalizer.normalize(seg.raw_text)
                    normalized_text = norm_result.normalized_text

                    # 6. Quality & Language Filtering
                    decision = self.quality_filter.evaluate(normalized_text)
                    if not decision.is_accepted:
                        rejection = RejectionRecord(
                            record_id=seg.segment_id,
                            document_id=doc.document_id,
                            source_id=source.source_id,
                            rejection_reason=decision.rejection_reason or RejectionReason.INVALID_STRUCTURE,
                            rejection_stage="filtering",
                            raw_text_sample=seg.raw_text[:100],
                            metric_name=decision.failed_metric,
                            metric_value=decision.metric_value,
                            threshold_value=decision.threshold_value,
                            created_at=source.acquisition_date,
                        )
                        writer.write_rejection(rejection)
                        reason_str = decision.rejection_reason.value if decision.rejection_reason else "UNKNOWN"
                        manifest_builder.observe_rejection(reason_str)
                        continue

                    # 7. Record-Level Deduplication (Exact & Normalized, tracking contributing sources)
                    is_rec_dup, canonical_rec_id, dup_type = self.deduplicator.check_and_register_record(
                        record_id=seg.segment_id,
                        raw_text=seg.raw_text,
                        normalized_text=normalized_text,
                        source_id=source.source_id,
                        document_id=doc.document_id,
                        attribution=source.attribution,
                    )
                    if is_rec_dup:
                        rejection = RejectionRecord(
                            record_id=seg.segment_id,
                            document_id=doc.document_id,
                            source_id=source.source_id,
                            rejection_reason=RejectionReason.DUPLICATE,
                            rejection_stage="deduplication",
                            raw_text_sample=f"Duplicate ({dup_type}) of record {canonical_rec_id}",
                            created_at=source.acquisition_date,
                        )
                        writer.write_rejection(rejection)
                        manifest_builder.observe_duplicate(dup_type=dup_type or "record")
                        continue

                    # 8. Assemble Canonical CorpusRecord
                    words = normalized_text.split()
                    provenance = RecordProvenance(
                        source_id=source.source_id,
                        document_id=doc.document_id,
                        segment_index=seg.segment_index,
                        start_char_offset=seg.start_char_offset,
                        end_char_offset=seg.end_char_offset,
                        normalizer_version=self.normalizer.VERSION,
                        filter_version=self.quality_filter.VERSION,
                        created_at=source.acquisition_date,
                    )

                    record = CorpusRecord(
                        record_id=seg.segment_id,
                        document_id=doc.document_id,
                        source_id=source.source_id,
                        segment_index=seg.segment_index,
                        raw_text=seg.raw_text,
                        normalized_text=normalized_text,
                        raw_char_count=len(seg.raw_text),
                        normalized_char_count=len(normalized_text),
                        approx_word_count=len(words),
                        quality_score=decision.quality_score,
                        is_duplicate=False,
                        split=doc_split.value,
                        corpus_version=self.corpus_version,
                        provenance=provenance,
                        language="en",
                        group_id=doc.group_id,
                        contributing_sources=[source.source_id],
                        attribution_notices=[source.attribution] if source.attribution else [],
                    )

                    # 9. Storage Write & Manifest Accumulation
                    writer.write_record(record)
                    manifest_builder.observe_record(record)
                    doc_has_retained_record = True

                if doc_has_retained_record:
                    manifest_builder.retained_documents += 1
                else:
                    manifest_builder.rejected_documents += 1

            # Register sources in manifest
            for source in sources:
                manifest_builder.register_source(source, source_doc_counts[source.source_id])

            # Update duplicate statistics in manifest
            manifest_builder.observe_duplicates(
                exact=self.deduplicator.stats.exact_duplicates,
                normalized=self.deduplicator.stats.normalized_duplicates,
                document=self.deduplicator.stats.document_duplicates,
            )

            # Close and commit storage files atomically
            checksums = writer.close(commit=True)

            # Build and write manifest
            manifest = manifest_builder.build(checksums)
            manifest_path = out_path / "manifest.json"
            with open(manifest_path, "w", encoding="utf-8") as f:
                f.write(manifest.to_json())

            # Write sources.json catalog
            sources_path = out_path / "sources.json"
            with open(sources_path, "w", encoding="utf-8") as f:
                json.dump([s.to_dict() for s in sources], f, indent=2, ensure_ascii=False)

            return manifest

        except Exception as e:
            # Atomic rollback on any failure
            writer.close(commit=False)
            raise RuntimeError(f"Corpus pipeline aborted due to error: {e}") from e

    def ingest_production_corpus(
        self,
        sources: List[CorpusSource],
        documents: List[CorpusDocument],
        output_dir: Path,
        source_registry: Optional[SourceRegistry] = None,
        estimated_job_bytes: int = 0,
    ) -> CorpusManifest:
        """
        Authoritative Production Ingestion Entry Point (Phase 4.2.3).
        Fails closed on ANY unmet precondition:
        - Source missing from registry or tampered metadata
        - Non-VERIFIED_PERMITTED licensing status
        - Unacquired, unverified, or empty artifact SHA-256
        - Missing or unverified license evidence SHA-256
        - Expired approval or missing work-level scope
        - Missing attribution or provenance
        - Excluded source
        - Storage budget or host reserve margin violation (<40% free space reserve)
        - Atomic rollback guaranteeing zero committed records on failure
        """
        if source_registry is None:
            source_registry = SourceRegistry.load_from_json("data/corpus/source_registry.json")

        out_path = Path(output_dir)

        # 1. Enforce physical host reserve margin
        self.preflight_checker.verify_host_reserve_margin(out_path, estimated_job_bytes)

        # 2. Enforce strict source governance and integrity against registry
        for s in sources:
            source_registry.verify_source_integrity(s)
            source_registry.assert_permitted_admissible(s, strict_evidence=True)

        # 3. Process corpus with full strict governance and preflight enforcement
        return self.process_corpus(
            sources=sources,
            documents=documents,
            output_dir=out_path,
            strict_governance=True,
            enforce_preflight=True,
            estimated_job_bytes=estimated_job_bytes,
            source_registry=source_registry,
        )

