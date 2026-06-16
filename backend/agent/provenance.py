"""
Provenance: where a stored fact came from, how sure we are, and how fresh it is.

Every current-value and dated-log entry carries provenance (MEMORY_DATA_MODEL §3)
so a recalled conversational number never silently overwrites a bank statement.
The authority order governs supersede decisions in the current-value engine.
"""
from __future__ import annotations

from dataclasses import dataclass

# Source-authority precedence (MEMORY_DATA_MODEL §3):
#   document_upload ≈ brokerage_sync > conversation
#                                    > onboarding_form ≈ onboarding_quiz > inference
# Self-stated facts are authoritative: a first-person conversational statement
# outranks the onboarding form (the user is the source of truth, and a later
# correction should win), while objective documents/syncs stay above everything.
_AUTHORITY: dict[str, int] = {
    "document_upload": 4,
    "brokerage_sync": 4,
    "conversation": 3,
    "onboarding_form": 2,
    "onboarding_quiz": 2,
    "inference": 1,
}


@dataclass(frozen=True)
class Provenance:
    """Immutable provenance stamp written onto a stored fact."""

    source: str
    confidence: str  # low | med | high
    as_of: str  # YYYY-MM-DD — date the value was true
    last_updated: str  # YYYY-MM-DD — date the entry was written


def authority_of(source: str) -> int:
    """Authority rank of a source; unknown sources rank lowest (treated as a guess)."""
    return _AUTHORITY.get(source, 0)
