"""
VEDA Corpus CLI Tooling (Phase 4 — Training Corpus Architecture)

Provides command-line commands for building golden fixtures, inspecting manifests,
and verifying corpus file integrity.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from foundation.corpus.manifest import CorpusManifest
from foundation.corpus.pipeline import CorpusPipeline
from foundation.corpus.schemas import CorpusDocument, CorpusSource
from foundation.corpus.storage import CorpusReader


def cmd_build_golden(args: argparse.Namespace) -> None:
    """Builds the golden corpus fixture pipeline."""
    output_dir = Path(args.output)
    fixtures_dir = Path("data/corpus/fixtures")

    sources_path = fixtures_dir / "golden_sources.json"
    docs_path = fixtures_dir / "golden_documents.json"

    if not sources_path.exists() or not docs_path.exists():
        print(f"Error: Fixtures not found in {fixtures_dir}", file=sys.stderr)
        sys.exit(1)

    with open(sources_path, "r", encoding="utf-8") as f:
        sources = [CorpusSource.from_dict(s) for s in json.load(f)]

    with open(docs_path, "r", encoding="utf-8") as f:
        docs = [CorpusDocument.from_dict(d) for d in json.load(f)]

    print("============================================================")
    print("VEDA Training Corpus Architecture — Golden Fixture Pipeline")
    print("============================================================")
    print(f"Sources loaded: {len(sources)}")
    print(f"Documents loaded: {len(docs)}")
    print(f"Output directory: {output_dir}\n")

    pipeline = CorpusPipeline(
        corpus_name="veda_golden_corpus_v0.1",
        corpus_version="0.1.0",
    )

    manifest = pipeline.process_corpus(sources, docs, output_dir)

    print("Pipeline Execution Succeeded!")
    print(f"Total documents processed: {manifest.statistics['total_documents']}")
    print(f"Total candidate records:   {manifest.statistics['total_records_processed']}")
    print(f"Retained training records: {manifest.statistics['retained_records']}")
    print(f"Rejected records:          {manifest.statistics['rejected_records']}")
    print(f"Duplicate records:         {manifest.statistics['duplicate_records']}")
    print("\nSplit Distribution:")
    for split, count in manifest.statistics["split_counts"].items():
        print(f"  {split.upper():12}: {count:5} records")
    print(f"\nLogical Fingerprint: {manifest.artifacts['logical_fingerprint']}")
    print(f"Manifest written to: {output_dir / 'manifest.json'}")


def cmd_inspect_manifest(args: argparse.Namespace) -> None:
    """Displays detailed summary of a CorpusManifest file."""
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"Error: File not found: {manifest_path}", file=sys.stderr)
        sys.exit(1)

    manifest = CorpusManifest.from_file(manifest_path)
    print("============================================================")
    print(f"VEDA Corpus Manifest: {manifest.corpus_name} (v{manifest.corpus_version})")
    print("============================================================")
    print(f"Created At:         {manifest.created_at}")
    print(f"Schema Version:     {manifest.schema_version}")
    print(f"Pipeline Version:   {manifest.pipeline_version}")
    print(f"Split Seed:         {manifest.split_seed}")
    print("\nPolicy Versions:")
    for k, v in manifest.policies.items():
        print(f"  {k:24}: {v}")

    print("\nSources Cataloged:")
    for s in manifest.sources:
        print(f"  - ID: {s['source_id']} | License: {s['license']} ({s['licensing_status']}) | Docs: {s['document_count']}")

    print("\nProcessing Statistics:")
    stats = manifest.statistics
    print(f"  Documents:          {stats['total_documents']}")
    print(f"  Records Processed:  {stats['total_records_processed']}")
    print(f"  Retained Records:   {stats['retained_records']}")
    print(f"  Rejected Records:   {stats['rejected_records']}")
    print(f"  Duplicate Records:  {stats['duplicate_records']}")

    print("\nRejection Breakdown:")
    for reason, count in stats.get("rejection_breakdown", {}).items():
        print(f"  {reason:24}: {count}")

    print("\nArtifact Hashes:")
    for k, v in manifest.artifacts.items():
        print(f"  {k:24}: {v}")


def cmd_verify(args: argparse.Namespace) -> None:
    """Verifies cryptographic file integrity against manifest."""
    corpus_dir = Path(args.dir)
    manifest_path = corpus_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: manifest.json not found in {corpus_dir}", file=sys.stderr)
        sys.exit(1)

    manifest = CorpusManifest.from_file(manifest_path)
    print(f"Verifying corpus directory: {corpus_dir}")

    all_ok = True
    for split in ("train", "validation", "test", "rejections"):
        file_key = f"{split}_file"
        hash_key = f"{split}_sha256"
        filename = manifest.artifacts.get(file_key)
        expected_hash = manifest.artifacts.get(hash_key)

        if not filename or not expected_hash:
            continue

        file_path = corpus_dir / filename
        if not file_path.exists():
            print(f"  FAILED: Missing file {filename}")
            all_ok = False
            continue

        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        actual_hash = hasher.hexdigest()

        if actual_hash == expected_hash:
            print(f"  OK: {filename} (SHA-256 verified)")
        else:
            print(f"  MISMATCH: {filename}")
            print(f"    Expected: {expected_hash}")
            print(f"    Actual:   {actual_hash}")
            all_ok = False

    if all_ok:
        print("\nAll corpus files successfully verified against manifest!")
    else:
        print("\nIntegrity check FAILED.", file=sys.stderr)
        sys.exit(1)


def cmd_sources(args: argparse.Namespace) -> None:
    """Lists and audits candidate sources in the source registry."""
    from foundation.corpus.sources import SourceRegistry
    reg_path = Path(args.registry)
    if not reg_path.exists():
        print(f"Error: Registry file not found: {reg_path}", file=sys.stderr)
        sys.exit(1)

    reg = SourceRegistry.load_from_json(reg_path)
    summary = reg.summary()

    print("============================================================")
    print("VEDA Training Corpus — Candidate Source Registry (Phase 4.2)")
    print("============================================================")
    print(f"Total Registered Sources: {summary['total_registered_sources']}")
    print(f"  - Verified Permitted:   {summary['verified_permitted_count']}")
    print(f"  - Requires Review:      {summary['requires_review_count']}")
    print(f"  - Unknown:              {summary['unknown_count']}")
    print(f"  - Excluded:             {summary['excluded_count']}\n")

    print(f"{'SOURCE ID':30} {'STATUS':20} {'LICENSE':25} {'CONTENT TYPE'}")
    print("-" * 90)
    for s in reg.sources:
        print(f"{s.source_id:30} {s.licensing_status.value:20} {s.license[:24]:25} {s.source_type}")


def cmd_pilot(args: argparse.Namespace) -> None:
    """Executes the Phase 4.2 controlled ingestion pilot."""
    from scripts.run_corpus_pilot import run_pilot
    run_pilot()


def main() -> None:
    parser = argparse.ArgumentParser(description="VEDA Training Corpus CLI Tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sources
    p_sources = subparsers.add_parser("sources", help="List and audit registered candidate sources")
    p_sources.add_argument("--registry", default="data/corpus/source_registry.json", help="Path to source registry JSON")
    p_sources.set_defaults(func=cmd_sources)

    # pilot
    p_pilot = subparsers.add_parser("pilot", help="Run the Phase 4.2 controlled ingestion pilot")
    p_pilot.set_defaults(func=cmd_pilot)

    # build-golden
    p_build = subparsers.add_parser("build-golden", help="Build the golden corpus fixture")
    p_build.add_argument("--output", default="data/corpus/golden_output", help="Output directory")
    p_build.set_defaults(func=cmd_build_golden)

    # inspect-manifest
    p_inspect = subparsers.add_parser("inspect-manifest", help="Inspect a corpus manifest.json")
    p_inspect.add_argument("manifest", help="Path to manifest.json")
    p_inspect.set_defaults(func=cmd_inspect_manifest)

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify corpus files against manifest")
    p_verify.add_argument("dir", help="Path to corpus directory containing manifest.json")
    p_verify.set_defaults(func=cmd_verify)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

