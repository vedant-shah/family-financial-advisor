"""Persist the onboarding "who" phase: the family roster → member dirs + profiles.

The backend owns canonical member ids (slugify + dedup against existing dirs), so
the picker — which lists `memory/members/` — reflects what onboarding produced.

Isolation-preserving by design (MEMORY_DATA_MODEL §7): each member's profile is
written *as that member* (`write_profile(writer=<their own id>)`), so the
per-writer cross-member guard passes naturally — this is N self-authored writes,
never one cross-member write.

Create-or-update only. This module never deletes a member tree; removing someone
from the draft simply stops re-creating them (deletion is a deferred,
confirmation-gated policy).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from backend.agent import writers
from backend.utils.markdown_io import list_member_dirs, write_markdown_atomic

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Lowercase, collapse non-alphanumerics to hyphens, trim. Matches the safe
    member-id slug (`^[a-z0-9_-]{1,64}$`); empty names fall back to 'member'."""
    s = _NON_SLUG.sub("-", name.lower().strip()).strip("-")
    return (s or "member")[:64]


def _assign_id(name: str, provided_id: str | None, taken: set[str]) -> str:
    """A known id that already exists is reused (update path); otherwise derive a
    fresh id from the name and dedup against ids already taken."""
    if provided_id and provided_id in taken:
        return provided_id
    base = slugify(name)
    candidate = base
    n = 2
    while candidate in taken:
        candidate = f"{base}-{n}"
        n += 1
    return candidate


@dataclass(frozen=True)
class PersistedMember:
    id: str
    name: str
    is_self: bool


def _relationship(m: dict) -> str:
    return m.get("relationship") or ("self" if m.get("isSelf") else "family")


def _write_household(memory_root: Path, members: list[dict], ids: list[str], *, today: str) -> None:
    """(Re)write family/household.md so it reflects the current roster. This is
    the family overview the assembler always loads, so the advisor can answer
    "who is in my family". Family-scoped write (any member may write family/)."""
    rows = "\n".join(
        f"| {mid} | {m['name']} | {_relationship(m)} | "
        f"{'yes' if m.get('earns') else 'no'} |"
        for m, mid in zip(members, ids)
    )
    content = (
        f"---\nlast_updated: {today}\n---\n\n"
        "# Household\n\n"
        "## Members\n"
        "| member_id | Name | Relationship | Earning |\n"
        "|---|---|---|---|\n"
        f"{rows}\n"
    )
    write_markdown_atomic(memory_root / "family" / "household.md", content)


def persist_roster(
    memory_root: Path, members: list[dict], *, today: str
) -> list[PersistedMember]:
    """Create/update each roster member's dir + identity profile.md, in order.

    `members` are draft dicts: {name, relationship?, age?, earns, occupation?,
    isSelf, moneyComfort?, id?}. Returns the persisted members (same order) with
    their canonical ids, so the client can re-key its local draft."""
    taken = set(list_member_dirs(memory_root))
    result: list[PersistedMember] = []
    ids: list[str] = []
    for m in members:
        mid = _assign_id(m["name"], m.get("id"), taken)
        taken.add(mid)
        ids.append(mid)
        writers.write_profile(
            mid,
            name=m["name"],
            relationship=_relationship(m),
            as_of=today,
            age=m.get("age"),
            earning_status="earning" if m.get("earns") else "not_earning",
            occupation=m.get("occupation"),
            financial_literacy=m.get("moneyComfort"),
        )
        result.append(
            PersistedMember(id=mid, name=m["name"], is_self=bool(m.get("isSelf")))
        )
    _write_household(memory_root, members, ids, today=today)
    return result
