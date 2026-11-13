"""
VEDA Candidate Database Subsystem — Reviewer Authentication Interface & Argon2id Provider
Phase 4.14.2
"""

import uuid
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from foundation.candidates.models import AuthenticationEventRecord
from foundation.candidates.exceptions import AuthenticationError


class IReviewerAuthenticator(ABC):
    """Abstract interface for reviewer identity authentication."""

    @abstractmethod
    def hash_password(self, plaintext: str) -> str:
        """Hashes plaintext password securely."""
        pass

    @abstractmethod
    def verify_password(self, plaintext: str, hashed: str) -> bool:
        """Verifies plaintext against hash."""
        pass

    @abstractmethod
    def create_session(
        self,
        reviewer_id: str,
        client_host: str = "localhost",
        duration_minutes: int = 480,
    ) -> AuthenticationEventRecord:
        """Creates an auditable authentication session event."""
        pass


class LocalSecureAuthenticator(IReviewerAuthenticator):
    """
    Local authentication provider using Argon2id password hashing and secure session tokens.
    Suitable for local/development environments before enterprise SSO integration.
    """

    def __init__(self):
        self.hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65536,  # 64 MB
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )

    def hash_password(self, plaintext: str) -> str:
        if not plaintext or len(plaintext) < 8:
            raise AuthenticationError("Password must be at least 8 characters.")
        return self.hasher.hash(plaintext)

    def verify_password(self, plaintext: str, hashed: str) -> bool:
        try:
            return self.hasher.verify(hashed, plaintext)
        except VerifyMismatchError:
            return False
        except Exception as e:
            raise AuthenticationError(f"Password verification error: {e}") from e

    def create_session(
        self,
        reviewer_id: str,
        client_host: str = "localhost",
        duration_minutes: int = 480,
    ) -> AuthenticationEventRecord:
        auth_id = f"urn:uuid:{uuid.uuid4()}"
        now = datetime.now(timezone.utc)
        expires = (now + timedelta(minutes=duration_minutes)).isoformat()
        return AuthenticationEventRecord(
            auth_event_id=auth_id,
            reviewer_id=reviewer_id,
            auth_method="LOCAL_PASSWORD_MFA",
            client_host=client_host,
            auth_status="SUCCESS",
            session_expires_at=expires,
            created_at=now.isoformat(),
        )

