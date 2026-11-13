"""
Tests for Session Validation, Production Key Provider, Dual Approval Source Governance, and Proof-of-Possession
Phase 4.14.2.1.2 — Issue 2, Issue 3, Issue 4, Issue 5
"""

import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import replace
import pytest

from foundation.candidates.config import CandidateDatabaseConfig
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.migrations import MigrationManager
from foundation.candidates.repository import CandidateRepository
from foundation.candidates.reviewers import ReviewerService
from foundation.candidates.approvals import ApprovalService
from foundation.candidates.quarantine import QuarantineManager
from foundation.candidates.signatures import Ed25519SignatureService
from foundation.candidates.authentication import LocalSecureAuthenticator
from foundation.candidates.key_custody import WindowsDPAPIKeyProvider, InMemoryEphemeralKeyProvider
from foundation.candidates.models import CandidateSourceRecord, AuthenticationEventRecord
from foundation.candidates.exceptions import (
    AuthenticationError,
    SessionExpiredError,
    ReviewerInactiveError,
    ReviewerUnauthorizedError,
    NonProductionProviderError,
    InvalidDualApprovalError,
    ProofOfPossessionError,
    ValidationError,
)
from foundation.corpus.sources import SourceRegistry, CorpusSource, LicensingStatus


@pytest.fixture
def gov_env(tmp_path: Path):
    """Sets up an isolated test database environment for governance testing."""
    config = CandidateDatabaseConfig.for_testing(tmp_path)
    with CandidateDatabaseConnection(config) as db:
        manager = MigrationManager(db)
        manager.apply_all()

        repo = CandidateRepository(db)
        reviewers = ReviewerService(db)
        approvals = ApprovalService(db, repo, reviewers)
        quarantine = QuarantineManager(db, repo, reviewers)
        authenticator = LocalSecureAuthenticator()

        # Seed valid permitted source
        source_id = "src_gov_01"
        repo.upsert_source(
            CandidateSourceRecord(
                source_id=source_id,
                name="Governance Test Source",
                version="1.0",
                licensing_status="VERIFIED PERMITTED",
                license_name="CC0-1.0",
                training_permitted_status="EXPLICITLY_PERMITTED",
                commercial_permitted=True,
                artifact_sha256="1" * 64,
                registry_entry_sha256="2" * 64,
                approval_expiration_date="2099-12-31",
            )
        )

        # Create reviewers
        alice = reviewers.create_reviewer("alice_curator", "Alice Curator", "alice@veda.internal")
        reviewers.assign_role(alice.reviewer_id, "DOMAIN_CURATOR", assigned_by="admin")

        bob = reviewers.create_reviewer("bob_officer", "Bob Officer", "bob@veda.internal")
        reviewers.assign_role(bob.reviewer_id, "SAFETY_COMPLIANCE_OFFICER", assigned_by="admin")

        # Create valid sessions
        alice_session = authenticator.create_session(alice.reviewer_id)
        reviewers.record_authentication_event(alice_session)

        bob_session = authenticator.create_session(bob.reviewer_id)
        reviewers.record_authentication_event(bob_session)

        # Register keys
        a_pem, a_pub = Ed25519SignatureService.generate_key_pair()
        a_key = reviewers.register_public_key(alice.reviewer_id, a_pub, is_test_key=False)
        reviewers.activate_public_key(a_key.public_key_id, actor_id="admin")

        b_pem, b_pub = Ed25519SignatureService.generate_key_pair()
        b_key = reviewers.register_public_key(bob.reviewer_id, b_pub, is_test_key=False)
        reviewers.activate_public_key(b_key.public_key_id, actor_id="admin")

        yield {
            "db": db,
            "repo": repo,
            "reviewers": reviewers,
            "approvals": approvals,
            "quarantine": quarantine,
            "authenticator": authenticator,
            "source_id": source_id,
            "alice": alice,
            "bob": bob,
            "alice_session": alice_session,
            "bob_session": bob_session,
            "a_pem": a_pem,
            "a_pub": a_pub,
            "a_key": a_key,
            "b_pem": b_pem,
            "b_pub": b_pub,
            "b_key": b_key,
            "tmp_path": tmp_path,
        }


# =========================================================================
# PART 4 TESTS: AUTHENTICATION SESSION VALIDATION
# =========================================================================

def test_expired_session_rejected_at_approval(gov_env):
    """An expired session token must fail closed with SessionExpiredError."""
    env = gov_env
    repo = env["repo"]
    approvals = env["approvals"]
    reviewers = env["reviewers"]

    cand = repo.submit_candidate("Prose for session testing.", env["source_id"], "doc_s1")
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "APPROVAL_PENDING")

    # Record an expired session
    past_iso = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    expired_event = AuthenticationEventRecord(
        auth_event_id=f"urn:uuid:{uuid.uuid4()}",
        reviewer_id=env["alice"].reviewer_id,
        auth_method="LOCAL_PASSWORD_MFA",
        client_host="127.0.0.1",
        auth_status="SUCCESS",
        session_expires_at=past_iso,
    )
    reviewers.record_authentication_event(expired_event)

    with pytest.raises(SessionExpiredError):
        approvals.approve_candidate(
            candidate_id=cand.candidate_id,
            reviewer_id=env["alice"].reviewer_id,
            reviewer_role="DOMAIN_CURATOR",
            public_key_id=env["a_key"].public_key_id,
            auth_event_id=expired_event.auth_event_id,
            decision_reason="Testing expired session.",
            private_key_pem=env["a_pem"],
        )


def test_failed_auth_event_rejected_at_approval(gov_env):
    """A failed authentication event (auth_status=FAILURE) must be rejected."""
    env = gov_env
    repo = env["repo"]
    approvals = env["approvals"]
    reviewers = env["reviewers"]

    cand = repo.submit_candidate("Prose for failed auth testing.", env["source_id"], "doc_s2")
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "APPROVAL_PENDING")

    future_iso = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    failed_event = AuthenticationEventRecord(
        auth_event_id=f"urn:uuid:{uuid.uuid4()}",
        reviewer_id=env["alice"].reviewer_id,
        auth_method="LOCAL_PASSWORD_MFA",
        client_host="127.0.0.1",
        auth_status="FAILURE",
        session_expires_at=future_iso,
    )
    reviewers.record_authentication_event(failed_event)

    with pytest.raises(AuthenticationError, match="status is 'FAILURE'"):
        approvals.approve_candidate(
            candidate_id=cand.candidate_id,
            reviewer_id=env["alice"].reviewer_id,
            reviewer_role="DOMAIN_CURATOR",
            public_key_id=env["a_key"].public_key_id,
            auth_event_id=failed_event.auth_event_id,
            decision_reason="Testing failed auth event.",
            private_key_pem=env["a_pem"],
        )


def test_cross_user_session_rejected_at_approval(gov_env):
    """Passing Bob's session to approve Alice's candidate must be rejected."""
    env = gov_env
    repo = env["repo"]
    approvals = env["approvals"]

    cand = repo.submit_candidate("Prose for cross user testing.", env["source_id"], "doc_s3")
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "APPROVAL_PENDING")

    with pytest.raises(AuthenticationError, match="Cross-user session violation"):
        approvals.approve_candidate(
            candidate_id=cand.candidate_id,
            reviewer_id=env["alice"].reviewer_id,
            reviewer_role="DOMAIN_CURATOR",
            public_key_id=env["a_key"].public_key_id,
            auth_event_id=env["bob_session"].auth_event_id,  # Bob's session used for Alice!
            decision_reason="Testing cross-user session.",
            private_key_pem=env["a_pem"],
        )


# =========================================================================
# PART 5 TESTS: PRODUCTION KEY-PROVIDER ENFORCEMENT
# =========================================================================

def test_in_memory_provider_rejected_when_production_enforced(gov_env):
    """InMemoryEphemeralKeyProvider must be rejected when production provider is enforced."""
    env = gov_env
    repo = env["repo"]
    approvals = env["approvals"]

    cand = repo.submit_candidate("Prose for provider testing.", env["source_id"], "doc_p1")
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "APPROVAL_PENDING")

    ephemeral = InMemoryEphemeralKeyProvider()
    e_kid, e_pub = ephemeral.generate_and_store_key(env["alice"].reviewer_id, is_test_key=False)

    with pytest.raises(NonProductionProviderError, match="is non-production"):
        approvals.approve_candidate(
            candidate_id=cand.candidate_id,
            reviewer_id=env["alice"].reviewer_id,
            reviewer_role="DOMAIN_CURATOR",
            public_key_id=env["a_key"].public_key_id,
            auth_event_id=env["alice_session"].auth_event_id,
            decision_reason="Testing ephemeral provider in prod.",
            key_provider=ephemeral,
            require_production_provider=True,
        )


def test_test_key_rejected_when_production_enforced(gov_env):
    """A key flagged as is_test_key=True must be rejected when production provider is enforced."""
    env = gov_env
    repo = env["repo"]
    approvals = env["approvals"]
    reviewers = env["reviewers"]

    cand = repo.submit_candidate("Prose for test key testing.", env["source_id"], "doc_p2")
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "APPROVAL_PENDING")

    # Register explicit test key
    _, t_pub = Ed25519SignatureService.generate_key_pair()
    test_key = reviewers.register_public_key(env["alice"].reviewer_id, t_pub, is_test_key=True)
    reviewers.activate_public_key(test_key.public_key_id, actor_id="admin")

    class MockProdProvider(WindowsDPAPIKeyProvider):
        def __init__(self):
            pass
        @property
        def is_production(self) -> bool:
            return True
        def has_private_key(self, reviewer_id: str, public_key_id: str) -> bool:
            return True
        def sign_payload(self, reviewer_id: str, public_key_id: str, payload_bytes: bytes) -> str:
            return "0" * 128

    with pytest.raises(NonProductionProviderError, match="is flagged as a test key"):
        approvals.approve_candidate(
            candidate_id=cand.candidate_id,
            reviewer_id=env["alice"].reviewer_id,
            reviewer_role="DOMAIN_CURATOR",
            public_key_id=test_key.public_key_id,
            auth_event_id=env["alice_session"].auth_event_id,
            decision_reason="Testing test key in prod.",
            key_provider=MockProdProvider(),
            require_production_provider=True,
        )


# =========================================================================
# PART 6 TESTS: SOURCE GOVERNANCE BETWEEN DUAL-APPROVAL LEGS
# =========================================================================

def test_source_revoked_between_dual_approval_legs_rejected(gov_env):
    """
    If source licensing is revoked between Leg 1 and Leg 2,
    complete_quarantine_dual_approval must reject and keep candidate QUARANTINED.
    """
    env = gov_env
    repo = env["repo"]
    quarantine = env["quarantine"]

    cand = repo.submit_candidate("Suspicious prose requiring quarantine.", env["source_id"], "doc_q1")
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "QUARANTINED")

    case = repo.create_quarantine_case(
        candidate_id=cand.candidate_id,
        reason="SEMANTIC_SAFETY_CONFLICT",
        category="SAFETY",
        assigned_role="ROLE_SAFETY_OFFICER",
    )

    # Leg 1 approval by Alice
    quarantine.initiate_quarantine_dual_approval(
        case_id=case.case_id,
        reviewer_id=env["alice"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=env["a_key"].public_key_id,
        auth_event_id=env["alice_session"].auth_event_id,
        decision_reason="Leg 1 approval verified.",
        private_key_pem=env["a_pem"],
    )

    # Now source licensing is revoked in candidate database cache!
    db = env["db"]
    with db.transaction() as c:
        c.execute(
            "UPDATE candidate_sources SET licensing_status = 'EXCLUDED' WHERE source_id = ?;",
            (env["source_id"],),
        )

    # Leg 2 approval by Bob must fail closed!
    with pytest.raises(InvalidDualApprovalError, match="permission was revoked"):
        quarantine.complete_quarantine_dual_approval(
            case_id=case.case_id,
            reviewer_id=env["bob"].reviewer_id,
            reviewer_role="SAFETY_COMPLIANCE_OFFICER",
            public_key_id=env["b_key"].public_key_id,
            auth_event_id=env["bob_session"].auth_event_id,
            decision_reason="Leg 2 approval attempting commit.",
            private_key_pem=env["b_pem"],
        )

    # Verify candidate remains QUARANTINED
    reloaded_cand = repo.get_candidate(cand.candidate_id)
    assert reloaded_cand.processing_status == "QUARANTINED"


# =========================================================================
# PART 7 TESTS: PUBLIC-KEY PROOF-OF-POSSESSION
# =========================================================================

def test_proof_of_possession_successful_registration(gov_env):
    """Reviewer successfully proves possession of private key corresponding to public key."""
    env = gov_env
    reviewers = env["reviewers"]

    rev = env["alice"]
    priv_pem, pub_hex = Ed25519SignatureService.generate_key_pair()

    # 1. Request challenge
    challenge = reviewers.request_key_registration_challenge(rev.reviewer_id, pub_hex)
    assert challenge.nonce is not None

    # 2. Sign challenge payload
    payload_bytes = f"VEDA_POP:{challenge.challenge_id}:{rev.reviewer_id}:{pub_hex.lower()}:{challenge.nonce}".encode("utf-8")
    sig_hex = Ed25519SignatureService.sign(priv_pem, payload_bytes)

    # 3. Register with proof
    key_rec = reviewers.register_public_key_with_proof(
        reviewer_id=rev.reviewer_id,
        proposed_public_key_hex=pub_hex,
        challenge_id=challenge.challenge_id,
        pop_signature_hex=sig_hex,
    )
    assert key_rec.key_status == "PENDING_ACTIVATION"
    assert key_rec.public_key_hex == pub_hex.lower()


def test_proof_of_possession_wrong_private_key_rejected(gov_env):
    """Signing challenge with an unrelated private key fails PoP verification."""
    env = gov_env
    reviewers = env["reviewers"]

    rev = env["alice"]
    _, pub_hex = Ed25519SignatureService.generate_key_pair()
    wrong_priv, _ = Ed25519SignatureService.generate_key_pair()

    challenge = reviewers.request_key_registration_challenge(rev.reviewer_id, pub_hex)
    payload_bytes = f"VEDA_POP:{challenge.challenge_id}:{rev.reviewer_id}:{pub_hex.lower()}:{challenge.nonce}".encode("utf-8")
    wrong_sig = Ed25519SignatureService.sign(wrong_priv, payload_bytes)

    with pytest.raises(ProofOfPossessionError, match="verification failed"):
        reviewers.register_public_key_with_proof(
            reviewer_id=rev.reviewer_id,
            proposed_public_key_hex=pub_hex,
            challenge_id=challenge.challenge_id,
            pop_signature_hex=wrong_sig,
        )


def test_proof_of_possession_challenge_reuse_rejected(gov_env):
    """Attempting to reuse an already consumed challenge nonce fails."""
    env = gov_env
    reviewers = env["reviewers"]

    rev = env["alice"]
    priv_pem, pub_hex = Ed25519SignatureService.generate_key_pair()

    challenge = reviewers.request_key_registration_challenge(rev.reviewer_id, pub_hex)
    payload_bytes = f"VEDA_POP:{challenge.challenge_id}:{rev.reviewer_id}:{pub_hex.lower()}:{challenge.nonce}".encode("utf-8")
    sig_hex = Ed25519SignatureService.sign(priv_pem, payload_bytes)

    # First registration consumes challenge
    reviewers.register_public_key_with_proof(
        reviewer_id=rev.reviewer_id,
        proposed_public_key_hex=pub_hex,
        challenge_id=challenge.challenge_id,
        pop_signature_hex=sig_hex,
    )

    # Second registration with same challenge must fail
    with pytest.raises(ProofOfPossessionError, match="already been consumed"):
        reviewers.register_public_key_with_proof(
            reviewer_id=rev.reviewer_id,
            proposed_public_key_hex=pub_hex,
            challenge_id=challenge.challenge_id,
            pop_signature_hex=sig_hex,
        )


def test_unauthorized_key_activation_rejected(gov_env):
    """An actor lacking administrative or key management authority cannot activate keys."""
    env = gov_env
    reviewers = env["reviewers"]

    rev = env["alice"]
    priv_pem, pub_hex = Ed25519SignatureService.generate_key_pair()
    key_rec = reviewers.register_public_key(rev.reviewer_id, pub_hex)

    # Bob is only a SAFETY_COMPLIANCE_OFFICER (can_manage_keys=0, can_administer_accounts=0)
    with pytest.raises(ReviewerUnauthorizedError, match="lacks authority to activate"):
        reviewers.activate_public_key(
            public_key_id=key_rec.public_key_id,
            actor_id=env["bob"].reviewer_id,
            actor_auth_event_id=env["bob_session"].auth_event_id,
        )


def test_same_idp_subject_id_dual_approval_rejected(gov_env):
    """
    Two accounts that resolve to the same underlying physical human identity (same idp_subject_id)
    must be rejected by the dual-approval protocol.
    """
    env = gov_env
    repo = env["repo"]
    reviewers = env["reviewers"]
    quarantine = env["quarantine"]

    # Create two accounts with same physical IdP subject ID
    emp_id = "corp_emp_998811"
    rev1 = reviewers.create_reviewer("human_curator", "Human One", "h1@corp.internal", idp_subject_id=emp_id)
    reviewers.assign_role(rev1.reviewer_id, "DOMAIN_CURATOR", assigned_by="admin")
    priv1, pub1 = Ed25519SignatureService.generate_key_pair()
    k1 = reviewers.register_public_key(rev1.reviewer_id, pub1)
    reviewers.activate_public_key(k1.public_key_id, actor_id="admin")
    s1 = env["authenticator"].create_session(rev1.reviewer_id)
    reviewers.record_authentication_event(s1)

    rev2 = reviewers.create_reviewer("human_safety", "Human Two", "h2@corp.internal", idp_subject_id=emp_id)
    reviewers.assign_role(rev2.reviewer_id, "SAFETY_COMPLIANCE_OFFICER", assigned_by="admin")
    priv2, pub2 = Ed25519SignatureService.generate_key_pair()
    k2 = reviewers.register_public_key(rev2.reviewer_id, pub2)
    reviewers.activate_public_key(k2.public_key_id, actor_id="admin")
    s2 = env["authenticator"].create_session(rev2.reviewer_id)
    reviewers.record_authentication_event(s2)

    cand = repo.submit_candidate("Prose for identity assurance.", env["source_id"], "doc_idp_1")
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "QUARANTINED")

    case = repo.create_quarantine_case(
        candidate_id=cand.candidate_id,
        reason="SEMANTIC_SAFETY_CONFLICT",
        category="SAFETY",
        assigned_role="ROLE_SAFETY_OFFICER",
    )

    # Leg 1
    quarantine.initiate_quarantine_dual_approval(
        case_id=case.case_id,
        reviewer_id=rev1.reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=k1.public_key_id,
        auth_event_id=s1.auth_event_id,
        decision_reason="Leg 1 valid.",
        private_key_pem=priv1,
    )

    # Leg 2 must reject due to same IdP subject ID
    with pytest.raises(InvalidDualApprovalError, match="Both reviewer accounts map to the same organizational IdP subject identifier"):
        quarantine.complete_quarantine_dual_approval(
            case_id=case.case_id,
            reviewer_id=rev2.reviewer_id,
            reviewer_role="SAFETY_COMPLIANCE_OFFICER",
            public_key_id=k2.public_key_id,
            auth_event_id=s2.auth_event_id,
            decision_reason="Leg 2 attempting collision bypass.",
            private_key_pem=priv2,
        )


def test_production_dual_approval_blocked_without_idp(gov_env):
    """
    When production identity assurance is enforced, reviewers lacking verified
    IdP subject identifiers are blocked and dual approval is rejected as NOT IMPLEMENTED.
    """
    env = gov_env
    repo = env["repo"]
    quarantine = env["quarantine"]

    cand = repo.submit_candidate("Prose for unverified IdP.", env["source_id"], "doc_idp_2")
    repo.update_status(cand.candidate_id, "PROCESSING_PASSED")
    repo.update_status(cand.candidate_id, "QUARANTINED")

    case = repo.create_quarantine_case(
        candidate_id=cand.candidate_id,
        reason="SEMANTIC_SAFETY_CONFLICT",
        category="SAFETY",
        assigned_role="ROLE_SAFETY_OFFICER",
    )

    # Leg 1
    quarantine.initiate_quarantine_dual_approval(
        case_id=case.case_id,
        reviewer_id=env["alice"].reviewer_id,
        reviewer_role="DOMAIN_CURATOR",
        public_key_id=env["a_key"].public_key_id,
        auth_event_id=env["alice_session"].auth_event_id,
        decision_reason="Leg 1 valid.",
        private_key_pem=env["a_pem"],
    )

    # Leg 2 with enforce_identity_assurance=True must fail closed
    with pytest.raises(InvalidDualApprovalError, match="Organizational identity provider assurance is NOT IMPLEMENTED"):
        quarantine.complete_quarantine_dual_approval(
            case_id=case.case_id,
            reviewer_id=env["bob"].reviewer_id,
            reviewer_role="SAFETY_COMPLIANCE_OFFICER",
            public_key_id=env["b_key"].public_key_id,
            auth_event_id=env["bob_session"].auth_event_id,
            decision_reason="Leg 2 prod assurance check.",
            private_key_pem=env["b_pem"],
            enforce_identity_assurance=True,
        )
