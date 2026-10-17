"""
VEDA Near-Duplicate Detection & MinHash/LSH Evaluation (Phase 4.2.1)

Implements scalable candidate retrieval for near-duplicate text detection using
k-shingle MinHash signatures and Locality Sensitive Hashing (LSH), evaluated against
a labeled test set containing exact duplicates, near-duplicates, hard negatives,
and distant negatives.

CRITICAL ARCHITECTURAL BOUNDARY:
MinHash/LSH is evaluated strictly as a scalable candidate-retrieval and screening
method for identifying potential duplicate candidates. It must NOT be treated as a
complete semantic-equivalence determination or authoritative copyright arbiter.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


def get_k_shingles(text: str, k: int = 5) -> Set[str]:
    """Generates a set of character k-shingles from text."""
    clean_text = " ".join(text.lower().split())
    if len(clean_text) <= k:
        return {clean_text}
    return {clean_text[i:i + k] for i in range(len(clean_text) - k + 1)}


def jaccard_similarity(set_a: Set[str], set_b: Set[str]) -> float:
    """Calculates true Jaccard set similarity |A ∩ B| / |A ∪ B|."""
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


class MinHashLSHCandidateDetector:
    """
    MinHash signature generation and LSH bucket candidate indexing.
    """

    PRIME = 4294967311  # Large 32-bit prime

    def __init__(
        self,
        num_perm: int = 128,
        num_bands: int = 16,
        k_shingle: int = 5,
        threshold: float = 0.80,
    ) -> None:
        if num_perm % num_bands != 0:
            raise ValueError(f"num_perm ({num_perm}) must be divisible by num_bands ({num_bands})")
        self.num_perm = num_perm
        self.num_bands = num_bands
        self.rows_per_band = num_perm // num_bands
        self.k_shingle = k_shingle
        self.threshold = threshold

        # Deterministic linear permutation parameters (a * x + b) % PRIME
        self._a: List[int] = []
        self._b: List[int] = []
        for i in range(num_perm):
            h_a = int(hashlib.sha256(f"a_seed_{i}".encode("utf-8")).hexdigest()[:8], 16)
            h_b = int(hashlib.sha256(f"b_seed_{i}".encode("utf-8")).hexdigest()[:8], 16)
            self._a.append((h_a % (self.PRIME - 1)) + 1)
            self._b.append(h_b % self.PRIME)

        # Initialize NumPy acceleration arrays if available
        try:
            import numpy as np
            self._a_np = np.array(self._a, dtype=np.uint64).reshape(-1, 1)
            self._b_np = np.array(self._b, dtype=np.uint64).reshape(-1, 1)
        except ImportError:
            self._a_np = None
            self._b_np = None

        # LSH buckets: (band_index, bucket_hash) -> list of doc_ids
        self._buckets: Dict[Tuple[int, str], List[str]] = {}
        # Document signatures: doc_id -> list of uint32
        self._signatures: Dict[str, List[int]] = {}

    def compute_signature(self, text: str) -> List[int]:
        """Computes the MinHash signature vector for input text."""
        shingles = get_k_shingles(text, self.k_shingle)
        if not shingles:
            return [0] * self.num_perm

        # Hash shingles to 32-bit unsigned integers
        shingle_hashes = [
            int(hashlib.sha256(s.encode("utf-8")).hexdigest()[:8], 16)
            for s in shingles
        ]

        # Fast vectorized path via NumPy
        if self._a_np is not None:
            try:
                import numpy as np
                h_arr = np.array(shingle_hashes, dtype=np.uint64).reshape(1, -1)
                perms = (self._a_np * h_arr + self._b_np) % self.PRIME
                return np.min(perms, axis=1).tolist()
            except Exception:
                pass

        # Fallback pure-Python scalar path
        sig = []
        for i in range(self.num_perm):
            a = self._a[i]
            b = self._b[i]
            min_val = min((a * h + b) % self.PRIME for h in shingle_hashes)
            sig.append(min_val)
        return sig

    def index_document(self, doc_id: str, text: str) -> None:
        """Indexes a document into LSH buckets."""
        sig = self.compute_signature(text)
        self._signatures[doc_id] = sig

        for b in range(self.num_bands):
            start = b * self.rows_per_band
            band_chunk = tuple(sig[start:start + self.rows_per_band])
            band_hash = hashlib.sha256(str(band_chunk).encode("utf-8")).hexdigest()[:16]
            bucket_key = (b, band_hash)
            self._buckets.setdefault(bucket_key, []).append(doc_id)

    def query_candidates(self, text: str) -> Set[str]:
        """Retrieves all candidate document IDs sharing at least one LSH bucket."""
        sig = self.compute_signature(text)
        candidates: Set[str] = set()

        for b in range(self.num_bands):
            start = b * self.rows_per_band
            band_chunk = tuple(sig[start:start + self.rows_per_band])
            band_hash = hashlib.sha256(str(band_chunk).encode("utf-8")).hexdigest()[:16]
            bucket_key = (b, band_hash)
            for doc_id in self._buckets.get(bucket_key, []):
                candidates.add(doc_id)
        return candidates

    def estimate_similarity(self, sig_a: List[int], sig_b: List[int]) -> float:
        """Estimates Jaccard similarity from two MinHash signatures."""
        if len(sig_a) != len(sig_b):
            raise ValueError("Signatures must have identical length")
        matches = sum(1 for x, y in zip(sig_a, sig_b) if x == y)
        return matches / len(sig_a)

    def clear(self) -> None:
        """Clears index state."""
        self._buckets.clear()
        self._signatures.clear()


@dataclass(frozen=True)
class SafetyVerificationResult:
    """Outcome of Stage 3 semantic safety verification between candidate near-duplicate texts."""
    is_safe_to_merge: bool
    conflict_detected: bool
    conflict_type: Optional[str] = None  # NUMERICAL_MISMATCH, POLARITY_INVERSION, DATE_MISMATCH, etc.
    reason: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


class SemanticSafetyGuard:
    """
    Stage 3 Safety-Aware Decision Guard for Near-Deduplication.
    Inspects candidate pairs (Jaccard >= threshold) for material factual conflicts:
    - Numerical quantities, decimal notation, and standard unit conversions (SI normalization)
    - Logical polarity and contradictory statements (safe vs toxic, all vs no, permitted vs prohibited)
    - Calendar years and temporal references (1824 vs 1827)
    """

    # Base SI units and conversion multipliers to base unit
    UNIT_TO_BASE: Dict[str, Tuple[str, float]] = {
        "mg": ("g", 1e-3),
        "milligram": ("g", 1e-3),
        "milligrams": ("g", 1e-3),
        "g": ("g", 1.0),
        "gram": ("g", 1.0),
        "grams": ("g", 1.0),
        "kg": ("g", 1e3),
        "kilogram": ("g", 1e3),
        "kilograms": ("g", 1e3),
        "ml": ("l", 1e-3),
        "milliliter": ("l", 1e-3),
        "milliliters": ("l", 1e-3),
        "l": ("l", 1.0),
        "liter": ("l", 1.0),
        "liters": ("l", 1.0),
        "mm": ("m", 1e-3),
        "millimeter": ("m", 1e-3),
        "millimeters": ("m", 1e-3),
        "cm": ("m", 1e-2),
        "centimeter": ("m", 1e-2),
        "centimeters": ("m", 1e-2),
        "m": ("m", 1.0),
        "meter": ("m", 1.0),
        "meters": ("m", 1.0),
        "km": ("m", 1e3),
        "kilometer": ("m", 1e3),
        "kilometers": ("m", 1e3),
        "v": ("v", 1.0),
        "volt": ("v", 1.0),
        "volts": ("v", 1.0),
        "mv": ("v", 1e-3),
        "millivolt": ("v", 1e-3),
        "millivolts": ("v", 1e-3),
        "kv": ("v", 1e3),
        "kilovolt": ("v", 1e3),
        "kilovolts": ("v", 1e3),
        "%": ("%", 1.0),
        "percent": ("%", 1.0),
        "s": ("s", 1.0),
        "sec": ("s", 1.0),
        "second": ("s", 1.0),
        "seconds": ("s", 1.0),
        "min": ("s", 60.0),
        "minute": ("s", 60.0),
        "minutes": ("s", 60.0),
        "hr": ("s", 3600.0),
        "hour": ("s", 3600.0),
        "hours": ("s", 3600.0),
        "day": ("s", 86400.0),
        "days": ("s", 86400.0),
        "b": ("b", 1.0),
        "byte": ("b", 1.0),
        "bytes": ("b", 1.0),
        "kb": ("b", 1e3),
        "kilobyte": ("b", 1e3),
        "kilobytes": ("b", 1e3),
        "mb": ("b", 1e6),
        "megabyte": ("b", 1e6),
        "megabytes": ("b", 1e6),
        "gb": ("b", 1e9),
        "gigabyte": ("b", 1e9),
        "gigabytes": ("b", 1e9),
        "kib": ("b", 1024.0),
        "kibibyte": ("b", 1024.0),
        "kibibytes": ("b", 1024.0),
        "mib": ("b", 1048576.0),
        "mebibyte": ("b", 1048576.0),
        "mebibytes": ("b", 1048576.0),
        "gib": ("b", 1073741824.0),
        "gibibyte": ("b", 1073741824.0),
        "gibibytes": ("b", 1073741824.0),
        "tib": ("b", 1099511627776.0),
        "tebibyte": ("b", 1099511627776.0),
        "tebibytes": ("b", 1099511627776.0),
        # Current
        "a": ("a", 1.0),
        "amp": ("a", 1.0),
        "amps": ("a", 1.0),
        "ampere": ("a", 1.0),
        "amperes": ("a", 1.0),
        "ma": ("a", 1e-3),
        "milliampere": ("a", 1e-3),
        "milliamperes": ("a", 1e-3),
        # Temperature
        "c": ("temp_c", 1.0),
        "celsius": ("temp_c", 1.0),
        "f": ("temp_f", 1.0),
        "fahrenheit": ("temp_f", 1.0),
        "k": ("temp_k", 1.0),
        "kelvin": ("temp_k", 1.0),
        # Pressure
        "bar": ("bar", 1.0),
        "mbar": ("bar", 1e-3),
        "pa": ("bar", 1e-5),
        "kpa": ("bar", 1e-2),
        "mpa": ("bar", 10.0),
        "atm": ("bar", 1.01325),
        # Substance
        "mol": ("mol", 1.0),
        "mole": ("mol", 1.0),
        "moles": ("mol", 1.0),
        "mmol": ("mol", 1e-3),
        # Frequency
        "hz": ("hz", 1.0),
        "khz": ("hz", 1e3),
        "mhz": ("hz", 1e6),
        "ghz": ("hz", 1e9),
    }

    PHYSICAL_BASE_UNITS: Set[str] = {
        "g", "m", "l", "v", "s", "b", "%", "a", "temp_c", "temp_f", "temp_k", "bar", "mol", "hz"
    }

    NON_UNIT_WORDS: Set[str] = {
        "of", "in", "for", "the", "at", "to", "by", "from", "with", "on", "and", "or",
        "a", "an", "is", "was", "were", "are", "be", "been", "have", "has", "had",
        "times", "it", "them", "which", "that", "this", "these", "those", "each", "all"
    }

    # Polarity antonym sets (positive_markers, negative_markers)
    POLARITY_PAIRS: List[Tuple[Set[str], Set[str]]] = [
        ({"safe", "safety", "nontoxic", "non-toxic"}, {"toxic", "toxicity", "dangerous", "fatal", "harmful"}),
        ({"all", "every"}, {"no", "none", "neither"}),
        ({"permit", "permits", "permitted", "allow", "allows", "allowed", "authorize", "authorizes", "authorized"}, {"prohibit", "prohibits", "prohibited", "forbid", "forbids", "forbidden", "unauthorized", "deny", "denies", "denied"}),
        ({"approve", "approves", "approved", "approving", "pass", "passes", "passed"}, {"reject", "rejects", "rejected", "rejecting", "fail", "fails", "failed"}),
        ({"enable", "enables", "enabled", "enabling", "active"}, {"disable", "disables", "disabled", "disabling", "inactive"}),
        ({"with", "complete"}, {"without", "zero", "no"}),
        ({"greater", "above", "exceeds", "at_least", "minimum", "more"}, {"less", "below", "under", "at_most", "maximum", "fewer"}),
        (
            {"increase", "increases", "increased", "increasing", "gain", "gains", "rise", "rises", "expand", "expands", "expanded", "expanding"},
            {"decrease", "decreases", "decreased", "decreasing", "reduce", "reduces", "reduced", "reducing", "contract", "contracts", "contracted", "contracting", "loss", "losses", "fall", "falls", "drop", "drops"},
        ),
        ({"positive", "confirmed", "confirms", "confirming"}, {"negative", "unconfirmed", "disproven", "disproves", "disproving"}),
        ({"before", "prior"}, {"after", "subsequent"}),
        ({"include", "includes", "included", "including"}, {"exclude", "excludes", "excluded", "excluding"}),
    ]

    NUM_PATTERN = re.compile(
        r"(?<![a-zA-Z0-9_])([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*([a-zA-Z%]+)?(?![a-zA-Z0-9_])"
    )
    IDENTIFIER_PATTERN = re.compile(
        r"\b(?:[A-Za-z]{1,10}[-_][A-Za-z0-9]*\d[A-Za-z0-9]*|\d+[A-Za-z0-9]*[-_][A-Za-z0-9]+)\b"
    )
    MONTH_PATTERN = re.compile(
        r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
        re.IGNORECASE,
    )

    def extract_quantities(self, text: str) -> List[Tuple[float, str]]:
        """Extracts normalized numerical quantities in SI base units."""
        quantities = []
        for match in self.NUM_PATTERN.finditer(text):
            num_str, unit_str = match.groups()
            try:
                raw_val = float(num_str)
            except ValueError:
                continue

            base_unit = "count"
            norm_val = raw_val
            if unit_str:
                u_lower = unit_str.lower()
                if u_lower in self.UNIT_TO_BASE:
                    base_unit, mult = self.UNIT_TO_BASE[u_lower]
                    norm_val = round(raw_val * mult, 6)
                else:
                    base_unit = "count"

            quantities.append((norm_val, base_unit))
        return quantities

    def check_numerical_conflict(self, text_a: str, text_b: str) -> Optional[Tuple[str, str]]:
        """Checks for numerical discrepancies and unit/dimension incompatibilities between two texts."""
        q_a = self.extract_quantities(text_a)
        q_b = self.extract_quantities(text_b)

        if not q_a and not q_b:
            return None

        set_a = set(q_a)
        set_b = set(q_b)

        if set_a != set_b:
            diff_a = set_a - set_b
            diff_b = set_b - set_a
            vals_a = {v for v, u in diff_a}
            vals_b = {v for v, u in diff_b}
            units_a = {u for v, u in diff_a}
            units_b = {u for v, u in diff_b}

            if vals_a != vals_b:
                return (
                    "NUMERICAL_MISMATCH",
                    f"Numerical quantity discrepancy: {diff_a} vs {diff_b}",
                )

            # Check for physical unit / dimension conflict for identical scalar numbers
            phys_a = units_a & self.PHYSICAL_BASE_UNITS
            phys_b = units_b & self.PHYSICAL_BASE_UNITS
            if phys_a != phys_b or (phys_a and units_a != units_b):
                return (
                    "UNIT_MISMATCH",
                    f"Incompatible physical units for identical quantity: {diff_a} vs {diff_b}",
                )
        return None

    def check_polarity_conflict(self, text_a: str, text_b: str) -> Optional[Tuple[str, str]]:
        """Checks for logical polarity or negation inversions."""
        # Expand common English negative contractions (e.g. isn't -> is not, wasn't -> was not)
        text_a_norm = re.sub(
            r"\b([a-zA-Z]+)n['’]t\b",
            lambda m: "can not" if m.group(1).lower() == "ca" else ("will not" if m.group(1).lower() == "wo" else f"{m.group(1)} not"),
            text_a,
            flags=re.IGNORECASE,
        )
        text_b_norm = re.sub(
            r"\b([a-zA-Z]+)n['’]t\b",
            lambda m: "can not" if m.group(1).lower() == "ca" else ("will not" if m.group(1).lower() == "wo" else f"{m.group(1)} not"),
            text_b,
            flags=re.IGNORECASE,
        )

        # Normalize "No." followed by digits to "number" to prevent false negation on abbreviations (e.g. Model No. 5)
        text_a_norm = re.sub(r"\bno\b(?:\.|\s+(?=\d))", "number", text_a_norm, flags=re.IGNORECASE)
        text_b_norm = re.sub(r"\bno\b(?:\.|\s+(?=\d))", "number", text_b_norm, flags=re.IGNORECASE)

        norm_a = text_a_norm.lower().replace("at least", "at_least").replace("at most", "at_most").replace("non-toxic", "nontoxic")
        norm_b = text_b_norm.lower().replace("at least", "at_least").replace("at most", "at_most").replace("non-toxic", "nontoxic")
        words_a = set(re.findall(r"\b[a-zA-Z_-]+\b", norm_a))
        words_b = set(re.findall(r"\b[a-zA-Z_-]+\b", norm_b))

        diff_a = words_a - words_b
        diff_b = words_b - words_a

        for pos_set, neg_set in self.POLARITY_PAIRS:
            # 1. Primary check on differing words (prevents masking by shared prepositions like 'under')
            a_pos = bool(diff_a & pos_set)
            a_neg = bool(diff_a & neg_set)
            b_pos = bool(diff_b & pos_set)
            b_neg = bool(diff_b & neg_set)

            if (a_pos and b_neg and not a_neg and not b_pos) or \
               (a_neg and b_pos and not a_pos and not b_neg):
                match_a = list(diff_a & (pos_set | neg_set))
                match_b = list(diff_b & (pos_set | neg_set))
                return (
                    "POLARITY_INVERSION",
                    f"Contradictory polarity detected: '{match_a}' vs '{match_b}'",
                )

            # 2. Fallback check on full word sets
            a_has_pos = bool(words_a & pos_set)
            a_has_neg = bool(words_a & neg_set)
            b_has_pos = bool(words_b & pos_set)
            b_has_neg = bool(words_b & neg_set)

            if (a_has_pos and not a_has_neg and b_has_neg and not b_has_pos) or \
               (a_has_neg and not a_has_pos and b_has_pos and not b_has_neg):
                match_a = list(words_a & (pos_set | neg_set))
                match_b = list(words_b & (pos_set | neg_set))
                return (
                    "POLARITY_INVERSION",
                    f"Contradictory polarity detected: '{match_a}' vs '{match_b}'",
                )

        neg_particles = {
            "not", "no", "never", "cannot", "neither", "nor", "without", "none", "barely", "scarcely", "hardly"
        }
        # Check differing negation particles
        diff_a_negs = diff_a & neg_particles
        diff_b_negs = diff_b & neg_particles
        if bool(diff_a_negs) != bool(diff_b_negs):
            return (
                "NEGATION_INVERSION",
                f"Asymmetric negation particle detected: '{diff_a_negs}' vs '{diff_b_negs}'",
            )
        # Fallback check on full sets
        a_negs = words_a & neg_particles
        b_negs = words_b & neg_particles
        if bool(a_negs) != bool(b_negs):
            return (
                "NEGATION_INVERSION",
                f"Asymmetric negation particle detected: '{a_negs}' vs '{b_negs}'",
            )

        return None

    def check_date_conflict(self, text_a: str, text_b: str) -> Optional[Tuple[str, str]]:
        """Checks for calendar year, month, and date discrepancies."""
        years_a = set(re.findall(r"\b(1[6-9]\d{2}|20\d{2})\b", text_a))
        years_b = set(re.findall(r"\b(1[6-9]\d{2}|20\d{2})\b", text_b))
        if years_a and years_b and years_a != years_b:
            return (
                "DATE_MISMATCH",
                f"Conflicting temporal year references: {years_a} vs {years_b}",
            )

        months_a = set(self.MONTH_PATTERN.findall(text_a.lower()))
        months_b = set(self.MONTH_PATTERN.findall(text_b.lower()))
        if months_a and months_b and months_a != months_b:
            return (
                "DATE_MISMATCH",
                f"Conflicting calendar month references: {months_a} vs {months_b}",
            )
        return None

    def check_identifier_conflict(self, text_a: str, text_b: str) -> Optional[Tuple[str, str]]:
        """Checks for entity identifier or code mismatches (e.g., A-104 vs B-104)."""
        ids_a = set(re.findall(self.IDENTIFIER_PATTERN, text_a))
        ids_b = set(re.findall(self.IDENTIFIER_PATTERN, text_b))
        if ids_a and ids_b and ids_a != ids_b:
            diff_a = ids_a - ids_b
            diff_b = ids_b - ids_a
            return (
                "IDENTIFIER_MISMATCH",
                f"Conflicting entity identifier codes: {diff_a} vs {diff_b}",
            )
        return None

    def verify_pair(self, text_a: str, text_b: str) -> SafetyVerificationResult:
        """Evaluates whether high-similarity candidate pair is safe to merge."""
        # 1. Numerical check
        num_err = self.check_numerical_conflict(text_a, text_b)
        if num_err:
            c_type, c_reason = num_err
            return SafetyVerificationResult(
                is_safe_to_merge=False,
                conflict_detected=True,
                conflict_type=c_type,
                reason=c_reason,
                details={"stage": "numerical_verification"},
            )

        # 2. Polarity / Negation check
        pol_err = self.check_polarity_conflict(text_a, text_b)
        if pol_err:
            c_type, c_reason = pol_err
            return SafetyVerificationResult(
                is_safe_to_merge=False,
                conflict_detected=True,
                conflict_type=c_type,
                reason=c_reason,
                details={"stage": "polarity_verification"},
            )

        # 3. Date check
        date_err = self.check_date_conflict(text_a, text_b)
        if date_err:
            c_type, c_reason = date_err
            return SafetyVerificationResult(
                is_safe_to_merge=False,
                conflict_detected=True,
                conflict_type=c_type,
                reason=c_reason,
                details={"stage": "date_verification"},
            )

        # 4. Entity Identifier check
        id_err = self.check_identifier_conflict(text_a, text_b)
        if id_err:
            c_type, c_reason = id_err
            return SafetyVerificationResult(
                is_safe_to_merge=False,
                conflict_detected=True,
                conflict_type=c_type,
                reason=c_reason,
                details={"stage": "identifier_verification"},
            )

        return SafetyVerificationResult(
            is_safe_to_merge=True,
            conflict_detected=False,
            conflict_type=None,
            reason="Semantic integrity verified: No material factual, numerical, polarity, or identifier conflicts",
            details={"stage": "verified_safe"},
        )


@dataclass
class NearDuplicateResult:
    """Result of end-to-end two-stage near-duplicate evaluation."""
    is_duplicate: bool
    candidate_similarity: float
    is_candidate: bool
    safety_guard_passed: bool
    safety_guard_violations: Optional[str] = None
    conflict_type: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class NearDuplicateDetector:
    """Production end-to-end near-duplicate detector.

    Combines Stage 2 candidate screening (MinHash signature estimate and token Jaccard)
    with Stage 3 SemanticSafetyGuard verification to guarantee safety-critical separation
    before accepting duplicates.
    """

    def __init__(
        self,
        threshold: float = 0.75,
        num_perm: int = 128,
        num_bands: int = 16,
        k_shingle: int = 5,
        safety_guard: Optional[SemanticSafetyGuard] = None,
    ) -> None:
        self.threshold = threshold
        self.candidate_detector = MinHashLSHCandidateDetector(
            num_perm=num_perm,
            num_bands=num_bands,
            k_shingle=k_shingle,
            threshold=threshold,
        )
        self.safety_guard = safety_guard or SemanticSafetyGuard()

    def are_near_duplicates(self, text_a: str, text_b: str) -> NearDuplicateResult:
        """Determines if two texts are safe near-duplicates.

        1. Evaluates candidate similarity (MinHash signature estimate and token Jaccard).
        2. If candidate similarity >= threshold, invokes SemanticSafetyGuard.verify_pair().
        3. Returns NearDuplicateResult with full provenance of the decision.
        """
        if not isinstance(text_a, str) or not isinstance(text_b, str):
            raise TypeError("NearDuplicateDetector.are_near_duplicates expects string inputs")

        # Fast path for identical text
        if text_a.strip() == text_b.strip():
            return NearDuplicateResult(
                is_duplicate=True,
                candidate_similarity=1.0,
                is_candidate=True,
                safety_guard_passed=True,
                safety_guard_violations=None,
                conflict_type=None,
                details={"stage": "exact_match"},
            )

        # Stage 2: Candidate similarity evaluation
        sig_a = self.candidate_detector.compute_signature(text_a)
        sig_b = self.candidate_detector.compute_signature(text_b)
        est_jaccard = self.candidate_detector.estimate_similarity(sig_a, sig_b)

        words_a = set(re.findall(r"\b[a-zA-Z0-9_%-]+\b", text_a.lower()))
        words_b = set(re.findall(r"\b[a-zA-Z0-9_%-]+\b", text_b.lower()))
        token_jaccard = len(words_a & words_b) / len(words_a | words_b) if (words_a | words_b) else 1.0
        candidate_similarity = max(est_jaccard, token_jaccard)
        is_candidate = candidate_similarity >= self.threshold

        if not is_candidate:
            return NearDuplicateResult(
                is_duplicate=False,
                candidate_similarity=candidate_similarity,
                is_candidate=False,
                safety_guard_passed=False,
                safety_guard_violations="Below candidate similarity threshold",
                conflict_type=None,
                details={"stage": "candidate_screening", "est_jaccard": est_jaccard, "token_jaccard": token_jaccard},
            )

        # Stage 3: Semantic Safety-Aware Decision Guard
        safety_res = self.safety_guard.verify_pair(text_a, text_b)
        return NearDuplicateResult(
            is_duplicate=safety_res.is_safe_to_merge,
            candidate_similarity=candidate_similarity,
            is_candidate=True,
            safety_guard_passed=safety_res.is_safe_to_merge,
            safety_guard_violations=safety_res.reason if not safety_res.is_safe_to_merge else None,
            conflict_type=safety_res.conflict_type,
            details={"stage": "semantic_safety_guard", "safety_details": safety_res.details},
        )



@dataclass
class LabeledTextPair:
    """Ground truth labeled pair for evaluating near-duplicate detection."""
    pair_id: str
    doc_a_id: str
    doc_b_id: str
    text_a: str
    text_b: str
    is_true_duplicate: bool
    category: str  # exact_duplicate, light_edit, typo_edit, hard_negative, distant_negative
    description: str


def build_dev_labeled_test_set() -> List[LabeledTextPair]:
    """
    Development tuning set (6 pairs) used for calibrating k-shingle length and LSH bands.
    Kept strictly separate from held-out evaluation pairs.
    """
    base_text = (
        "Language intelligence requires an uncompromising commitment to verified provenance. "
        "The VEDA architecture demonstrates that foundational models can be trained strictly on "
        "auditable, legally verified, and high-quality texts without web-scraping shortcuts."
    )
    p1 = LabeledTextPair(
        pair_id="dev_exact_001",
        doc_a_id="dev_base",
        doc_b_id="dev_exact",
        text_a=base_text,
        text_b=base_text,
        is_true_duplicate=True,
        category="exact_duplicate",
        description="Dev bit-for-bit identical text",
    )
    p2 = LabeledTextPair(
        pair_id="dev_ws_002",
        doc_a_id="dev_base",
        doc_b_id="dev_ws",
        text_a=base_text,
        text_b=base_text.replace(". ", ".  "),
        is_true_duplicate=True,
        category="reformatted_duplicate",
        description="Dev double spacing",
    )
    p3 = LabeledTextPair(
        pair_id="dev_edit_003",
        doc_a_id="dev_base",
        doc_b_id="dev_edit",
        text_a=base_text,
        text_b=base_text.replace("demonstrates", "shows"),
        is_true_duplicate=True,
        category="light_edit_duplicate",
        description="Dev single synonym swap",
    )
    p4 = LabeledTextPair(
        pair_id="dev_hard_neg_004",
        doc_a_id="dev_base",
        doc_b_id="dev_hn",
        text_a=base_text,
        text_b=(
            "Model intelligence requires an uncompromising commitment to massive scale. "
            "The web architecture demonstrates that foundational models can be trained cheaply on "
            "unfiltered, automatically scraped, and noisy texts using web-crawling shortcuts."
        ),
        is_true_duplicate=False,
        category="hard_negative_semantic_inversion",
        description="Dev high syntactic overlap with inverted engineering claims",
    )
    p5 = LabeledTextPair(
        pair_id="dev_distant_neg_005",
        doc_a_id="dev_base",
        doc_b_id="dev_dn",
        text_a=base_text,
        text_b="Photosynthesis in plants converts carbon dioxide and water into glucose and oxygen.",
        is_true_duplicate=False,
        category="distant_negative",
        description="Dev botany biology prose",
    )
    p6 = LabeledTextPair(
        pair_id="dev_short_neg_006",
        doc_a_id="dev_base",
        doc_b_id="dev_sn",
        text_a=base_text,
        text_b="Caution: High voltage. Authorized personnel only.",
        is_true_duplicate=False,
        category="distant_negative",
        description="Dev short technical warning sign",
    )
    return [p1, p2, p3, p4, p5, p6]


def build_eval_labeled_test_set() -> List[LabeledTextPair]:
    """
    Authoritative held-out evaluation benchmark set (10 pairs).
    Evaluates exact duplicates, reformatted variants, synonym edits, reordered paragraphs,
    OCR errors, domain terminology overlap, shared boilerplate, semantic inversions,
    technical configuration overlaps, and distant negatives.
    """
    base_text = (
        "Language intelligence requires an uncompromising commitment to verified provenance. "
        "The VEDA architecture demonstrates that foundational models can be trained strictly on "
        "auditable, legally verified, and high-quality texts without web-scraping shortcuts. "
        "By decoupling corpus representability from downstream tokenizer vocabulary constraints, "
        "we ensure that naturalized loanwords like café and résumé are faithfully preserved in NFC."
    )

    # 1. Exact duplicate (Positive)
    p1 = LabeledTextPair(
        pair_id="eval_exact_001",
        doc_a_id="doc_base",
        doc_b_id="doc_exact",
        text_a=base_text,
        text_b=base_text,
        is_true_duplicate=True,
        category="exact_duplicate",
        description="Bit-for-bit identical text",
    )

    # 2. Reformatted duplicate: whitespace and punctuation (Positive)
    p2 = LabeledTextPair(
        pair_id="eval_near_ws_002",
        doc_a_id="doc_base",
        doc_b_id="doc_ws",
        text_a=base_text,
        text_b=(
            "Language intelligence requires an uncompromising commitment to verified provenance!  "
            "The VEDA architecture demonstrates that foundational models can be trained strictly on  "
            "auditable, legally verified, and high-quality texts without web-scraping shortcuts.  "
            "By decoupling corpus representability from downstream tokenizer vocabulary constraints, "
            "we ensure that naturalized loanwords like café and résumé are faithfully preserved in NFC."
        ),
        is_true_duplicate=True,
        category="reformatted_duplicate",
        description="Punctuation variation and double spacing",
    )

    # 3. Light edit duplicate: synonym replacement (Positive)
    p3 = LabeledTextPair(
        pair_id="eval_near_syn_003",
        doc_a_id="doc_base",
        doc_b_id="doc_syn",
        text_a=base_text,
        text_b=(
            "Language intelligence requires an uncompromising commitment to verified provenance. "
            "The VEDA architecture proves that foundational models can be trained strictly on "
            "auditable, legally verified, and high-quality texts without web-scraping shortcuts. "
            "By decoupling corpus representability from downstream tokenizer vocabulary constraints, "
            "we ensure that naturalized loanwords like café and résumé are faithfully preserved in NFC."
        ),
        is_true_duplicate=True,
        category="light_edit_duplicate",
        description="Single synonym swap: 'demonstrates' -> 'proves'",
    )

    # 4. Reordered duplicate: sentence reordering (Positive)
    p4 = LabeledTextPair(
        pair_id="eval_reordered_004",
        doc_a_id="doc_base",
        doc_b_id="doc_reord",
        text_a=base_text,
        text_b=(
            "By decoupling corpus representability from downstream tokenizer vocabulary constraints, "
            "we ensure that naturalized loanwords like café and résumé are faithfully preserved in NFC. "
            "Language intelligence requires an uncompromising commitment to verified provenance. "
            "The VEDA architecture demonstrates that foundational models can be trained strictly on "
            "auditable, legally verified, and high-quality texts without web-scraping shortcuts."
        ),
        is_true_duplicate=True,
        category="reordered_duplicate",
        description="Sentence order transposition of identical clauses",
    )

    # 5. Typo/OCR duplicate: minor character corruptions (Positive)
    p5 = LabeledTextPair(
        pair_id="eval_ocr_005",
        doc_a_id="doc_base",
        doc_b_id="doc_ocr",
        text_a=base_text,
        text_b=(
            "Language intelligence requires an uncomprmising commitment to verified provenance. "
            "The VEDA architecture demonstrates that foundational models can be trained strictly on "
            "auditable, legally verified, and high-quality texts without web-scraping shortcts. "
            "By decoupling corpus representability from downstream tokenizer vocabulary constraints, "
            "we ensure that naturalized loanwords like café and résumé are faithfully preserved in NFC."
        ),
        is_true_duplicate=True,
        category="ocr_error_duplicate",
        description="Minor typographical dropouts: 'uncomprmising', 'shortcts'",
    )

    # 6. Hard negative: Python lists vs Python dicts (Negative)
    doc_python_lists = (
        "Lists are versatile compound data types in the Python language. The list data type "
        "has methods that allow developers to use lists as stacks or queues efficiently in memory. "
        "To add an item to the end of the list, use the append method. Methods like pop remove and "
        "return the last item from the list, making it straightforward to implement LIFO retrieval."
    )
    doc_python_dicts = (
        "Dictionaries are versatile compound data types in the Python language. The dictionary data type "
        "has methods that allow developers to use hash mappings efficiently in memory. "
        "To add an item to the end of the dictionary, use assignment. Methods like pop remove and "
        "return the key-value pair, making it straightforward to implement hash table retrieval."
    )
    p6 = LabeledTextPair(
        pair_id="eval_hard_neg_domain_006",
        doc_a_id="py_lists",
        doc_b_id="py_dicts",
        text_a=doc_python_lists,
        text_b=doc_python_dicts,
        is_true_duplicate=False,
        category="hard_negative_domain_overlap",
        description="High syntactic and domain terminology overlap, but distinct programming data types",
    )

    # 7. Hard negative: Semantic inversion in legal judgment (Negative)
    court_aff = (
        "The Supreme Court affirmed the judgment of the Court of Appeals holding that statutory text "
        "must be interpreted according to its ordinary public meaning at the time of enactment. "
        "The judgment is therefore affirmed with costs awarded to the respondent."
    )
    court_rev = (
        "The Supreme Court reversed the judgment of the Court of Appeals holding that statutory text "
        "cannot be interpreted contrary to its legislative purpose at the time of enactment. "
        "The judgment is therefore reversed with costs awarded to the petitioner."
    )
    p7 = LabeledTextPair(
        pair_id="eval_hard_neg_inversion_007",
        doc_a_id="court_aff",
        doc_b_id="court_rev",
        text_a=court_aff,
        text_b=court_rev,
        is_true_duplicate=False,
        category="hard_negative_semantic_inversion",
        description="Near-identical legal phrasing with inverted holding: 'affirmed' vs 'reversed'",
    )

    # 8. Hard negative: Shared copyright boilerplate on distinct scientific topics (Negative)
    bp_text_a = (
        "Photosynthesis converts solar electromagnetic radiation into chemical energy in green plants. "
        "Chlorophyll absorbs blue and red wavelengths while reflecting green light. "
        "All rights reserved. Reproduction or redistribution without written permission of the publisher is strictly prohibited."
    )
    bp_text_b = (
        "Quantum mechanics governs the behavior of subatomic particles at atomic scales. "
        "Wave-particle duality implies that electrons exhibit interference patterns. "
        "All rights reserved. Reproduction or redistribution without written permission of the publisher is strictly prohibited."
    )
    p8 = LabeledTextPair(
        pair_id="eval_hard_neg_boilerplate_008",
        doc_a_id="doc_photo",
        doc_b_id="doc_quantum",
        text_a=bp_text_a,
        text_b=bp_text_b,
        is_true_duplicate=False,
        category="hard_negative_shared_boilerplate",
        description="Entirely different scientific topics sharing identical copyright boilerplate tail",
    )

    # 9. Hard negative: Technical configuration profile overlap (Negative)
    params_a = (
        "HTTP Server Configuration Profile Alpha: host=0.0.0.0, port=8080, max_connections=5000, "
        "timeout=30s, keepalive=true, ssl_enabled=false, log_level=DEBUG, thread_pool_size=16, buffer_size=65536"
    )
    params_b = (
        "HTTP Server Configuration Profile Beta: host=127.0.0.1, port=443, max_connections=200, "
        "timeout=120s, keepalive=false, ssl_enabled=true, log_level=ERROR, thread_pool_size=4, buffer_size=16384"
    )
    p9 = LabeledTextPair(
        pair_id="eval_hard_neg_params_009",
        doc_a_id="cfg_alpha",
        doc_b_id="cfg_beta",
        text_a=params_a,
        text_b=params_b,
        is_true_duplicate=False,
        category="hard_negative_technical_overlap",
        description="Identical configuration key template with entirely distinct production values",
    )

    # 10. Distant negative: Literature vs Technical (Negative)
    doc_frankenstein = (
        "I am by birth a Genevese, and my family is one of the most distinguished of that republic. "
        "My ancestors had been for many years counsellors and syndics, and my father had filled several "
        "public situations with honour and reputation. He was respected by all who knew him for his integrity."
    )
    p10 = LabeledTextPair(
        pair_id="eval_distant_neg_010",
        doc_a_id="doc_base",
        doc_b_id="frank_001",
        text_a=base_text,
        text_b=doc_frankenstein,
        is_true_duplicate=False,
        category="distant_negative",
        description="Completely different topic, author, genre, and vocabulary",
    )

    # 11. Partial overlap: 40% shared text + 60% diverging chemical text (Negative)
    partial_text = (
        "Language intelligence requires an uncompromising commitment to verified provenance. "
        "The VEDA architecture demonstrates that foundational models can be trained strictly on "
        "reagents undergoing catalytic dehydrogenation in pressurized autoclave vessels."
    )
    p11 = LabeledTextPair(
        pair_id="eval_partial_overlap_011",
        doc_a_id="doc_base",
        doc_b_id="doc_partial",
        text_a=base_text,
        text_b=partial_text,
        is_true_duplicate=False,
        category="partial_overlap_negative",
        description="Passage sharing 40% opening words then diverging into distinct chemical prose",
    )

    # 12. Critical numerical / semantic inversion: dosage and safety outcome (Negative)
    t_safe = (
        "Clinical trial dosage protocol: administer 5.0 milligrams of active compound per kilogram daily. "
        "The treatment demonstrated safety with zero adverse cardiac events observed in Phase 1 trials."
    )
    t_toxic = (
        "Clinical trial dosage protocol: administer 50.0 milligrams of active compound per kilogram daily. "
        "The treatment demonstrated toxicity with severe adverse cardiac events observed in Phase 1 trials."
    )
    p12 = LabeledTextPair(
        pair_id="eval_critical_numerical_inversion_012",
        doc_a_id="doc_safe",
        doc_b_id="doc_toxic",
        text_a=t_safe,
        text_b=t_toxic,
        is_true_duplicate=False,
        category="hard_negative_semantic_inversion",
        description="Subtle numerical dosage and adverse outcome inversion (high lexical overlap, fatal semantic divergence)",
    )

    return [p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12]


def build_safety_critical_pairs() -> List[LabeledTextPair]:
    """Returns the 5 Phase 4.5 safety-critical evaluation pairs."""
    p13 = LabeledTextPair(
        pair_id="eval_safety_dosage_013",
        doc_a_id="doc_dose_10",
        doc_b_id="doc_dose_100",
        text_a=(
            "The pediatric patient was administered 10mg of active medication every morning before breakfast. "
            "Vital signs remained completely stable throughout observation."
        ),
        text_b=(
            "The pediatric patient was administered 100mg of active medication every morning before breakfast. "
            "Vital signs remained completely stable throughout observation."
        ),
        is_true_duplicate=False,
        category="safety_numerical_inversion",
        description="Critical 10x pediatric dosage inversion (10mg vs 100mg)",
    )

    p14 = LabeledTextPair(
        pair_id="eval_safety_unit_014",
        doc_a_id="doc_unit_mg",
        doc_b_id="doc_unit_g",
        text_a=(
            "The research team confirmed that exactly 1000 mg of sodium chloride was dissolved in one liter of distilled water at room temperature."
        ),
        text_b=(
            "The research team confirmed that exactly 1 g of sodium chloride was dissolved in one liter of distilled water at room temperature."
        ),
        is_true_duplicate=True,
        category="safety_unit_conversion_duplicate",
        description="Valid duplicate utilizing standard SI unit conversion (1000 mg = 1 g)",
    )

    p15 = LabeledTextPair(
        pair_id="eval_safety_date_015",
        doc_a_id="doc_date_1824",
        doc_b_id="doc_date_1827",
        text_a=(
            "The definitive treaty of friendship and commerce was officially ratified in London in 1824 following three years of bilateral diplomatic negotiations."
        ),
        text_b=(
            "The definitive treaty of friendship and commerce was officially ratified in London in 1827 following three years of bilateral diplomatic negotiations."
        ),
        is_true_duplicate=False,
        category="safety_temporal_date_inversion",
        description="Single calendar year historical discrepancy (1824 vs 1827)",
    )

    p16 = LabeledTextPair(
        pair_id="eval_safety_negation_016",
        doc_a_id="doc_safe_assay",
        doc_b_id="doc_toxic_assay",
        text_a=(
            "The novel organic compound was evaluated in preclinical assays and demonstrated to be safe and non-toxic across all cellular cell lines tested."
        ),
        text_b=(
            "The novel organic compound was evaluated in preclinical assays and demonstrated to be toxic and dangerous across all cellular cell lines tested."
        ),
        is_true_duplicate=False,
        category="safety_polarity_inversion",
        description="Safety polarity flip: safe/non-toxic vs toxic/dangerous",
    )

    p17 = LabeledTextPair(
        pair_id="eval_safety_paraphrase_017",
        doc_a_id="doc_para_a",
        doc_b_id="doc_para_b",
        text_a=(
            "The clinical trial supervisor instructed nurses that 500 mg of antibiotic should be administered to patients every eight hours with water."
        ),
        text_b=(
            "Nurses were instructed by the clinical trial supervisor that 500 mg of antibiotic should be administered to patients every eight hours with water."
        ),
        is_true_duplicate=True,
        category="safety_valid_paraphrase_duplicate",
        description="Legitimate grammatical voice paraphrase with identical quantities and polarity",
    )

    return [p13, p14, p15, p16, p17]


def build_phase45_safety_test_set() -> List[LabeledTextPair]:
    """Expanded Phase 4.5 safety test set (17 pairs = 12 baseline + 5 safety critical)."""
    return build_eval_labeled_test_set() + build_safety_critical_pairs()


def build_default_labeled_test_set() -> List[LabeledTextPair]:
    """Default evaluation fixture returning the 12-pair held-out benchmark."""
    return build_eval_labeled_test_set()


def _wilson_score_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Calculates Wilson score 95% confidence interval for a binomial proportion."""
    if total == 0:
        return 0.0, 0.0
    p_hat = successes / total
    denom = 1 + (z ** 2) / total
    center = (p_hat + (z ** 2) / (2 * total)) / denom
    margin = (z / denom) * ((p_hat * (1 - p_hat) / total + (z ** 2) / (4 * (total ** 2))) ** 0.5)
    return round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)


def evaluate_near_duplicate_strategy(
    detector: Optional[MinHashLSHCandidateDetector] = None,
    labeled_pairs: Optional[List[LabeledTextPair]] = None,
    threshold: float = 0.80,
    safety_guard: Optional[SemanticSafetyGuard] = None,
) -> Dict[str, Any]:
    """
    Evaluates MinHash/LSH candidate detection and Stage 3 Semantic Safety Guard
    against labeled ground truth pairs.
    Separately measures:
    1. Candidate Retrieval Stage (LSH band collisions).
    2. Similarity Threshold Stage (signature Jaccard estimate >= threshold).
    3. Semantic Safety-Aware Decision Stage (verifying quantities, units, dates, polarity).
    Reports precision, recall, specificity, F1, false positives, false negatives,
    false merges prevented, Wilson confidence intervals, and candidate filtering selectivity.
    """
    if detector is None:
        detector = MinHashLSHCandidateDetector(threshold=threshold)
    if labeled_pairs is None:
        labeled_pairs = build_eval_labeled_test_set()
    if safety_guard is None:
        safety_guard = SemanticSafetyGuard()

    start_time = time.perf_counter()

    # Stage 1: Candidate Retrieval (LSH collision) counters
    cand_tp = 0
    cand_fp = 0
    cand_tn = 0
    cand_fn = 0

    # Stage 2: Pure MinHash Threshold Decision counters
    s2_tp = 0
    s2_fp = 0
    s2_tn = 0
    s2_fn = 0

    # Stage 3: Semantic Safety Decision counters (Final Safe Merge Decision)
    tp = 0
    fp = 0
    tn = 0
    fn = 0

    false_merges_prevented = 0
    conflicts_detected: List[Dict[str, Any]] = []
    false_positives: List[Dict[str, Any]] = []
    false_negatives: List[Dict[str, Any]] = []
    pair_results: List[Dict[str, Any]] = []

    for pair in labeled_pairs:
        # Shingle ground truth Jaccard
        shingles_a = get_k_shingles(pair.text_a, detector.k_shingle)
        shingles_b = get_k_shingles(pair.text_b, detector.k_shingle)
        true_jaccard = jaccard_similarity(shingles_a, shingles_b)

        # Stage 1: Isolated LSH candidate retrieval test
        pair_lsh = MinHashLSHCandidateDetector(
            threshold=threshold,
            num_perm=detector.num_perm,
            num_bands=detector.num_bands,
            k_shingle=detector.k_shingle,
        )
        pair_lsh.index_document(pair.doc_a_id, pair.text_a)
        retrieved_candidates = pair_lsh.query_candidates(pair.text_b)
        is_retrieved_candidate = (pair.doc_a_id in retrieved_candidates)

        if pair.is_true_duplicate and is_retrieved_candidate:
            cand_tp += 1
        elif not pair.is_true_duplicate and is_retrieved_candidate:
            cand_fp += 1
        elif not pair.is_true_duplicate and not is_retrieved_candidate:
            cand_tn += 1
        else:
            cand_fn += 1

        # Stage 2: MinHash signature estimate & threshold decision
        sig_a = detector.compute_signature(pair.text_a)
        sig_b = detector.compute_signature(pair.text_b)
        est_jaccard = detector.estimate_similarity(sig_a, sig_b)

        words_a = set(re.findall(r"\b[a-zA-Z0-9_%-]+\b", pair.text_a.lower()))
        words_b = set(re.findall(r"\b[a-zA-Z0-9_%-]+\b", pair.text_b.lower()))
        token_jaccard = len(words_a & words_b) / len(words_a | words_b) if (words_a | words_b) else 1.0
        candidate_similarity = max(est_jaccard, token_jaccard)
        predicted_candidate = candidate_similarity >= threshold

        if pair.is_true_duplicate and predicted_candidate:
            s2_tp += 1
        elif not pair.is_true_duplicate and predicted_candidate:
            s2_fp += 1
        elif not pair.is_true_duplicate and not predicted_candidate:
            s2_tn += 1
        else:
            s2_fn += 1

        # Stage 3: Semantic Safety-Aware Decision Guard
        if predicted_candidate:
            safety_res = safety_guard.verify_pair(pair.text_a, pair.text_b)
            final_merge_decision = safety_res.is_safe_to_merge
            if not final_merge_decision:
                conflicts_detected.append({
                    "pair_id": pair.pair_id,
                    "conflict_type": safety_res.conflict_type,
                    "reason": safety_res.reason,
                    "details": safety_res.details,
                })
                if not pair.is_true_duplicate:
                    false_merges_prevented += 1
        else:
            final_merge_decision = False
            safety_res = SafetyVerificationResult(
                is_safe_to_merge=False,
                conflict_detected=False,
                reason="Below candidate similarity threshold",
            )

        result_entry = {
            "pair_id": pair.pair_id,
            "category": pair.category,
            "true_jaccard": round(true_jaccard, 4),
            "est_jaccard": round(est_jaccard, 4),
            "is_true_duplicate": pair.is_true_duplicate,
            "is_retrieved_candidate": is_retrieved_candidate,
            "stage2_candidate": predicted_candidate,
            "stage3_safe_merge": final_merge_decision,
            "predicted_duplicate": final_merge_decision,
            "safety_conflict": safety_res.conflict_type,
            "safety_reason": safety_res.reason,
        }
        pair_results.append(result_entry)

        if pair.is_true_duplicate and final_merge_decision:
            tp += 1
        elif not pair.is_true_duplicate and final_merge_decision:
            fp += 1
            false_positives.append({
                "pair_id": pair.pair_id,
                "description": pair.description,
                "true_jaccard": true_jaccard,
                "est_jaccard": est_jaccard,
            })
        elif not pair.is_true_duplicate and not final_merge_decision:
            tn += 1
        else:
            fn += 1
            false_negatives.append({
                "pair_id": pair.pair_id,
                "description": pair.description,
                "true_jaccard": true_jaccard,
                "est_jaccard": est_jaccard,
            })

    elapsed = time.perf_counter() - start_time
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (tp + tn) / len(labeled_pairs) if labeled_pairs else 0.0

    cand_recall = cand_tp / (cand_tp + cand_fn) if (cand_tp + cand_fn) > 0 else 0.0
    cand_selectivity = cand_tn / (cand_tn + cand_fp) if (cand_tn + cand_fp) > 0 else 0.0

    s2_precision = s2_tp / (s2_tp + s2_fp) if (s2_tp + s2_fp) > 0 else 0.0
    s2_recall = s2_tp / (s2_tp + s2_fn) if (s2_tp + s2_fn) > 0 else 0.0
    s2_f1 = (2 * s2_precision * s2_recall) / (s2_precision + s2_recall) if (s2_precision + s2_recall) > 0 else 0.0
    s2_accuracy = (s2_tp + s2_tn) / len(labeled_pairs) if labeled_pairs else 0.0

    prec_ci = _wilson_score_interval(tp, tp + fp) if (tp + fp) > 0 else (0.0, 0.0)
    rec_ci = _wilson_score_interval(tp, tp + fn) if (tp + fn) > 0 else (0.0, 0.0)

    return {
        "benchmark_type": "smoke_test_developmental",
        "methodology_disclaimer": (
            "MinHash/LSH is evaluated strictly as a scalable candidate-retrieval method. "
            "Stage 3 Semantic Safety Guard performs semantic verification before any record merge."
        ),
        "sample_size_limitation": (
            f"Evaluated on N={len(labeled_pairs)} calibrated synthetic pairs. "
            "This serves as an algorithmic smoke test, not a production-scale accuracy claim."
        ),
        "threshold": threshold,
        "total_evaluated_pairs": len(labeled_pairs),
        "stage1_candidate_retrieval": {
            "cand_true_positives": cand_tp,
            "cand_false_positives": cand_fp,
            "cand_true_negatives": cand_tn,
            "cand_false_negatives": cand_fn,
            "candidate_recall": round(cand_recall, 4),
            "candidate_selectivity": round(cand_selectivity, 4),
        },
        "stage2_similarity_threshold": {
            "true_positives": s2_tp,
            "false_positives": s2_fp,
            "true_negatives": s2_tn,
            "false_negatives": s2_fn,
            "precision": round(s2_precision, 4),
            "recall": round(s2_recall, 4),
            "f1_score": round(s2_f1, 4),
            "accuracy": round(s2_accuracy, 4),
        },
        "stage3_safety_decision": {
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "false_merges_prevented": false_merges_prevented,
            "conflicts_detected": conflicts_detected,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "specificity": round(specificity, 4),
            "f1_score": round(f1, 4),
            "accuracy": round(accuracy, 4),
            "precision_95_ci": prec_ci,
            "recall_95_ci": rec_ci,
        },
        # Backwards-compatible top-level keys (representing the final safe merge decision)
        "true_positives": tp,
        "false_positives": fp,
        "true_negatives": tn,
        "false_negatives": fn,
        "false_merges_prevented": false_merges_prevented,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "f1_score": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "precision_95_ci": prec_ci,
        "recall_95_ci": rec_ci,
        "elapsed_seconds": round(elapsed, 4),
        "pair_results": pair_results,
        "false_positive_examples": false_positives,
        "false_negative_examples": false_negatives,
    }


def benchmark_near_dedup_runtime(
    sample_text_lengths: Tuple[int, ...] = (100, 500, 2000, 5000),
    warmup_runs: int = 5,
    timed_runs: int = 30,
) -> Dict[str, Any]:
    """
    Empirically benchmarks MinHash signature computation and LSH query latency
    across multiple text lengths with warm-up runs and summary statistics.
    """
    import os
    import statistics

    detector = MinHashLSHCandidateDetector(num_perm=128, num_bands=16, k_shingle=5)
    base_corpus = (
        "Language intelligence requires an uncompromising commitment to verified provenance. "
        "The VEDA architecture demonstrates that foundational models can be trained strictly on "
        "auditable, legally verified, and high-quality texts without web-scraping shortcuts. "
    ) * 50

    results_by_length: Dict[str, Any] = {}

    for length in sample_text_lengths:
        sample = base_corpus[:length]

        # Warm-up runs
        for _ in range(warmup_runs):
            _ = detector.compute_signature(sample)

        # Timed signature generation runs
        durations_ms: List[float] = []
        for _ in range(timed_runs):
            t0 = time.perf_counter()
            _ = detector.compute_signature(sample)
            t1 = time.perf_counter()
            durations_ms.append((t1 - t0) * 1000.0)

        mean_ms = statistics.mean(durations_ms)
        std_ms = statistics.stdev(durations_ms) if len(durations_ms) > 1 else 0.0
        chars_per_sec = (length / (mean_ms / 1000.0)) if mean_ms > 0 else 0.0

        results_by_length[f"{length}_chars"] = {
            "text_length_chars": length,
            "timed_runs": timed_runs,
            "mean_latency_ms": round(mean_ms, 3),
            "std_latency_ms": round(std_ms, 3),
            "min_latency_ms": round(min(durations_ms), 3),
            "max_latency_ms": round(max(durations_ms), 3),
            "throughput_chars_per_sec": round(chars_per_sec, 1),
        }

    return {
        "hardware_environment": {
            "os_name": os.name,
            "cpu_cores_logical": os.cpu_count() or 1,
        },
        "config": {
            "num_perm": detector.num_perm,
            "num_bands": detector.num_bands,
            "k_shingle": detector.k_shingle,
            "warmup_runs": warmup_runs,
            "timed_runs": timed_runs,
        },
        "results": results_by_length,
    }

