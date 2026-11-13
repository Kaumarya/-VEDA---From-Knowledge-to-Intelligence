"""
VEDA Candidate Database Subsystem — Database Schema DDL & Definitions
Phase 4.14.2
Reconciled across Architecture Revisions 1, 2, 3, and 4.
"""

# Migration 001: Core Ingestion, Sources, Decisions & Duplicates
MIGRATION_001_CORE = """
-- 1. SCHEMA MIGRATIONS REGISTRY
CREATE TABLE IF NOT EXISTS schema_migrations (
    version             INTEGER PRIMARY KEY,
    name                TEXT NOT NULL,
    applied_at          TEXT NOT NULL,
    checksum            TEXT NOT NULL,
    description         TEXT NOT NULL
);

-- 2. CANDIDATE SOURCES (RELATIONAL CACHE OF SOURCEREGISTRY)
CREATE TABLE IF NOT EXISTS candidate_sources (
    source_id                   TEXT PRIMARY KEY,
    name                        TEXT NOT NULL,
    version                     TEXT NOT NULL,
    licensing_status            TEXT NOT NULL,
    license_name                TEXT NOT NULL,
    training_permitted_status   TEXT NOT NULL,
    commercial_permitted        INTEGER NOT NULL DEFAULT 0,
    artifact_sha256             TEXT NOT NULL,
    registry_entry_sha256       TEXT NOT NULL,
    approval_expiration_date    TEXT,
    attribution                 TEXT,
    sync_timestamp              TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    CONSTRAINT chk_src_licensing_status CHECK (
        licensing_status IN ('VERIFIED PERMITTED', 'REQUIRES REVIEW', 'UNKNOWN', 'EXCLUDED')
    ),
    CONSTRAINT chk_src_training_status CHECK (
        training_permitted_status IN ('EXPLICITLY_PERMITTED', 'REQUIRES_LEGAL_REVIEW', 'EXCLUDED')
    )
);

-- 3. CANDIDATE SUBMISSIONS (MASTER CANDIDATE REGISTRY)
CREATE TABLE IF NOT EXISTS candidate_submissions (
    candidate_id                TEXT PRIMARY KEY,              -- UUIDv4 format
    source_id                   TEXT NOT NULL,                 -- FK to candidate_sources
    source_document_id          TEXT NOT NULL,                 -- Source document/item identifier
    original_text               TEXT NOT NULL,                 -- Verbatim immutable submitted text
    normalized_text             TEXT NOT NULL,                 -- Deterministically normalized text
    raw_content_hash            TEXT NOT NULL,                 -- SHA-256 of original_text
    normalized_content_hash     TEXT NOT NULL,                 -- SHA-256 of normalized_text
    raw_char_count              INTEGER NOT NULL,
    normalized_char_count       INTEGER NOT NULL,
    approx_word_count           INTEGER NOT NULL,
    processing_status           TEXT NOT NULL DEFAULT 'RECEIVED',
    is_canonical                INTEGER NOT NULL DEFAULT 1,    -- 1 if master deduplicated record
    canonical_candidate_id      TEXT,                          -- Self-ref if non-canonical duplicate
    pipeline_version            TEXT NOT NULL DEFAULT 'v0.4.14',
    created_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (source_id) REFERENCES candidate_sources (source_id) ON DELETE RESTRICT,
    FOREIGN KEY (canonical_candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT,

    CONSTRAINT chk_candidate_status CHECK (
        processing_status IN (
            'RECEIVED',
            'PENDING',
            'PROCESSING',
            'PROCESSING_PASSED',
            'APPROVAL_PENDING',
            'APPROVED',
            'REJECTED',
            'QUARANTINED',
            'PROCESSING_FAILED',
            'EXPORT_PENDING',
            'EXPORTED',
            'REVOKED'
        )
    ),
    CONSTRAINT chk_raw_hash_len CHECK (length(raw_content_hash) = 64),
    CONSTRAINT chk_norm_hash_len CHECK (length(normalized_content_hash) = 64),
    CONSTRAINT chk_is_canonical_bool CHECK (is_canonical IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_candidates_status ON candidate_submissions (processing_status);
CREATE INDEX IF NOT EXISTS idx_candidates_norm_hash ON candidate_submissions (normalized_content_hash);
CREATE INDEX IF NOT EXISTS idx_candidates_raw_hash ON candidate_submissions (raw_content_hash);
CREATE INDEX IF NOT EXISTS idx_candidates_source ON candidate_submissions (source_id, created_at);

-- 4. PROCESSING DECISIONS (VERSIONED, APPEND-ONLY AUDIT TRAIL)
CREATE TABLE IF NOT EXISTS processing_decisions (
    decision_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id                TEXT NOT NULL,
    stage_name                  TEXT NOT NULL,                 -- NORMALIZATION, LANGUAGE_FILTER, QUALITY, NEAR_DEDUP, SAFETY
    pipeline_version            TEXT NOT NULL,
    decision_outcome            TEXT NOT NULL,                 -- PASS, FAIL, QUARANTINE, MERGE
    quality_score               REAL,
    language_confidence         REAL,
    failed_metric               TEXT,
    diagnostic_evidence_json    TEXT,
    evaluated_at                TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT,
    CONSTRAINT chk_proc_outcome CHECK (decision_outcome IN ('PASS', 'FAIL', 'QUARANTINE', 'MERGE'))
);

CREATE INDEX IF NOT EXISTS idx_decisions_candidate ON processing_decisions (candidate_id, evaluated_at);

-- 5. DUPLICATE RELATIONSHIPS (EXACT, NEAR & SEMANTIC CONFLICTS)
CREATE TABLE IF NOT EXISTS duplicate_relationships (
    relationship_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id                TEXT NOT NULL,
    related_candidate_id        TEXT NOT NULL,
    relationship_type           TEXT NOT NULL,                 -- EXACT_RAW, EXACT_NORMALIZED, NEAR_DUPLICATE, SEMANTIC_CONFLICT
    detector_version            TEXT NOT NULL,
    similarity_score            REAL NOT NULL,
    is_safe_to_merge            INTEGER NOT NULL DEFAULT 1,    -- 0 if polarity/numerical/date conflict detected
    conflict_reason             TEXT,
    detected_at                 TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT,
    FOREIGN KEY (related_candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT,

    CONSTRAINT chk_rel_type CHECK (
        relationship_type IN ('EXACT_RAW', 'EXACT_NORMALIZED', 'NEAR_DUPLICATE', 'SEMANTIC_CONFLICT')
    ),
    CONSTRAINT chk_safe_merge_bool CHECK (is_safe_to_merge IN (0, 1)),
    CONSTRAINT chk_no_self_duplicate CHECK (candidate_id != related_candidate_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_dup_pair 
ON duplicate_relationships (candidate_id, related_candidate_id, relationship_type);
"""

# Migration 002: Reviewer Accounts, RBAC Roles, Public Keys, Auth & Key Lifecycles
MIGRATION_002_REVIEWER_SECURITY = """
-- 6. REVIEWER ACCOUNTS
CREATE TABLE IF NOT EXISTS reviewer_accounts (
    reviewer_id         TEXT PRIMARY KEY,              -- UUIDv4 format
    username            TEXT NOT NULL UNIQUE,          -- Corporate directory handle
    full_name           TEXT NOT NULL,                 -- Verified human legal name
    email               TEXT NOT NULL UNIQUE,          -- Corporate email
    account_status      TEXT NOT NULL DEFAULT 'ACTIVE',-- ACTIVE, SUSPENDED, INACTIVE, OFFBOARDED
    idp_subject_id      TEXT,                          -- External IdP unique subject identifier
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    CONSTRAINT chk_reviewer_account_status CHECK (
        account_status IN ('ACTIVE', 'SUSPENDED', 'INACTIVE', 'OFFBOARDED')
    )
);

-- 7. REVIEWER ROLES (RBAC TAXONOMY)
CREATE TABLE IF NOT EXISTS reviewer_roles (
    role_id             TEXT PRIMARY KEY,              -- Role identifier
    role_name           TEXT NOT NULL UNIQUE,          -- Display name
    description         TEXT NOT NULL,                 -- Scope of authority
    can_approve_corpus  INTEGER NOT NULL DEFAULT 1,    -- Boolean: 1 if role can grant production approval
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Seed predefined authoritative governance roles
INSERT OR IGNORE INTO reviewer_roles (role_id, role_name, description, can_approve_corpus) VALUES
('ROLE_LEGAL_AUDITOR',   'LEGAL_COMPLIANCE_AUDITOR', 'Authorizes licensing, copyright, and provenance compliance', 1),
('ROLE_DOMAIN_CURATOR',  'DOMAIN_CURATOR',           'Authorizes linguistic quality, register, and dialect accuracy', 1),
('ROLE_SAFETY_OFFICER',  'SAFETY_COMPLIANCE_OFFICER', 'Authorizes resolution of quarantined or sensitive content', 1),
('ROLE_CHIEF_DATA_OFF',  'CHIEF_DATA_OFFICER',       'Executive authority for bulk promotions and policy exceptions', 1),
('ROLE_AUDIT_OBSERVER',  'AUDIT_OBSERVER',           'Read-only inspector with no approval authority', 0);

-- 8. REVIEWER ACCOUNT ROLE ASSIGNMENTS
CREATE TABLE IF NOT EXISTS reviewer_account_roles (
    assignment_id       TEXT PRIMARY KEY,              -- UUIDv4 format
    reviewer_id         TEXT NOT NULL,
    role_id             TEXT NOT NULL,
    assigned_by         TEXT NOT NULL,                 -- Admin reviewer_id
    assigned_at         TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    revoked_at          TEXT,                          -- NULL if actively assigned

    FOREIGN KEY (reviewer_id) REFERENCES reviewer_accounts (reviewer_id) ON DELETE RESTRICT,
    FOREIGN KEY (role_id) REFERENCES reviewer_roles (role_id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_active_role ON reviewer_account_roles (reviewer_id, role_id)
WHERE revoked_at IS NULL;

-- 9. REVIEWER PUBLIC KEYS (NEVER STORES PRIVATE KEYS)
CREATE TABLE IF NOT EXISTS reviewer_public_keys (
    public_key_id       TEXT PRIMARY KEY,              -- Key fingerprint / UUIDv4
    reviewer_id         TEXT NOT NULL,
    algorithm           TEXT NOT NULL DEFAULT 'Ed25519',
    public_key_hex      TEXT NOT NULL UNIQUE,          -- 64 lowercase hex characters (32 bytes)
    key_status          TEXT NOT NULL DEFAULT 'PENDING_ACTIVATION',
    is_test_key         INTEGER NOT NULL DEFAULT 0,    -- 1 = test fixture key, 0 = production key
    activated_at        TEXT,                          -- Timestamp when key became active
    valid_until         TEXT,                          -- Timestamp of scheduled retirement / rotation
    revoked_at          TEXT,                          -- Timestamp of emergency revocation
    revocation_reason   TEXT,                          -- Explanation for revocation
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (reviewer_id) REFERENCES reviewer_accounts (reviewer_id) ON DELETE RESTRICT,

    CONSTRAINT chk_key_algorithm CHECK (algorithm = 'Ed25519'),
    CONSTRAINT chk_key_hex_len CHECK (length(public_key_hex) = 64),
    CONSTRAINT chk_key_status CHECK (
        key_status IN ('PENDING_ACTIVATION', 'ACTIVE', 'ROTATED_RETIRED', 'REVOKED_COMPROMISED', 'REVOKED_ADMIN')
    ),
    CONSTRAINT chk_test_key_bool CHECK (is_test_key IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_pubkeys_reviewer ON reviewer_public_keys (reviewer_id, key_status);

-- 10. AUTHENTICATION EVENTS
CREATE TABLE IF NOT EXISTS authentication_events (
    auth_event_id       TEXT PRIMARY KEY,              -- UUIDv4 format
    reviewer_id         TEXT NOT NULL,
    auth_method         TEXT NOT NULL,                 -- LOCAL_PASSWORD_MFA, OIDC_SSO, FIDO2_WEBAUTHN
    client_host         TEXT NOT NULL,                 -- Client hostname / IP
    auth_status         TEXT NOT NULL,                 -- SUCCESS, FAILURE, EXPIRED
    session_expires_at  TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (reviewer_id) REFERENCES reviewer_accounts (reviewer_id) ON DELETE RESTRICT,
    CONSTRAINT chk_auth_status CHECK (auth_status IN ('SUCCESS', 'FAILURE', 'EXPIRED'))
);

CREATE INDEX IF NOT EXISTS idx_auth_events_reviewer ON authentication_events (reviewer_id, created_at);

-- 11. KEY LIFECYCLE EVENTS
CREATE TABLE IF NOT EXISTS key_lifecycle_events (
    event_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    public_key_id       TEXT NOT NULL,
    previous_status     TEXT,
    new_status          TEXT NOT NULL,
    actor_id            TEXT NOT NULL,                 -- Reviewer or admin ID executing transition
    reason              TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (public_key_id) REFERENCES reviewer_public_keys (public_key_id) ON DELETE RESTRICT
);
"""

# Migration 003: Approval History, Quarantine, Retention, Export Batches, Triggers & Views
MIGRATION_003_APPROVALS_QUARANTINE_EXPORT = """
-- 12. APPROVAL HISTORY (APPEND-ONLY CRYPTOGRAPHIC AUDIT LOG)
CREATE TABLE IF NOT EXISTS approval_history (
    history_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id                TEXT NOT NULL,
    decision_id                 TEXT NOT NULL UNIQUE,          -- UUIDv4 bound into payload
    reviewer_id                 TEXT NOT NULL,                 -- Reviewer identity
    reviewer_role               TEXT NOT NULL,                 -- Role asserted at signing
    public_key_id               TEXT NOT NULL,                 -- Public key used for verification
    auth_event_id               TEXT NOT NULL,                 -- Active session reference
    old_status                  TEXT NOT NULL,
    new_status                  TEXT NOT NULL,
    decision_reason             TEXT NOT NULL,
    canonical_payload_json      TEXT NOT NULL,                 -- Full RFC 8785 canonical JSON string
    canonical_payload_sha256    TEXT NOT NULL,                 -- 64 lowercase hex SHA-256 of payload
    signature_ed25519           TEXT NOT NULL,                 -- 128 lowercase hex characters (64 bytes)
    payload_schema_version      TEXT NOT NULL DEFAULT '1.0',
    verification_status         TEXT NOT NULL DEFAULT 'VERIFIED_VALID',
    created_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT,
    FOREIGN KEY (reviewer_id) REFERENCES reviewer_accounts (reviewer_id) ON DELETE RESTRICT,
    FOREIGN KEY (public_key_id) REFERENCES reviewer_public_keys (public_key_id) ON DELETE RESTRICT,
    FOREIGN KEY (auth_event_id) REFERENCES authentication_events (auth_event_id) ON DELETE RESTRICT,

    CONSTRAINT chk_hist_status CHECK (
        new_status IN ('PROCESSING_PASSED', 'APPROVAL_PENDING', 'APPROVED', 'REJECTED', 'QUARANTINED', 'REVOKED')
    ),
    CONSTRAINT chk_payload_sha256_len CHECK (length(canonical_payload_sha256) = 64),
    CONSTRAINT chk_sig_ed25519_len CHECK (length(signature_ed25519) = 128),
    CONSTRAINT chk_verif_status CHECK (
        verification_status IN ('VERIFIED_VALID', 'VERIFICATION_FAILED', 'REVOKED_POST_APPROVAL')
    )
);

CREATE INDEX IF NOT EXISTS idx_approval_history_candidate ON approval_history (candidate_id, created_at);
CREATE INDEX IF NOT EXISTS idx_approval_history_reviewer ON approval_history (reviewer_id, created_at);
CREATE INDEX IF NOT EXISTS idx_approval_history_pubkey ON approval_history (public_key_id);

-- 13. QUARANTINE CASES (SLA TRACKING, NON-MUTATING ESCALATIONS, HUMAN RESOLUTION)
CREATE TABLE IF NOT EXISTS quarantine_cases (
    case_id                         TEXT PRIMARY KEY,              -- UUIDv4 format
    candidate_id                    TEXT NOT NULL,                 -- FK to candidate_submissions
    quarantine_reason               TEXT NOT NULL,                 -- Reason code
    quarantine_category             TEXT NOT NULL,                 -- SAFETY, LANGUAGE, LEGAL, QUALITY
    diagnostic_evidence_json        TEXT NOT NULL,                 -- Diagnostic payload, tokens, scores
    pipeline_version                TEXT NOT NULL,                 -- Version that flagged candidate
    quarantined_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    review_due_at                   TEXT NOT NULL,                 -- SLA monitoring target (quarantined_at + 30 days)
    last_reminder_at                TEXT,                          -- Timestamp of last reminder sent
    escalated_at                    TEXT,                          -- Timestamp of 30-day escalation
    escalation_level                TEXT NOT NULL DEFAULT 'STANDARD', -- STANDARD, ESCALATED_30_DAYS, CRITICAL_60_DAYS
    assigned_reviewer_id            TEXT,                          -- Reviewer assigned to inspect case
    assigned_role                   TEXT NOT NULL,                 -- Required reviewer role to resolve
    resolution_decision_id          TEXT,                          -- FK to approval_history (NULL while unresolved)
    resolution_evidence_reference   TEXT,                          -- External evidence or notes reference
    resolved_at                     TEXT,                          -- Timestamp of explicit human resolution

    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT,
    FOREIGN KEY (assigned_reviewer_id) REFERENCES reviewer_accounts (reviewer_id) ON DELETE RESTRICT,
    FOREIGN KEY (assigned_role) REFERENCES reviewer_roles (role_id) ON DELETE RESTRICT,
    FOREIGN KEY (resolution_decision_id) REFERENCES approval_history (decision_id) ON DELETE RESTRICT,

    CONSTRAINT chk_quarantine_reason CHECK (
        quarantine_reason IN (
            'LANGUAGE_FILTER_AMBIGUOUS',
            'SEMANTIC_SAFETY_CONFLICT',
            'NEAR_DEDUP_INVERSION',
            'SOURCE_LICENSING_UNCERTAINTY',
            'MALFORMED_STRUCTURE',
            'MANUAL_HUMAN_QUARANTINE'
        )
    ),
    CONSTRAINT chk_quarantine_category CHECK (
        quarantine_category IN ('SAFETY', 'LANGUAGE', 'LEGAL', 'QUALITY')
    ),
    CONSTRAINT chk_escalation_level CHECK (
        escalation_level IN ('STANDARD', 'ESCALATED_30_DAYS', 'CRITICAL_60_DAYS')
    ),
    CONSTRAINT chk_resolution_consistency CHECK (
        (resolution_decision_id IS NULL AND resolved_at IS NULL) OR
        (resolution_decision_id IS NOT NULL AND resolved_at IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_quarantine_candidate ON quarantine_cases (candidate_id);
CREATE INDEX IF NOT EXISTS idx_quarantine_open_cases ON quarantine_cases (quarantine_category, escalation_level)
WHERE resolution_decision_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_quarantine_sla_monitoring ON quarantine_cases (review_due_at)
WHERE resolution_decision_id IS NULL;

-- 14. RETENTION DECISIONS (LEGAL/GOVERNANCE RECORD RETENTION)
CREATE TABLE IF NOT EXISTS retention_decisions (
    decision_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id                TEXT NOT NULL,
    decision_type               TEXT NOT NULL,                 -- RETAIN_AUDIT_EVIDENCE, RESTRICT_ACCESS_DISPUTE, REDACT_RAW_TEXT_MANDATE, EXPUNGE_LEGAL_ORDER
    legal_basis                 TEXT NOT NULL,                 -- Terms of service, Copyright notice, Privacy directive
    governance_notes            TEXT NOT NULL,
    authorized_by               TEXT NOT NULL,                 -- Reviewer ID or Legal Counsel ID
    enacted_at                  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    review_deadline             TEXT,                          -- Scheduled revisit date

    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT,
    CONSTRAINT chk_retention_type CHECK (
        decision_type IN (
            'RETAIN_AUDIT_EVIDENCE',
            'RESTRICT_ACCESS_DISPUTE',
            'REDACT_RAW_TEXT_MANDATE',
            'EXPUNGE_LEGAL_ORDER'
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_retention_candidate ON retention_decisions (candidate_id);

-- 15. EXPORT BATCHES
CREATE TABLE IF NOT EXISTS export_batches (
    batch_id            TEXT PRIMARY KEY,              -- UUIDv4 format
    corpus_version      TEXT NOT NULL,                 -- e.g. "v0.1.0"
    target_split        TEXT NOT NULL,                 -- train, dev, test
    record_count        INTEGER NOT NULL DEFAULT 0,
    export_status       TEXT NOT NULL DEFAULT 'PREPARING', -- PREPARING, COMMITTED, FAILED, REVOKED
    manifest_sha256     TEXT,                          -- Checksum of exported manifest
    output_path         TEXT,                          -- Relative artifact destination
    created_at          TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    committed_at        TEXT,

    CONSTRAINT chk_target_split CHECK (target_split IN ('train', 'dev', 'test')),
    CONSTRAINT chk_batch_status CHECK (
        export_status IN ('PREPARING', 'COMMITTED', 'FAILED', 'REVOKED')
    )
);

-- 16. EXPORT BATCH ITEMS
CREATE TABLE IF NOT EXISTS export_batch_items (
    item_id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id                    TEXT NOT NULL,
    candidate_id                TEXT NOT NULL,
    normalized_content_hash     TEXT NOT NULL,
    exported_at                 TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    FOREIGN KEY (batch_id) REFERENCES export_batches (batch_id) ON DELETE RESTRICT,
    FOREIGN KEY (candidate_id) REFERENCES candidate_submissions (candidate_id) ON DELETE RESTRICT
);

-- Release-scoped idempotency constraint: same candidate cannot be exported twice into same corpus version & split
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_release_export
ON export_batch_items (batch_id, candidate_id);

-- ============================================================================
-- DATABASE TRIGGERS
-- ============================================================================

-- Trigger 1: Immutable approval_history records (prevent UPDATE)
CREATE TRIGGER IF NOT EXISTS trig_abort_approval_history_update
BEFORE UPDATE ON approval_history
BEGIN
    SELECT RAISE(ABORT, 'SECURITY VIOLATION: approval_history records are immutable and cannot be updated.');
END;

-- Trigger 2: Permanent approval_history records (prevent DELETE)
CREATE TRIGGER IF NOT EXISTS trig_abort_approval_history_delete
BEFORE DELETE ON approval_history
BEGIN
    SELECT RAISE(ABORT, 'SECURITY VIOLATION: approval_history records are permanent and cannot be deleted.');
END;

-- Trigger 3: Prevent mutation of public key material once registered
CREATE TRIGGER IF NOT EXISTS trig_abort_public_key_mutation
BEFORE UPDATE OF public_key_hex, algorithm, is_test_key ON reviewer_public_keys
BEGIN
    SELECT RAISE(ABORT, 'SECURITY VIOLATION: Public key material is cryptographically immutable once registered.');
END;

-- Trigger 4: Prevent mutation of processing decisions (append-only)
CREATE TRIGGER IF NOT EXISTS trig_abort_decision_update
BEFORE UPDATE ON processing_decisions
BEGIN
    SELECT RAISE(ABORT, 'SECURITY VIOLATION: processing_decisions records are append-only.');
END;

-- Trigger 5: Enforce that candidate_submissions APPROVED status requires valid approval_history row
CREATE TRIGGER IF NOT EXISTS trig_enforce_signed_approval_mutation
BEFORE UPDATE OF processing_status ON candidate_submissions
WHEN NEW.processing_status = 'APPROVED'
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM approval_history ah
            JOIN reviewer_accounts ra ON ah.reviewer_id = ra.reviewer_id
            JOIN reviewer_public_keys rpk ON ah.public_key_id = rpk.public_key_id
            WHERE ah.candidate_id = NEW.candidate_id
              AND ah.new_status = 'APPROVED'
              AND ah.verification_status = 'VERIFIED_VALID'
              AND ra.account_status = 'ACTIVE'
              AND rpk.is_test_key = 0
              AND rpk.key_status IN ('ACTIVE', 'ROTATED_RETIRED')
        )
        THEN RAISE(ABORT, 'SECURITY VIOLATION: Cannot mark candidate APPROVED without an authenticated, verified human Ed25519 approval event.')
    END;
END;

-- Trigger 6: Prevent candidate from exiting QUARANTINED without explicit human resolution record
CREATE TRIGGER IF NOT EXISTS trig_abort_unauthorized_quarantine_exit
BEFORE UPDATE OF processing_status ON candidate_submissions
WHEN OLD.processing_status = 'QUARANTINED' AND NEW.processing_status != 'QUARANTINED'
BEGIN
    SELECT CASE
        WHEN NOT EXISTS (
            SELECT 1 FROM quarantine_cases qc
            JOIN approval_history ah ON qc.resolution_decision_id = ah.decision_id
            JOIN reviewer_accounts ra ON ah.reviewer_id = ra.reviewer_id
            WHERE qc.candidate_id = NEW.candidate_id
              AND qc.resolution_decision_id IS NOT NULL
              AND ra.account_status = 'ACTIVE'
              AND ah.verification_status = 'VERIFIED_VALID'
        )
        THEN RAISE(ABORT, 'SECURITY VIOLATION: Candidate cannot exit QUARANTINED without an authenticated human cryptographic resolution record.')
    END;
END;

-- Trigger 7: Prevent escalation or reminder updates on non-quarantined candidates
CREATE TRIGGER IF NOT EXISTS trig_prevent_escalation_status_tampering
BEFORE UPDATE OF escalation_level, escalated_at, last_reminder_at ON quarantine_cases
BEGIN
    SELECT CASE
        WHEN EXISTS (
            SELECT 1 FROM candidate_submissions cs
            WHERE cs.candidate_id = NEW.candidate_id
              AND cs.processing_status != 'QUARANTINED'
        )
        THEN RAISE(ABORT, 'INTEGRITY VIOLATION: Escalation or reminder updates cannot be applied to non-quarantined candidates.')
    END;
END;

-- ============================================================================
-- PRODUCTION EXPORT ELIGIBILITY VIEW (18-POINT FAIL-CLOSED PREDICATE)
-- ============================================================================
DROP VIEW IF EXISTS v_export_eligible_candidates;
CREATE VIEW v_export_eligible_candidates AS
SELECT
    c.candidate_id,
    c.source_id,
    c.source_document_id,
    c.original_text,
    c.normalized_text,
    c.raw_content_hash,
    c.normalized_content_hash,
    c.raw_char_count,
    c.normalized_char_count,
    c.approx_word_count,
    s.name AS source_name,
    s.attribution AS source_attribution,
    ah.decision_id AS approval_decision_id,
    ah.reviewer_id AS approved_by_reviewer_id,
    ra.full_name AS reviewer_full_name,
    ah.signature_ed25519 AS approval_signature,
    ah.canonical_payload_sha256 AS payload_hash
FROM candidate_submissions c
JOIN candidate_sources s ON c.source_id = s.source_id
JOIN approval_history ah ON c.candidate_id = ah.candidate_id
JOIN reviewer_accounts ra ON ah.reviewer_id = ra.reviewer_id
JOIN reviewer_public_keys k ON ah.public_key_id = k.public_key_id
WHERE c.processing_status = 'APPROVED'                           -- 1. Status is APPROVED
  AND c.processing_status != 'QUARANTINED'                       -- 2. Explicitly NOT QUARANTINED
  AND c.is_canonical = 1                                         -- 3. Master deduplicated candidate
  AND s.licensing_status = 'VERIFIED PERMITTED'                  -- 4. Source licensing verified
  AND s.training_permitted_status = 'EXPLICITLY_PERMITTED'       -- 5. Training explicitly permitted
  AND s.artifact_sha256 != 'NOT_VERIFIED'                        -- 6. Physical source hash verified
  AND (s.approval_expiration_date IS NULL                        -- 7. Source approval non-expired
       OR s.approval_expiration_date >= strftime('%Y-%m-%d', 'now'))
  AND ah.new_status = 'APPROVED'                                 -- 8. Audit entry approves candidate
  AND ah.verification_status = 'VERIFIED_VALID'                  -- 9. Signature verification succeeded
  AND ra.account_status = 'ACTIVE'                               -- 10. Reviewer account is active
  AND k.is_test_key = 0                                          -- 11. NOT signed with test key
  AND k.key_status IN ('ACTIVE', 'ROTATED_RETIRED')              -- 12. Key active or legitimately rotated
  AND ah.created_at >= k.activated_at                            -- 13. Signed after key activation
  AND (k.valid_until IS NULL OR ah.created_at <= k.valid_until)   -- 14. Signed before key retirement
  AND (k.revoked_at IS NULL OR ah.created_at < k.revoked_at)     -- 15. Signed before any emergency revocation
  AND NOT EXISTS (                                               -- 16. ZERO UNRESOLVED QUARANTINE CASES
      SELECT 1 FROM quarantine_cases qc
      WHERE qc.candidate_id = c.candidate_id
        AND qc.resolution_decision_id IS NULL
  )
  AND NOT EXISTS (                                               -- 17. Zero safety-merge conflicts
      SELECT 1 FROM duplicate_relationships d
      WHERE (d.candidate_id = c.candidate_id OR d.related_candidate_id = c.candidate_id)
        AND d.is_safe_to_merge = 0
  )
  AND NOT EXISTS (                                               -- 18. Zero active legal redaction/expungement
      SELECT 1 FROM retention_decisions rd
      WHERE rd.candidate_id = c.candidate_id
        AND rd.decision_type IN ('RESTRICT_ACCESS_DISPUTE', 'REDACT_RAW_TEXT_MANDATE', 'EXPUNGE_LEGAL_ORDER')
  );
"""

