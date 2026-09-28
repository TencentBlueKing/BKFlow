"""Compatibility imports for the generic Harness approval verifier."""

import hashlib

from bkflow.harness.services.approval import ApprovalDecision as DebugApprovalDecision
from bkflow.harness.services.approval import ApprovalInvalid as DebugApprovalInvalid
from bkflow.harness.services.approval import (
    ApprovalVerifier,
    normalize_approval_decision,
)


class DebugApprovalVerifier(ApprovalVerifier):
    """Preserve P2's minimal no-backend denial before P3 closed-claim validation."""

    def verify(self, receipt_ref, expected_claims):
        if self._backend is None:
            value = receipt_ref if isinstance(receipt_ref, str) else "invalid-receipt-reference"
            return DebugApprovalDecision(
                allowed=False,
                provider="unconfigured",
                receipt_digest=hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest(),
                claims_digest="0" * 64,
                reason="verifier_unavailable",
            )
        return super().verify(receipt_ref, expected_claims)


__all__ = [
    "DebugApprovalDecision",
    "DebugApprovalInvalid",
    "DebugApprovalVerifier",
    "normalize_approval_decision",
]
