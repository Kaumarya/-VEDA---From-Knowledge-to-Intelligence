"""
VEDA Candidate Database Subsystem — Reviewer & Cryptographic Key Management
Phase 4.14.2
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from foundation.candidates.connection import CandidateDatabaseConnection
from foundation.candidates.models import (
    ReviewerAccountRecord,
    ReviewerRoleRecord,
    ReviewerPublicKeyRecord,
    AuthenticationEventRecord,
)
from foundation.candidates.exceptions import (
    ReviewerError,
    ReviewerNotFoundError,
    ReviewerInactiveError,
    ReviewerUnauthorizedError,
    RolePermissionError,
    KeyNotFoundError,
    KeyRevokedError,
    KeyExpiredError,
)


class ReviewerService:
    """
    Manages human reviewer accounts, RBAC roles, public key lifecycles, and auth events.
    Enforces that private keys are NEVER stored in SQLite.
    """

    def __init__(self, connection: CandidateDatabaseConnection):
        self.conn = connection

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

    def activate_public_key(self, public_key_id: str, actor_id: str, reason: str = "Identity verified") -> None:
        """Activates a public key for production or test signing."""
        key = self.get_public_key(public_key_id)
        if not key:
            raise KeyNotFoundError(f"Public key '{public_key_id}' not found.")
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

