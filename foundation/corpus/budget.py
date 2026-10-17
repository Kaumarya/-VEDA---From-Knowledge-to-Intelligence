"""
VEDA Corpus Resource Budget & Preflight Verification (Phase 4.2.1)

Audits and enforces physical system resource envelopes:
1. Peak concurrent storage accounting (downloads, extracts, staging, outputs, indexes, logs, backups)
2. Preflight disk space verification before ingestion execution
3. Host hardware measurement (OS, CPU, RAM, Disk)
4. Protection of host safety reserve margin to prevent system disk exhaustion
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore


class ResourceBudgetExceededError(RuntimeError):
    """Raised when physical system resources (disk space, RAM) fail preflight safety budgets."""
    pass


@dataclass(frozen=True)
class PeakStorageBudget:
    """
    Structured breakdown of peak concurrent disk storage for corpus ingestion.
    Distinguishes measured active pipeline footprint from future training projections.
    """
    downloaded_archives_gb: float
    extracted_source_files_gb: float
    temporary_staging_gb: float
    normalized_corpus_output_gb: float
    dedup_indexes_gb: float
    manifests_and_logs_gb: float
    backups_and_rebuild_gb: float
    # Future training artifacts (clearly labeled as NON-CONCURRENT downstream estimate deferred to Phase 7)
    future_training_artifacts_estimate_gb: float = 25.0

    @property
    def peak_concurrent_ingestion_gb(self) -> float:
        """
        Calculates maximum concurrent disk usage during ingestion:
        raw downloads + extracted files + temporary .tmp staging + retained outputs + indexes + logs + backup.
        Training artifacts are strictly deferred and NOT concurrent with ingestion.
        """
        return (
            self.downloaded_archives_gb
            + self.extracted_source_files_gb
            + self.temporary_staging_gb
            + self.normalized_corpus_output_gb
            + self.dedup_indexes_gb
            + self.manifests_and_logs_gb
            + self.backups_and_rebuild_gb
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["peak_concurrent_ingestion_gb"] = round(self.peak_concurrent_ingestion_gb, 2)
        d["training_artifacts_concurrent"] = False
        return d


class PreflightStorageChecker:
    """
    Programmatic preflight verification of disk storage and memory bounds.
    Halts execution before writing any files if disk exhaustion risks exist.

    OPERATIONAL CAVEATS:
    1. Static Preflight: Checks headroom before job starts; concurrent external processes
       writing to disk during ingestion could theoretically exhaust storage between checks.
    2. Streaming Fail-Safe: Production writers must handle OSError(ENOSPC) during atomic writes.
    3. Rollback Buffer: Atomic staging via .tmp rename requires up to 10% additional peak buffer.
    """

    # Default minimum free space reserve: 20 GB (or host-level 135.65 GB for 40% margin)
    DEFAULT_MINIMUM_RESERVE_BYTES = 20 * 1024 * 1024 * 1024  # 20 GB
    DEFAULT_HOST_SAFETY_MARGIN_PERCENT = 40.0  # 40% reserved

    def __init__(self, minimum_reserve_bytes: int = DEFAULT_MINIMUM_RESERVE_BYTES) -> None:
        self.minimum_reserve_bytes = minimum_reserve_bytes

    def verify_host_reserve_margin(
        self,
        target_path: Path,
        min_reserve_percent: float = DEFAULT_HOST_SAFETY_MARGIN_PERCENT,
        enforce: bool = True,
    ) -> Dict[str, Any]:
        """Verifies that the partition hosting target_path maintains the required host reserve margin."""
        path = Path(target_path).resolve()
        check_path = path
        while not check_path.exists() and check_path.parent != check_path:
            check_path = check_path.parent

        usage = shutil.disk_usage(str(check_path))
        free_percent = (usage.free / usage.total) * 100.0 if usage.total > 0 else 0.0
        meets_margin = free_percent >= min_reserve_percent

        report = {
            "target_path": str(path),
            "total_disk_gb": round(usage.total / (1024 ** 3), 2),
            "free_disk_gb": round(usage.free / (1024 ** 3), 2),
            "free_percent": round(free_percent, 2),
            "min_reserve_percent": min_reserve_percent,
            "meets_margin": meets_margin,
        }

        if enforce and not meets_margin:
            raise ResourceBudgetExceededError(
                f"Host safety reserve violation: Free space is {report['free_percent']}%, "
                f"below the required safety margin of {min_reserve_percent}%."
            )
        return report

    def verify_disk_availability(
        self,
        target_path: Path,
        estimated_job_bytes: int = 0,
        enforce: bool = True,
    ) -> Dict[str, Any]:
        """
        Checks available free disk space on the partition hosting target_path.

        Args:
            target_path: Filesystem path where ingestion will occur.
            estimated_job_bytes: Expected peak byte footprint of the job.
            enforce: If True, raises ResourceBudgetExceededError on violation.

        Returns:
            Dictionary containing disk metrics and safety verification status.
        """
        path = Path(target_path).resolve()
        # Find existing parent directory if target doesn't exist yet
        check_path = path
        while not check_path.exists() and check_path.parent != check_path:
            check_path = check_path.parent

        usage = shutil.disk_usage(str(check_path))
        total_bytes = usage.total
        free_bytes = usage.free
        used_bytes = usage.used

        required_bytes = estimated_job_bytes + self.minimum_reserve_bytes
        has_sufficient_space = free_bytes >= required_bytes

        report = {
            "target_path": str(path),
            "total_disk_gb": round(total_bytes / (1024 ** 3), 2),
            "used_disk_gb": round(used_bytes / (1024 ** 3), 2),
            "free_disk_gb": round(free_bytes / (1024 ** 3), 2),
            "required_reserve_gb": round(self.minimum_reserve_bytes / (1024 ** 3), 2),
            "estimated_job_gb": round(estimated_job_bytes / (1024 ** 3), 2),
            "total_required_gb": round(required_bytes / (1024 ** 3), 2),
            "has_sufficient_space": has_sufficient_space,
        }

        if enforce and not has_sufficient_space:
            shortfall_gb = round((required_bytes - free_bytes) / (1024 ** 3), 2)
            raise ResourceBudgetExceededError(
                f"Disk preflight check failed for {path}: Available free space is "
                f"{report['free_disk_gb']} GB, but {report['total_required_gb']} GB is required "
                f"({report['estimated_job_gb']} GB job + {report['required_reserve_gb']} GB safety reserve). "
                f"Shortfall: {shortfall_gb} GB."
            )

        return report

    @staticmethod
    def get_system_hardware_profile() -> Dict[str, Any]:
        """Measures and returns current physical host specifications."""
        profile: Dict[str, Any] = {
            "cpu_cores_logical": os.cpu_count() or 1,
            "os_name": os.name,
        }
        if psutil:
            mem = psutil.virtual_memory()
            profile.update({
                "total_ram_gb": round(mem.total / (1024 ** 3), 2),
                "available_ram_gb": round(mem.available / (1024 ** 3), 2),
                "ram_percent_used": mem.percent,
            })
        return profile
