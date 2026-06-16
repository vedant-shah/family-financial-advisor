"""Promote stranded cross-member observations into the household roster (M5, #7).

Observations one member makes about another ("my brother is 18, a student")
pile up in working/cross_member_observations.md and never reach the roster, so
the advisor never knows those people exist. Promotion reads them and ADDS the
missing people to family/household.md (always-loaded). It never overwrites an
existing roster row: when a new observation contradicts a stored fact (earning
status), it stages the conflict for confirmation instead.
"""
from __future__ import annotations

import pytest

from backend.agent.promotion import promote_observations

TODAY = "2026-06-16"


@pytest.fixture
def root(tmp_path):
    (tmp_path / "working").mkdir()
    (tmp_path / "family").mkdir()
    return tmp_path


def _obs(root, lines: str):
    (root / "working" / "cross_member_observations.md").write_text(lines)


def _household(root, rows: str):
    (root / "family" / "household.md").write_text(
        "---\nlast_updated: 2026-06-14\n---\n\n# Household\n\n## Members\n"
        "| member_id | Name | Relationship | Earning |\n|---|---|---|---|\n" + rows
    )


def test_new_people_added_existing_not_duplicated(root):
    _household(root, "| vedant | vedant | self | yes |\n| dharmendra | dharmendra | Father | yes |\n")
    _obs(
        root,
        "- 2026-06-14 — (via vedant, about Dharmendra (dad)): father, also earning <!-- id:a -->\n"
        "- 2026-06-14 — (via vedant, about mother): home baker earning some income <!-- id:b -->\n"
        "- 2026-06-14 — (via vedant, about brother): 18 years old, student <!-- id:c -->\n",
    )
    promote_observations(root, today=TODAY)

    hh = (root / "family" / "household.md").read_text()
    assert "| mother |" in hh          # new person added
    assert "| brother |" in hh         # new person added
    assert hh.count("| dharmendra |") == 1   # existing not duplicated


def test_earning_status_inferred(root):
    _household(root, "| vedant | vedant | self | yes |\n")
    _obs(
        root,
        "- 2026-06-14 — (via vedant, about mother): home baker earning some income <!-- id:b -->\n"
        "- 2026-06-14 — (via vedant, about brother): 18 years old, student <!-- id:c -->\n",
    )
    promote_observations(root, today=TODAY)

    hh = (root / "family" / "household.md").read_text()
    assert "| mother | mother | mother | yes |" in hh
    assert "| brother | brother | brother | no |" in hh


def test_contradiction_is_staged_not_overwritten(root):
    # dharmendra is on record as earning; a new observation says he retired.
    _household(root, "| vedant | vedant | self | yes |\n| dharmendra | dharmendra | Father | yes |\n")
    _obs(root, "- 2026-06-16 — (via vedant, about Dharmendra (dad)): dad has retired now <!-- id:d -->\n")

    promote_observations(root, today=TODAY)

    hh = (root / "family" / "household.md").read_text()
    assert "| dharmendra | dharmendra | Father | yes |" in hh  # NOT overwritten
    disc = (root / "working" / "discrepancies.md").read_text()
    assert "dharmendra" in disc
    assert "retired" in disc


def test_promotion_is_idempotent(root):
    _household(root, "| vedant | vedant | self | yes |\n")
    _obs(root, "- 2026-06-14 — (via vedant, about brother): 18, student <!-- id:c -->\n")

    promote_observations(root, today=TODAY)
    promote_observations(root, today=TODAY)

    hh = (root / "family" / "household.md").read_text()
    brother_rows = [ln for ln in hh.splitlines() if ln.startswith("| brother ")]
    assert len(brother_rows) == 1


def test_no_observations_is_noop(root):
    _household(root, "| vedant | vedant | self | yes |\n")
    promote_observations(root, today=TODAY)  # no cross_member file at all
    hh = (root / "family" / "household.md").read_text()
    assert "| vedant |" in hh
    assert hh.count("|") > 0  # unchanged, no crash
