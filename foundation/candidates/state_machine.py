"""
VEDA Candidate Database Subsystem — 12-State Candidate Lifecycle State Machine
Phase 4.14.2
"""

from typing import Set, Dict, Optional
from foundation.candidates.exceptions import InvalidStateTransitionError, QuarantineTimeoutMutationError


VALID_LIFECYCLE_STATES: Set[str] = {
    "RECEIVED",
    "PENDING",
    "PROCESSING",
    "PROCESSING_PASSED",
    "APPROVAL_PENDING",
    "APPROVED",
    "REJECTED",
    "QUARANTINED",
    "PROCESSING_FAILED",
    "EXPORT_PENDING",
    "EXPORTED",
    "REVOKED",
}


# Permitted state transition map
PERMITTED_TRANSITIONS: Dict[str, Set[str]] = {
    "RECEIVED": {"PENDING", "PROCESSING", "PROCESSING_PASSED", "QUARANTINED", "PROCESSING_FAILED"},
    "PENDING": {"PROCESSING", "QUARANTINED", "PROCESSING_FAILED"},
    "PROCESSING": {"PROCESSING_PASSED", "QUARANTINED", "REJECTED", "PROCESSING_FAILED"},
    "PROCESSING_PASSED": {"APPROVAL_PENDING", "PROCESSING", "QUARANTINED"},
    "APPROVAL_PENDING": {"APPROVED", "REJECTED", "QUARANTINED", "PROCESSING"},
    "QUARANTINED": {"APPROVAL_PENDING", "REJECTED", "APPROVED"},
    "APPROVED": {"EXPORT_PENDING", "REVOKED"},
    "EXPORT_PENDING": {"EXPORTED", "REVOKED", "APPROVED"},
    "EXPORTED": {"REVOKED"},
    "REJECTED": {"PROCESSING", "PENDING"},
    "PROCESSING_FAILED": {"PENDING", "PROCESSING"},
    "REVOKED": set(),  # Terminal status
}


class CandidateLifecycleStateMachine:
    """Enforces transition rules, human-only boundaries, and quarantine immutability."""

    @classmethod
    def validate_transition(
        cls,
        from_state: str,
        to_state: str,
        actor_role: Optional[str] = None,
        is_human: bool = False,
        is_timeout_action: bool = False,
    ) -> None:
        """
        Validates state transition invariants.
        Raises InvalidStateTransitionError or QuarantineTimeoutMutationError if violated.
        """
        if from_state not in VALID_LIFECYCLE_STATES:
            raise InvalidStateTransitionError(from_state, to_state, f"Unknown source state: {from_state}")
        if to_state not in VALID_LIFECYCLE_STATES:
            raise InvalidStateTransitionError(from_state, to_state, f"Unknown destination state: {to_state}")

        # Invariant 1: Quarantine timeout must NEVER mutate lifecycle state
        if from_state == "QUARANTINED" and is_timeout_action:
            raise QuarantineTimeoutMutationError(
                "GOVERNANCE VIOLATION: Quarantine timeouts must never automatically mutate candidate state."
            )

        # Invariant 2: Exiting QUARANTINED requires an authenticated human actor
        if from_state == "QUARANTINED" and not is_human:
            raise InvalidStateTransitionError(
                from_state, to_state, "Exiting QUARANTINED requires an authenticated human reviewer."
            )

        # Invariant 3: Entering APPROVED requires an authenticated human actor
        if to_state == "APPROVED" and not is_human:
            raise InvalidStateTransitionError(
                from_state, to_state, "Transitioning to APPROVED requires an explicit human reviewer approval."
            )

        # Invariant 4: Check permitted transition map
        allowed = PERMITTED_TRANSITIONS.get(from_state, set())
        if to_state not in allowed:
            raise InvalidStateTransitionError(
                from_state, to_state, f"Transition from {from_state} to {to_state} is not permitted by lifecycle rules."
            )
