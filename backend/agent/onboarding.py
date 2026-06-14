"""Onboarding completion marker, stored as a field in the member's profile.md.

Option-1 completion bar: a member is "onboarded" once they reach the finish
screen, regardless of which screens they skipped (every screen is skippable by
design). We record this as frontmatter on profile.md (`onboarding_status` /
`onboarding_completed_at`) rather than a separate file: finishing setup is a
per-member meta-flag, not a financial fact with conflict semantics.

This is safe because the current-value write engine preserves a file's preamble
(frontmatter) across later block upserts (`current_value._split_blocks`), and the
assembler strips frontmatter before context assembly — so the flag survives
profile edits yet stays invisible to the advisor.

The chat reads `is_complete` to decide whether to softly nudge the active
member toward the onboarding page.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import frontmatter

from backend.utils.markdown_io import write_markdown_atomic

_PROFILE_NAME = "profile.md"
_STATUS_KEY = "onboarding_status"
_COMPLETED_AT_KEY = "onboarding_completed_at"
_COMPLETE = "complete"


def _profile_path(memory_root: Path, member: str) -> Path:
    return memory_root / "members" / member / _PROFILE_NAME


def is_complete(memory_root: Path, member: str) -> bool:
    """True once the member has finished onboarding. False if profile.md is
    absent or carries no completion flag (never onboarded)."""
    path = _profile_path(memory_root, member)
    if not path.is_file():
        return False
    post = frontmatter.loads(path.read_text(encoding="utf-8"))
    return post.get(_STATUS_KEY) == _COMPLETE


def mark_complete(memory_root: Path, member: str, today: date | None = None) -> None:
    """Record onboarding completion as frontmatter on the member's profile.md,
    preserving any existing identity blocks. Idempotent: re-marking rewrites the
    same flag. The caller validates `member` and ensures the member dir exists."""
    day = today or date.today()
    path = _profile_path(memory_root, member)
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    post = frontmatter.loads(existing)
    post[_STATUS_KEY] = _COMPLETE
    post[_COMPLETED_AT_KEY] = day.isoformat()
    write_markdown_atomic(path, frontmatter.dumps(post) + "\n")
