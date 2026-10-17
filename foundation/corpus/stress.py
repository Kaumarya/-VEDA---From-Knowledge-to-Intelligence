"""
VEDA Synthetic Stress Corpus Generator (Phase 4.1 — Hardening & Certification)

Generates deterministic, parameterized synthetic stress documents featuring all
adversarial edge cases: duplicates, accented Latin, non-Latin, corrupted Unicode,
pathological whitespace, extreme lengths, boilerplate, and crawler loops.
"""

from __future__ import annotations

import random
from typing import Dict, List, Tuple

from foundation.corpus.schemas import CorpusDocument, CorpusSource, LicensingStatus


def generate_synthetic_stress_corpus(
    num_documents: int = 5000,
    seed: int = 42,
) -> Tuple[List[CorpusSource], List[CorpusDocument]]:
    """
    Generates a deterministic synthetic stress dataset with controlled proportions
    of adversarial edge cases and valid prose.
    """
    rng = random.Random(seed)

    source_permitted = CorpusSource(
        source_id="stress_permitted_src",
        name="VEDA Synthetic Stress Permitted Source",
        version="1.0",
        url_or_path="https://veda.local/stress_permitted.tar.gz",
        acquisition_date="2026-10-02",
        source_hash="11" * 32,
        license="CC0-1.0",
        licensing_status=LicensingStatus.VERIFIED_PERMITTED,
    )
    source_excluded = CorpusSource(
        source_id="stress_excluded_src",
        name="VEDA Synthetic Stress Excluded Source",
        version="1.0",
        url_or_path="https://veda.local/stress_excluded.tar.gz",
        acquisition_date="2026-10-02",
        source_hash="22" * 32,
        license="Proprietary",
        licensing_status=LicensingStatus.EXCLUDED,
    )
    sources = [source_permitted, source_excluded]

    valid_templates = [
        "The scientific method remains humanity's most dependable instrument for discovering natural laws.\n\nThrough rigorous empirical observation, controlled experimentation, and reproducible analysis, researchers separate persistent truth from temporary illusion.",
        "The café serves naïve patrons résumé advice with great care and diligence.\n\nPoincaré and Gödel explored foundational mathematics, discovering profound theorems about logic and formal systems.",
        "In 1772, the expedition recorded a temperature of 24° with an error margin of ±2°.\n\nOver 365 days, exactly 1,420 nautical miles were surveyed across the southern hemisphere with patience.",
        "“Knowledge is not merely information,” the scholar remarked, “it is understanding.”\n\nWe must distinguish between the ordinary—often superficial—facts and deep wisdom… indeed, wisdom’s path requires patience.",
        "<p>The <b>World Wide Web</b> operates on standardized protocols such as HTTP &amp; HTTPS.</p>\n\n<div>For full documentation, visit https://example.org/standards?spec=html5 &amp; read the official guide.</div>",
    ]

    documents: List[CorpusDocument] = []

    # Keep a pool of canonical documents to create exact duplicates
    canonical_pool: List[str] = []

    for i in range(num_documents):
        doc_id = f"stress_doc_{i:06d}"
        case_type = rng.random()

        if case_type < 0.45:
            # 1. Valid English prose (with typography, accents, math)
            template = rng.choice(valid_templates)
            raw_text = f"Document Section {i}: {template}"
            src_id = "stress_permitted_src"
            if len(canonical_pool) < 20:
                canonical_pool.append(raw_text)

        elif case_type < 0.55:
            # 2. Exact duplicate of previously generated document
            if canonical_pool:
                raw_text = rng.choice(canonical_pool)
            else:
                raw_text = valid_templates[0]
            src_id = "stress_permitted_src"

        elif case_type < 0.62:
            # 3. Pathological whitespace & control characters
            raw_text = f"Section {i}: Abnormal\t\twhitespace\u00a0\u00a0and\x00nulls.\n\n\n\n\nParagraph two with\t\trunaway spaces   and punctuation."
            src_id = "stress_permitted_src"

        elif case_type < 0.69:
            # 4. Very short fragments (too short chars / words)
            raw_text = rng.choice(["Hi.", "Short.", "No.", "A\n\nB\n\nC", "1 2 3"])
            src_id = "stress_permitted_src"

        elif case_type < 0.75:
            # 5. Non-Latin scripts (Hindi, Russian, Chinese)
            raw_text = rng.choice([
                "नमस्ते दोस्तों, यह एक हिंदी वाक्य है जो मॉडल में नहीं जाना चाहिए।\n\nधन्यवाद।",
                "Москва — столица России, крупнейший по численности населения город страны.\n\nРоссия.",
                "这是一个中文段落，用于测试非拉丁字母语言在系统中的过滤和隔离行为。",
            ])
            src_id = "stress_permitted_src"

        elif case_type < 0.81:
            # 6. Character and word repetition loops (crawler traps)
            if rng.random() < 0.5:
                raw_text = f"Corrupted loop {i}: " + "the " * 30 + "end."
            else:
                raw_text = f"Corrupted mash {i}: " + "a" * 25 + " and " + "-" * 30
            src_id = "stress_permitted_src"

        elif case_type < 0.86:
            # 7. Low alpha ratio / ASCII tables / code
            raw_text = "+-------+-------+-------+\n| 12345 | 67890 | 00000 |\n|-------|-------|-------|\n| 99999 | 88888 | 77777 |\n+-------+-------+-------+"
            src_id = "stress_permitted_src"

        elif case_type < 0.92:
            # 8. Boilerplate & Legal notices
            raw_text = f"All rights reserved {i}. Terms of service apply to all users of this service.\n\nPlease review our privacy policy before continuing."
            src_id = "stress_permitted_src"

        elif case_type < 0.96:
            # 9. Governance excluded source
            raw_text = f"This proprietary content {i} belongs to an excluded copyrighted textbook source."
            src_id = "stress_excluded_src"

        elif case_type < 0.98:
            # 10. Empty / whitespace-only text
            raw_text = rng.choice(["", "   ", "\n\n\t\t\n   ", "   \t  "])
            src_id = "stress_permitted_src"

        else:
            # 11. Oversized document / paragraph (> 15,000 chars)
            raw_text = f"Oversized text {i}: " + ("word " * 3500)
            src_id = "stress_permitted_src"

        doc = CorpusDocument(
            document_id=doc_id,
            source_id=src_id,
            raw_text=raw_text,
            title=f"Synthetic Document {i}",
        )
        documents.append(doc)

    return sources, documents
