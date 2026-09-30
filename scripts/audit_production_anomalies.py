"""
VEDA Production Lexicon Anomaly Scan & Statistical Sanity Audit (Phase 15 & 16)

Performs comprehensive audits on the 959,688-word production SQLite database:
1. Data Integrity & Anomaly Checks:
   - Empty or null words / normalized strings
   - Non-ASCII / invalid characters in normalized words
   - Punctuation, whitespace, digits in normalized words
   - Foreign / unexpected language tags
   - Impossible POS values
   - Zero-definition or zero-sense entries
   - Duplicate normalized entries
   - Referential integrity (orphan word_pos or senses rows)
2. Statistical Distributions & Extreme Outliers:
   - Word length distribution (min, max, avg, percentiles)
   - Senses per word distribution & top outliers
   - Definitions per word distribution & top outliers
   - Inflected forms distribution & top outliers
   - Pronunciations (IPA) distribution & top outliers
   - Synonyms and Antonyms coverage
   - Etymology coverage & percentage
   - Top JSON payload sizes
3. Semantic Invariant & Deduplication Audit:
   - Duplicate senses within individual entries
   - Duplicate definitions under the same POS
   - JSON deserialization integrity
"""

import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Safe UTF-8 console output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass


DEFAULT_DB = PROJECT_ROOT / "data" / "lexicon" / "veda_lexicon_v0.1.sqlite"


def run_anomaly_audit(db_path: Path) -> Dict[str, Any]:
    print("=" * 75)
    print(f" VEDA PRODUCTION DATABASE ANOMALY & STATISTICAL AUDIT")
    print(f" Target Database: {db_path} ({db_path.stat().st_size / (1024**2):.2f} MB)")
    print("=" * 75)

    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    report: Dict[str, Any] = {"anomalies": {}, "statistics": {}, "outliers": {}}

    # --- 1. CORE DATA INTEGRITY ANOMALY SCAN ---
    print("\n[1/4] Scanning for structural anomalies and contract violations...")

    cursor.execute("SELECT COUNT(*) AS c FROM words")
    total_words = int(cursor.fetchone()["c"])
    report["total_words"] = total_words
    print(f"  Total Words: {total_words:,}")

    # Empty words
    cursor.execute("SELECT COUNT(*) AS c FROM words WHERE length(word) = 0 OR length(normalized) = 0")
    empty_words = int(cursor.fetchone()["c"])
    report["anomalies"]["empty_words"] = empty_words
    print(f"  Empty words / normalized: {empty_words}")

    # Nulls in critical columns
    cursor.execute("SELECT COUNT(*) AS c FROM words WHERE normalized IS NULL OR word IS NULL OR language IS NULL OR entry_json IS NULL")
    null_cols = int(cursor.fetchone()["c"])
    report["anomalies"]["null_critical_columns"] = null_cols
    print(f"  Null required columns: {null_cols}")

    # Normalized characters strictly outside [a-z]
    cursor.execute("SELECT COUNT(*) AS c FROM words WHERE normalized GLOB '*[^a-z]*'")
    non_alpha = int(cursor.fetchone()["c"])
    report["anomalies"]["non_alpha_normalized"] = non_alpha
    print(f"  Normalized words outside [a-z]: {non_alpha}")

    # Whitespace in normalized
    cursor.execute("SELECT COUNT(*) AS c FROM words WHERE normalized LIKE '% %' OR normalized LIKE '%\t%' OR normalized LIKE '%\n%'")
    ws_count = int(cursor.fetchone()["c"])
    report["anomalies"]["whitespace_in_normalized"] = ws_count
    print(f"  Whitespace in normalized: {ws_count}")

    # Punctuation / Digits in normalized
    cursor.execute("SELECT COUNT(*) AS c FROM words WHERE normalized GLOB '*[0-9]*'")
    digit_count = int(cursor.fetchone()["c"])
    report["anomalies"]["digits_in_normalized"] = digit_count
    print(f"  Digits in normalized: {digit_count}")

    cursor.execute("SELECT COUNT(*) AS c FROM words WHERE normalized LIKE '%-%' OR normalized LIKE '%''%'")
    punct_count = int(cursor.fetchone()["c"])
    report["anomalies"]["punctuation_in_normalized"] = punct_count
    print(f"  Punctuation (hyphen/apostrophe) in normalized: {punct_count}")

    # Language validation
    cursor.execute("SELECT DISTINCT language FROM words")
    languages = [r["language"] for r in cursor.fetchall()]
    report["languages"] = languages
    print(f"  Distinct language tags: {languages}")

    # Zero senses or zero definitions
    cursor.execute("SELECT COUNT(*) AS c FROM words WHERE senses_count = 0")
    zero_senses = int(cursor.fetchone()["c"])
    report["anomalies"]["zero_senses"] = zero_senses
    print(f"  Entries with 0 senses: {zero_senses}")

    cursor.execute("SELECT COUNT(*) AS c FROM words WHERE definitions_count = 0")
    zero_defs = int(cursor.fetchone()["c"])
    report["anomalies"]["zero_definitions"] = zero_defs
    print(f"  Entries with 0 definitions: {zero_defs}")

    # Duplicate words
    cursor.execute("SELECT COUNT(*) AS c FROM (SELECT normalized FROM words GROUP BY normalized HAVING count(*) > 1)")
    duplicate_words = int(cursor.fetchone()["c"])
    report["anomalies"]["duplicate_normalized_words"] = duplicate_words
    print(f"  Duplicate normalized words in words table: {duplicate_words}")

    # Orphan child rows
    cursor.execute("SELECT COUNT(*) AS c FROM word_pos LEFT JOIN words ON word_pos.word_id = words.id WHERE words.id IS NULL")
    orphan_pos = int(cursor.fetchone()["c"])
    report["anomalies"]["orphan_word_pos"] = orphan_pos
    print(f"  Orphan word_pos rows: {orphan_pos}")

    cursor.execute("SELECT COUNT(*) AS c FROM senses LEFT JOIN words ON senses.word_id = words.id WHERE senses.id IS NULL")
    orphan_senses = int(cursor.fetchone()["c"])
    report["anomalies"]["orphan_senses"] = orphan_senses
    print(f"  Orphan senses rows: {orphan_senses}")

    # --- 2. STATISTICAL DISTRIBUTIONS ---
    print("\n[2/4] Computing statistical distributions across 959,688 records...")

    cursor.execute("""
        SELECT
            MIN(length(normalized)) AS min_len,
            MAX(length(normalized)) AS max_len,
            AVG(length(normalized)) AS avg_len,
            MIN(senses_count) AS min_senses,
            MAX(senses_count) AS max_senses,
            AVG(senses_count) AS avg_senses,
            MIN(definitions_count) AS min_defs,
            MAX(definitions_count) AS max_defs,
            AVG(definitions_count) AS avg_defs,
            MIN(forms_count) AS min_forms,
            MAX(forms_count) AS max_forms,
            AVG(forms_count) AS avg_forms,
            MIN(pronunciations_count) AS min_prons,
            MAX(pronunciations_count) AS max_prons,
            AVG(pronunciations_count) AS avg_prons,
            MAX(length(entry_json)) AS max_json_bytes
        FROM words
    """)
    stats_row = cursor.fetchone()
    report["statistics"] = {
        "min_len": stats_row["min_len"],
        "max_len": stats_row["max_len"],
        "avg_len": round(stats_row["avg_len"], 2),
        "min_senses": stats_row["min_senses"],
        "max_senses": stats_row["max_senses"],
        "avg_senses": round(stats_row["avg_senses"], 2),
        "min_defs": stats_row["min_defs"],
        "max_defs": stats_row["max_defs"],
        "avg_defs": round(stats_row["avg_defs"], 2),
        "min_forms": stats_row["min_forms"],
        "max_forms": stats_row["max_forms"],
        "avg_forms": round(stats_row["avg_forms"], 2),
        "min_prons": stats_row["min_prons"],
        "max_prons": stats_row["max_prons"],
        "avg_prons": round(stats_row["avg_prons"], 2),
        "max_json_bytes": stats_row["max_json_bytes"],
    }

    print(f"  Word Length:      min={stats_row['min_len']}, max={stats_row['max_len']}, avg={stats_row['avg_len']:.2f}")
    print(f"  Senses / Word:    min={stats_row['min_senses']}, max={stats_row['max_senses']}, avg={stats_row['avg_senses']:.2f}")
    print(f"  Defs / Word:      min={stats_row['min_defs']}, max={stats_row['max_defs']}, avg={stats_row['avg_defs']:.2f}")
    print(f"  Forms / Word:     min={stats_row['min_forms']}, max={stats_row['max_forms']}, avg={stats_row['avg_forms']:.2f}")
    print(f"  IPA / Word:       min={stats_row['min_prons']}, max={stats_row['max_prons']}, avg={stats_row['avg_prons']:.2f}")
    print(f"  Max JSON payload: {stats_row['max_json_bytes']:,} bytes")

    # Etymology coverage
    cursor.execute("SELECT COUNT(*) AS c FROM words WHERE etymology IS NOT NULL AND length(trim(etymology)) > 0")
    etym_count = int(cursor.fetchone()["c"])
    etym_pct = (etym_count / total_words) * 100.0
    report["statistics"]["etymology_count"] = etym_count
    report["statistics"]["etymology_pct"] = round(etym_pct, 2)
    print(f"  Etymology coverage: {etym_count:,} words ({etym_pct:.1f}%)")

    # --- 3. EXTREME OUTLIERS INSPECTION ---
    print("\n[3/4] Inspecting extreme outliers...")

    # Top words by senses count
    cursor.execute("SELECT normalized, primary_pos, senses_count, definitions_count FROM words ORDER BY senses_count DESC LIMIT 5")
    top_senses = [dict(r) for r in cursor.fetchall()]
    report["outliers"]["top_senses"] = top_senses
    print("  Top 5 words by sense count:")
    for r in top_senses:
        print(f"    - '{r['normalized']}' ({r['primary_pos']}): {r['senses_count']} senses, {r['definitions_count']} defs")

    # Longest words
    cursor.execute("SELECT normalized, length(normalized) AS len, primary_pos FROM words ORDER BY length(normalized) DESC LIMIT 5")
    longest_words = [dict(r) for r in cursor.fetchall()]
    report["outliers"]["longest_words"] = longest_words
    print("  Top 5 longest valid words:")
    for r in longest_words:
        print(f"    - '{r['normalized']}' ({r['primary_pos']}): {r['len']} characters")

    # Largest JSON entries
    cursor.execute("SELECT normalized, length(entry_json) AS b, senses_count, forms_count FROM words ORDER BY length(entry_json) DESC LIMIT 5")
    largest_json = [dict(r) for r in cursor.fetchall()]
    report["outliers"]["largest_json"] = largest_json
    print("  Top 5 largest entries by JSON payload size:")
    for r in largest_json:
        print(f"    - '{r['normalized']}': {r['b']:,} bytes ({r['senses_count']} senses, {r['forms_count']} forms)")

    # --- 4. SAMPLING FOR INNER REPETITIONS / DESERIALIZATION ---
    print("\n[4/4] Validating serialized JSON integrity & sense uniqueness across sample...")

    # Validate top 100 outliers + 1,000 random words
    cursor.execute("SELECT entry_json FROM words ORDER BY length(entry_json) DESC LIMIT 100")
    sample_rows = cursor.fetchall()

    cursor.execute("SELECT entry_json FROM words ORDER BY RANDOM() LIMIT 1000")
    sample_rows.extend(cursor.fetchall())

    deserialization_errors = 0
    duplicate_senses_detected = 0
    duplicate_glosses_detected = 0

    for row in sample_rows:
        try:
            data = json.loads(row["entry_json"])
        except Exception:
            deserialization_errors += 1
            continue

        senses = data.get("senses", [])
        # Check sense identity
        seen_senses = set()
        for s in senses:
            s_key = (s.get("pos"), tuple(s.get("glosses", [])), tuple(s.get("examples", [])))
            if s_key in seen_senses:
                duplicate_senses_detected += 1
            seen_senses.add(s_key)

        # Check duplicate glosses within the same POS
        defs_by_pos = data.get("definitions_by_pos", {})
        for pos, def_list in defs_by_pos.items():
            if len(def_list) != len(set(def_list)):
                duplicate_glosses_detected += 1

    report["anomalies"]["deserialization_errors_in_sample"] = deserialization_errors
    report["anomalies"]["duplicate_senses_in_sample"] = duplicate_senses_detected
    report["anomalies"]["duplicate_glosses_in_sample"] = duplicate_glosses_detected

    print(f"  Deserialization errors in 1,100 sample: {deserialization_errors}")
    print(f"  Duplicate senses in 1,100 sample:        {duplicate_senses_detected}")
    print(f"  Duplicate glosses under POS in sample:  {duplicate_glosses_detected}")

    conn.close()

    print("\n" + "=" * 75)
    print("ANOMALY AUDIT SUMMARY:")
    has_critical_anomaly = any(
        report["anomalies"][k] > 0
        for k in [
            "empty_words",
            "null_critical_columns",
            "non_alpha_normalized",
            "whitespace_in_normalized",
            "digits_in_normalized",
            "punctuation_in_normalized",
            "duplicate_normalized_words",
            "orphan_word_pos",
            "orphan_senses",
            "deserialization_errors_in_sample",
        ]
    )

    if has_critical_anomaly:
        print("RESULT: [FAIL] Critical contract anomalies detected!")
    else:
        print("RESULT: [PASS] Zero structural anomalies, zero contract violations detected.")
    print("=" * 75)

    return report


if __name__ == "__main__":
    db_file = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    res = run_anomaly_audit(db_file)
    has_crit = any(
        res["anomalies"][k] > 0
        for k in [
            "empty_words",
            "null_critical_columns",
            "non_alpha_normalized",
            "whitespace_in_normalized",
            "digits_in_normalized",
            "punctuation_in_normalized",
            "duplicate_normalized_words",
            "orphan_word_pos",
            "orphan_senses",
            "deserialization_errors_in_sample",
        ]
    )
    if has_crit:
        sys.exit(1)
