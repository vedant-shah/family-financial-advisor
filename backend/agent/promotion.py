"""Promote stranded cross-member observations into the household roster (M5, #7).

Observations one member's session makes about another person are staged to
`working/cross_member_observations.md` and, until now, never went anywhere — the
roster never learned those people exist, so the advisor stayed blind to them.

`promote_observations` reads that staging file and ADDS any mentioned person who
is not already in `family/household.md` (always-loaded, so a promoted person is
immediately visible). It is deliberately conservative:

- It only ever ADDS rows; it never rewrites an existing roster row. So it cannot
  silently contradict a confirmed fact.
- When a new observation conflicts with an existing row (earning status), the
  conflict is staged to `working/discrepancies.md` for confirmation in chat,
  rather than overwriting the roster (decision 2026-06-16).
- It is idempotent: a person already in the roster is skipped, so re-running on
  every session close never duplicates.
"""
from __future__ import annotations

import re
from pathlib import Path

from backend.agent.current_value import append_staging
from backend.agent.roster import slugify
from backend.utils.markdown_io import read_markdown_or_none, write_markdown_atomic

# Each staged line: "DATE — (via WRITER, about ABOUT): OBSERVATION <!-- id:.. -->"
_OBS_RE = re.compile(r"about (.+?)\): (.+?) <!-- id:")

# Earning inferred from the observation prose. NOT-earning is checked first so a
# "retired" or "student" wins even if the sentence also says "income".
_NOT_EARNING = ("student", "retired", "retire", "retiring", "unemployed",
                "homemaker", "not earning", "no income", "dependent", "minor")
_EARNING = ("earning", "income", "salary", "works", "job", "business", "baker", "pension")


def _split_about(about: str) -> tuple[str, str]:
    """"Dharmendra (dad)" -> ("Dharmendra", "dad"); "mother" -> ("mother", "mother")."""
    m = re.match(r"\s*(.+?)\s*\((.+)\)\s*$", about)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    a = about.strip()
    return a, a


def _earning(text: str) -> str | None:
    t = text.lower()
    if any(k in t for k in _NOT_EARNING):
        return "no"
    if any(k in t for k in _EARNING):
        return "yes"
    return None


def _parse_roster_rows(content: str) -> list[tuple[str, str, str, str]]:
    """Existing roster as ordered (member_id, name, relationship, earning) tuples.
    Header and separator rows are skipped."""
    rows: list[tuple[str, str, str, str]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) != 4:
            continue
        mid = cells[0]
        if mid == "member_id" or set(mid) <= set("-"):
            continue
        rows.append((mid, cells[1], cells[2], cells[3]))
    return rows


def _render_household(rows: list[tuple[str, str, str, str]], today: str) -> str:
    body = "\n".join(f"| {mid} | {name} | {rel} | {earn} |" for mid, name, rel, earn in rows)
    return (
        f"---\nlast_updated: {today}\n---\n\n"
        "# Household\n\n## Members\n"
        "| member_id | Name | Relationship | Earning |\n"
        "|---|---|---|---|\n"
        f"{body}\n"
    )


def promote_observations(memory_root: Path, *, today: str) -> None:
    """Add roster rows for people mentioned in cross-member observations but not
    yet in the household; stage earning-status conflicts for confirmation."""
    obs = read_markdown_or_none(memory_root / "working" / "cross_member_observations.md")
    if not obs:
        return

    household_path = memory_root / "family" / "household.md"
    rows = _parse_roster_rows(read_markdown_or_none(household_path) or "")
    by_id = {r[0]: r for r in rows}

    added: list[tuple[str, str, str, str]] = []
    for m in _OBS_RE.finditer(obs):
        name, rel = _split_about(m.group(1))
        text = m.group(2)
        mid = slugify(name)
        earning = _earning(text)

        if mid in by_id:
            stored = by_id[mid][3]
            if earning and stored in ("yes", "no") and earning != stored:
                append_staging(
                    memory_root / "working" / "discrepancies.md",
                    entry=(
                        f"roster {mid}: recorded earning={stored}, but a conversation "
                        f"suggests {earning} (\"{text}\") — confirm"
                    ),
                    dedup_id=f"roster-{mid}-{earning}",
                )
            continue

        if mid in {r[0] for r in added}:
            continue  # several observations about the same new person → one row
        added.append((mid, name, rel, earning or "unknown"))

    if added:
        write_markdown_atomic(household_path, _render_household(rows + added, today))
