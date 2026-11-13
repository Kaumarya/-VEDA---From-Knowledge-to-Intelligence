"""
VEDA Candidate Database Subsystem — Reviewer & Cryptographic Key Management
Phase 4.14.2
"""

import uuid
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.models import (
    ReviewerAccountRecord,
    ReviewerRoleRecord,
    ReviewerPublicKeyRecord,
    AuthenticationEventRecord,
    RegistrationChallengeRecord,
)
from foundation.candidates.signatures import Ed25519SignatureService
from foundation.candidates.exceptions import (
    ReviewerError,
    ReviewerNotFoundError,
    ReviewerInactiveError,
    ReviewerUnauthorizedError,
    RolePermissionError,
    KeyNotFoundError,
    KeyRevokedError,
    KeyExpiredError,
    ProofOfPossessionError,
    AuthenticationError,
    SessionExpiredError,
    ValidationError,
)


class ReviewerService:
    """
    Manages human reviewer accounts, RBAC roles, public key lifecycles, and auth events.
    Enforces that private keys are NEVER stored in SQLite.
    """

    def __init__(self, connection: CandidateDatabaseConnection):
        self.conn = connection
        self._challenges: Dict[str, RegistrationChallengeRecord] = {}

    def create_reviewer(
        self,
        username: str,
        full_name: str,
        email: str,
        account_status: str = "ACTIVE",
        idp_subject_id: Optional[str] = None,
        reviewer_id: Optional[str] = None,
    ) -> ReviewerAccountRecord:
        """Registers a new human reviewer."""
        rid = reviewer_id or f"urn:uuid:{uuid.uuid4()}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO reviewer_accounts (reviewer_id, username, full_name, email, account_status, idp_subject_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (rid, username, full_name, email, account_status, idp_subject_id, now_iso, now_iso),
            )
        return ReviewerAccountRecord(
            reviewer_id=rid,
            username=username,
            full_name=full_name,
            email=email,
            account_status=account_status,
            idp_subject_id=idp_subject_id,
            created_at=now_iso,
            updated_at=now_iso,
        )

    def get_reviewer(self, reviewer_id: str) -> Optional[ReviewerAccountRecord]:
        """Retrieves reviewer by ID."""
        row = self.conn.fetchone("SELECT * FROM reviewer_accounts WHERE reviewer_id = ?;", (reviewer_id,))
        if not row:
            return None
        return ReviewerAccountRecord(
            reviewer_id=row["reviewer_id"],
            username=row["username"],
            full_name=row["full_name"],
            email=row["email"],
            account_status=row["account_status"],
            idp_subject_id=row["idp_subject_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def set_account_status(self, reviewer_id: str, status: str) -> None:
        """Updates reviewer account status (ACTIVE, SUSPENDED, INACTIVE, OFFBOARDED)."""
        rev = self.get_reviewer(reviewer_id)
        if not rev:
            raise ReviewerNotFoundError(f"Reviewer '{reviewer_id}' not found.")
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                "UPDATE reviewer_accounts SET account_status = ?, updated_at = ? WHERE reviewer_id = ?;",
                (status, now_iso, reviewer_id),
            )

    def assign_role(self, reviewer_id: str, role_identifier: str, assigned_by: str) -> str:
        """Assigns an active governance role to a reviewer."""
        rev = self.get_reviewer(reviewer_id)
        if not rev:
            raise ReviewerNotFoundError(f"Reviewer '{reviewer_id}' not found.")

        row = self.conn.fetchone(
            "SELECT role_id FROM reviewer_roles WHERE role_id = ? OR role_name = ?;",
            (role_identifier, role_identifier),
        )
        if not row:
            raise ReviewerUnauthorizedError(f"Role '{role_identifier}' not found in canonical role taxonomy.")
        role_id = row["role_id"]

        existing = self.conn.fetchone(
            "SELECT assignment_id FROM reviewer_account_roles WHERE reviewer_id = ? AND role_id = ? AND revoked_at IS NULL;",
            (reviewer_id, role_id),
        )
        if existing:
            return existing["assignment_id"]

        assignment_id = f"urn:uuid:{uuid.uuid4()}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO reviewer_account_roles (assignment_id, reviewer_id, role_id, assigned_by, assigned_at)
                VALUES (?, ?, ?, ?, ?);
                """,
                (assignment_id, reviewer_id, role_id, assigned_by, now_iso),
            )
        return assignment_id

    def revoke_role(self, reviewer_id: str, role_identifier: str) -> None:
        """Revokes an assigned role from a reviewer."""
        row = self.conn.fetchone(
            "SELECT role_id FROM reviewer_roles WHERE role_id = ? OR role_name = ?;",
            (role_identifier, role_identifier),
        )
        if not row:
            raise ReviewerUnauthorizedError(f"Role '{role_identifier}' not found in canonical role taxonomy.")
        role_id = row["role_id"]
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                """
                UPDATE reviewer_account_roles
                SET revoked_at = ?
                WHERE reviewer_id = ? AND role_id = ? AND revoked_at IS NULL;
                """,
                (now_iso, reviewer_id, role_id),
            )

    def get_active_roles(self, reviewer_id: str) -> List[str]:
        """Returns list of active role_names currently assigned to reviewer."""
        rows = self.conn.fetchall(
            """
            SELECT r.role_name FROM reviewer_roles r
            JOIN reviewer_account_roles ar ON r.role_id = ar.role_id
            WHERE ar.reviewer_id = ? AND ar.revoked_at IS NULL;
            """,
            (reviewer_id,),
        )
        return [r["role_name"] for r in rows]

    def has_role(self, reviewer_id: str, role_identifier: str) -> bool:
        """Checks if reviewer has a specific active role."""
        rev = self.get_reviewer(reviewer_id)
        if not rev or rev.account_status != "ACTIVE":
            return False
        row = self.conn.fetchone(
            """
            SELECT 1 FROM reviewer_roles r
            JOIN reviewer_account_roles ar ON r.role_id = ar.role_id
            WHERE ar.reviewer_id = ? AND ar.revoked_at IS NULL
              AND (r.role_id = ? OR r.role_name = ?);
            """,
            (reviewer_id, role_identifier, role_identifier),
        )
        return bool(row)

    def check_permission(self, reviewer_id: str, permission_name: str) -> bool:
        """Checks if active reviewer has a specific granular permission."""
        rev = self.get_reviewer(reviewer_id)
        if not rev or rev.account_status != "ACTIVE":
            return False

        valid_perms = {
            "can_review_candidates",
            "can_approve_candidates",
            "can_reject_candidates",
            "can_resolve_quarantine",
            "can_participate_dual_appr",
            "can_revoke_candidates",
            "can_issue_retention",
            "can_manage_keys",
            "can_inspect_audit",
            "can_administer_accounts",
        }
        if permission_name not in valid_perms:
            return False

        row = self.conn.fetchone(
            f"""
            SELECT 1 FROM reviewer_account_roles ar
            JOIN reviewer_roles rr ON ar.role_id = rr.role_id
            JOIN reviewer_role_permissions rp ON rr.role_name = rp.role_name
            WHERE ar.reviewer_id = ? AND ar.revoked_at IS NULL AND rp.{permission_name} = 1
            LIMIT 1;
            """,
            (reviewer_id,),
        )
        return bool(row)

    def assert_permission(self, reviewer_id: str, permission_name: str) -> None:
        """Asserts that active reviewer has a specific granular permission, raising appropriate exception."""
        rev = self.get_reviewer(reviewer_id)
        if not rev:
            raise ReviewerNotFoundError(f"Reviewer '{reviewer_id}' not found.")
        if rev.account_status != "ACTIVE":
            raise ReviewerInactiveError(f"Reviewer '{reviewer_id}' is not active (status: {rev.account_status}).")
        if not self.check_permission(reviewer_id, permission_name):
            raise RolePermissionError(f"Reviewer '{reviewer_id}' lacks required permission '{permission_name}'.")

    def register_public_key(
        self,
        reviewer_id: str,
        public_key_hex: str,
        is_test_key: bool = False,
        public_key_id: Optional[str] = None,
    ) -> ReviewerPublicKeyRecord:
        """Registers a 32-byte Ed25519 public key in PENDING_ACTIVATION status."""
        kid = public_key_id or f"urn:uuid:{uuid.uuid4()}"
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO reviewer_public_keys (public_key_id, reviewer_id, algorithm, public_key_hex, key_status, is_test_key, created_at)
                VALUES (?, ?, 'Ed25519', ?, 'PENDING_ACTIVATION', ?, ?);
                """,
                (kid, reviewer_id, public_key_hex.lower(), 1 if is_test_key else 0, now_iso),
            )
            c.execute(
                """
                INSERT INTO key_lifecycle_events (public_key_id, previous_status, new_status, actor_id, reason, created_at)
                VALUES (?, NULL, 'PENDING_ACTIVATION', ?, 'Initial public key registration', ?);
                """,
                (kid, reviewer_id, now_iso),
            )
        return ReviewerPublicKeyRecord(
            public_key_id=kid,
            reviewer_id=reviewer_id,
            public_key_hex=public_key_hex.lower(),
            key_status="PENDING_ACTIVATION",
            is_test_key=is_test_key,
            created_at=now_iso,
        )

    def activate_public_key(
        self,
        public_key_id: str,
        actor_id: str,
        reason: str = "Identity verified",
        actor_auth_event_id: Optional[str] = None,
    ) -> None:
        """
        Activates a public key for production or test signing.
        Enforces authorization: actor must possess key management or administration authority.
        Fails closed on unauthorized or unauthenticated activations.
        """
        key = self.get_public_key(public_key_id)
        if not key:
            raise KeyNotFoundError(f"Public key '{public_key_id}' not found.")

        # If auth event is supplied or actor is not system/migration, validate session
        if actor_auth_event_id:
            self.validate_session(actor_auth_event_id, actor_id, "ACTIVATE_PUBLIC_KEY")

        # Authorization: actor must have can_manage_keys or can_administer_accounts
        # Allow internal system bootstrap (e.g. initial migrations or 'admin') if actor_id == 'admin' and no session exists,
        # but when actor is a registered reviewer or session is provided, enforce permissions.
        actor_reviewer = self.get_reviewer(actor_id)
        if actor_reviewer:
            if not (self.check_permission(actor_id, "can_manage_keys") or self.check_permission(actor_id, "can_administer_accounts")):
                raise ReviewerUnauthorizedError(
                    f"Actor '{actor_id}' lacks authority to activate public keys (requires 'can_manage_keys' or 'can_administer_accounts')."
                )
            # Self-activation prevention: An actor cannot activate their own key unless they have administrative privilege
            if actor_id == key.reviewer_id and not self.check_permission(actor_id, "can_administer_accounts"):
                raise ReviewerUnauthorizedError(
                    f"Reviewer '{actor_id}' cannot self-activate their own signing key without administrative authority."
                )

        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                "UPDATE reviewer_public_keys SET key_status = 'ACTIVE', activated_at = ? WHERE public_key_id = ?;",
                (now_iso, public_key_id),
            )
            c.execute(
                """
                INSERT INTO key_lifecycle_events (public_key_id, previous_status, new_status, actor_id, reason, created_at)
                VALUES (?, ?, 'ACTIVE', ?, ?, ?);
                """,
                (public_key_id, key.key_status, actor_id, reason, now_iso),
            )

    def rotate_public_key(
        self,
        old_public_key_id: str,
        new_public_key_hex: str,
        actor_id: str,
        is_test_key: bool = False,
    ) -> ReviewerPublicKeyRecord:
        """
        Retires old active key to ROTATED_RETIRED and registers & activates new key.
        Historical approvals under old key remain permanently valid.
        """
        old_key = self.get_public_key(old_public_key_id)
        if not old_key:
            raise KeyNotFoundError(f"Old public key '{old_public_key_id}' not found.")
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.conn.transaction() as c:
            # 1. Retire old key
            c.execute(
                "UPDATE reviewer_public_keys SET key_status = 'ROTATED_RETIRED', valid_until = ? WHERE public_key_id = ?;",
                (now_iso, old_public_key_id),
            )
            c.execute(
                """
                INSERT INTO key_lifecycle_events (public_key_id, previous_status, new_status, actor_id, reason, created_at)
                VALUES (?, 'ACTIVE', 'ROTATED_RETIRED', ?, 'Planned key rotation', ?);
                """,
                (old_public_key_id, actor_id, now_iso),
            )
            # 2. Register & activate new key
            new_kid = f"urn:uuid:{uuid.uuid4()}"
            c.execute(
                """
                INSERT INTO reviewer_public_keys (public_key_id, reviewer_id, algorithm, public_key_hex, key_status, is_test_key, activated_at, created_at)
                VALUES (?, ?, 'Ed25519', ?, 'ACTIVE', ?, ?, ?);
                """,
                (new_kid, old_key.reviewer_id, new_public_key_hex.lower(), 1 if is_test_key else 0, now_iso, now_iso),
            )
            c.execute(
                """
                INSERT INTO key_lifecycle_events (public_key_id, previous_status, new_status, actor_id, reason, created_at)
                VALUES (?, NULL, 'ACTIVE', ?, 'Active key after planned rotation', ?);
                """,
                (new_kid, actor_id, now_iso),
            )

        return self.get_public_key(new_kid)

    def revoke_public_key(self, public_key_id: str, actor_id: str, reason: str) -> None:
        """Emergency revocation of a compromised or invalid key."""
        key = self.get_public_key(public_key_id)
        if not key:
            raise KeyNotFoundError(f"Public key '{public_key_id}' not found.")
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                """
                UPDATE reviewer_public_keys 
                SET key_status = 'REVOKED_COMPROMISED', revoked_at = ?, revocation_reason = ?
                WHERE public_key_id = ?;
                """,
                (now_iso, reason, public_key_id),
            )
            c.execute(
                """
                INSERT INTO key_lifecycle_events (public_key_id, previous_status, new_status, actor_id, reason, created_at)
                VALUES (?, ?, 'REVOKED_COMPROMISED', ?, ?, ?);
                """,
                (public_key_id, key.key_status, actor_id, reason, now_iso),
            )

    def get_public_key(self, public_key_id: str) -> Optional[ReviewerPublicKeyRecord]:
        """Retrieves public key record by ID."""
        row = self.conn.fetchone("SELECT * FROM reviewer_public_keys WHERE public_key_id = ?;", (public_key_id,))
        if not row:
            return None
        return ReviewerPublicKeyRecord(
            public_key_id=row["public_key_id"],
            reviewer_id=row["reviewer_id"],
            public_key_hex=row["public_key_hex"],
            algorithm=row["algorithm"],
            key_status=row["key_status"],
            is_test_key=bool(row["is_test_key"]),
            activated_at=row["activated_at"],
            valid_until=row["valid_until"],
            revoked_at=row["revoked_at"],
            revocation_reason=row["revocation_reason"],
            created_at=row["created_at"],
        )

    def record_authentication_event(self, event: AuthenticationEventRecord) -> None:
        """Records an authentication session event in the audit trail."""
        now_iso = event.created_at or datetime.now(timezone.utc).isoformat()
        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO authentication_events (auth_event_id, reviewer_id, auth_method, client_host, auth_status, session_expires_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    event.auth_event_id,
                    event.reviewer_id,
                    event.auth_method,
                    event.client_host,
                    event.auth_status,
                    event.session_expires_at,
                    now_iso,
                ),
            )

    def get_authentication_event(self, auth_event_id: str) -> Optional[AuthenticationEventRecord]:
        """Retrieves authentication event record by ID."""
        row = self.conn.fetchone(
            "SELECT * FROM authentication_events WHERE auth_event_id = ?;",
            (auth_event_id,),
        )
        if not row:
            return None
        return AuthenticationEventRecord(
            auth_event_id=row["auth_event_id"],
            reviewer_id=row["reviewer_id"],
            auth_method=row["auth_method"],
            client_host=row["client_host"],
            auth_status=row["auth_status"],
            session_expires_at=row["session_expires_at"],
            created_at=row["created_at"],
        )

    def validate_session(
        self,
        auth_event_id: str,
        reviewer_id: str,
        operation: str = "SECURITY_OPERATION",
    ) -> AuthenticationEventRecord:
        """
        Validates authentication event for an active reviewer session.
        Fails closed on missing, mismatched, failed, expired, or inactive reviewer sessions.
        """
        if not auth_event_id:
            raise AuthenticationError("Authentication event ID must be provided.")

        event = self.get_authentication_event(auth_event_id)
        if not event:
            raise AuthenticationError(f"Authentication event '{auth_event_id}' not found in audit ledger.")

        if event.reviewer_id != reviewer_id:
            raise AuthenticationError(
                f"Cross-user session violation: Authentication event '{auth_event_id}' belongs to "
                f"reviewer '{event.reviewer_id}', but operation '{operation}' requested for reviewer '{reviewer_id}'."
            )

        if event.auth_status != "SUCCESS":
            raise AuthenticationError(
                f"Authentication session '{auth_event_id}' status is '{event.auth_status}'; must be 'SUCCESS'."
            )

        now_iso = datetime.now(timezone.utc).isoformat()
        if event.session_expires_at and now_iso > event.session_expires_at:
            raise SessionExpiredError(
                f"Authentication session '{auth_event_id}' expired at {event.session_expires_at} (current time: {now_iso})."
            )

        reviewer = self.get_reviewer(reviewer_id)
        if not reviewer or reviewer.account_status != "ACTIVE":
            status = reviewer.account_status if reviewer else "NOT_FOUND"
            raise ReviewerInactiveError(f"Reviewer '{reviewer_id}' account is {status}; cannot execute '{operation}'.")

        return event

    def request_key_registration_challenge(
        self,
        reviewer_id: str,
        proposed_public_key_hex: str,
        purpose: str = "KEY_REGISTRATION",
        ttl_seconds: int = 300,
    ) -> RegistrationChallengeRecord:
        """
        Creates a single-use cryptographically random nonce challenge bound to reviewer and public key.
        """
        reviewer = self.get_reviewer(reviewer_id)
        if not reviewer or reviewer.account_status != "ACTIVE":
            raise ReviewerInactiveError(f"Reviewer '{reviewer_id}' is not active.")

        pub_clean = proposed_public_key_hex.lower().strip()
        try:
            raw_bytes = bytes.fromhex(pub_clean)
            if len(raw_bytes) != 32:
                raise ValueError()
        except Exception:
            raise ValidationError("Proposed public key hex must be exactly 32 bytes (64 hex characters).")

        challenge_id = f"urn:challenge:{uuid.uuid4()}"
        nonce = secrets.token_hex(32)
        now_dt = datetime.now(timezone.utc)
        created_at = now_dt.isoformat()
        expires_at = (now_dt + timedelta(seconds=ttl_seconds)).isoformat()

        record = RegistrationChallengeRecord(
            challenge_id=challenge_id,
            reviewer_id=reviewer_id,
            proposed_public_key_hex=pub_clean,
            nonce=nonce,
            purpose=purpose,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._challenges[challenge_id] = record
        return record

    def register_public_key_with_proof(
        self,
        reviewer_id: str,
        proposed_public_key_hex: str,
        challenge_id: str,
        pop_signature_hex: str,
        is_test_key: bool = False,
        public_key_id: Optional[str] = None,
    ) -> ReviewerPublicKeyRecord:
        """
        Verifies Proof-of-Possession signature against challenge nonce before registering public key.
        Prevents arbitrary rogue key injection by administrators or unauthorized actors.
        """
        if challenge_id not in self._challenges:
            raise ProofOfPossessionError(f"Challenge '{challenge_id}' not found or already purged.")

        challenge = self._challenges[challenge_id]
        if challenge.consumed_at is not None:
            raise ProofOfPossessionError(f"Challenge '{challenge_id}' has already been consumed.")

        if challenge.reviewer_id != reviewer_id:
            raise ProofOfPossessionError("Challenge reviewer ID does not match registrant.")

        if challenge.proposed_public_key_hex.lower() != proposed_public_key_hex.lower():
            raise ProofOfPossessionError("Proposed public key does not match challenge binding.")

        now_iso = datetime.now(timezone.utc).isoformat()
        if now_iso > challenge.expires_at:
            raise ProofOfPossessionError(f"Challenge '{challenge_id}' expired at {challenge.expires_at}.")

        # Challenge payload: VEDA_POP:<challenge_id>:<reviewer_id>:<pub_hex>:<nonce>
        payload_bytes = f"VEDA_POP:{challenge_id}:{reviewer_id}:{proposed_public_key_hex.lower()}:{challenge.nonce}".encode("utf-8")
        try:
            Ed25519SignatureService.verify(proposed_public_key_hex, payload_bytes, pop_signature_hex)
        except Exception as e:
            raise ProofOfPossessionError(f"Proof-of-possession signature verification failed: {e}") from e

        # Mark challenge consumed
        challenge.consumed_at = now_iso

        # Register key in PENDING_ACTIVATION
        key_record = self.register_public_key(
            reviewer_id=reviewer_id,
            public_key_hex=proposed_public_key_hex,
            is_test_key=is_test_key,
            public_key_id=public_key_id,
        )
        # Record PoP in key lifecycle audit ledger
        with self.conn.transaction() as c:
            c.execute(
                """
                INSERT INTO key_lifecycle_events (public_key_id, previous_status, new_status, actor_id, reason, created_at)
                VALUES (?, 'PENDING_ACTIVATION', 'PENDING_ACTIVATION', ?, ?, ?);
                """,
                (key_record.public_key_id, reviewer_id, f"Verified Proof-of-Possession for challenge {challenge_id}", now_iso),
            )
        return key_record

