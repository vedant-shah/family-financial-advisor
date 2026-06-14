"""write_profile: onboarding's identity writer for profile.md (MEMORY_DATA_MODEL §4).

profile.md is a current-value file holding IDENTITY ONLY (name, relationship,
age, earning status, occupation, financial literacy) with provenance — never
money figures. One block per field so a later single-field correction supersedes
cleanly. Writes are idempotent per (field, value): an unchanged resubmit is a
NOOP; a changed value supersedes the prior block.
"""
from __future__ import annotations

from backend.agent import writers
from backend.agent.current_value import UpsertOutcome


def _profile(tmp_memory, member="vedant"):
    return (tmp_memory / "members" / member / "profile.md").read_text()


def test_write_profile_writes_identity_fields_with_provenance(tmp_memory):
    out = writers.write_profile(
        "vedant",
        name="Vedant Shah",
        relationship="self",
        as_of="2026-06-13",
        age=25,
        earning_status="earning",
        occupation="Engineer",
        financial_literacy="high",
    )
    assert out["name"] is UpsertOutcome.INSERTED
    content = _profile(tmp_memory)
    assert "## identity.name" in content
    assert "- name: Vedant Shah" in content
    assert "## identity.relationship" in content
    assert "- relationship: self" in content
    assert "- age: 25" in content
    assert "- earning_status: earning" in content
    assert "- occupation: Engineer" in content
    assert "- financial_literacy: high" in content
    # Provenance + spec source on every block.
    assert "- source: onboarding_form" in content
    assert "- as_of: 2026-06-13" in content
    assert "- status: CURRENT" in content


def test_write_profile_skips_empty_optional_fields(tmp_memory):
    # Lazy: a fact-less field gets no block (MEMORY_DATA_MODEL §6).
    writers.write_profile(
        "vedant",
        name="Vedant",
        relationship="self",
        as_of="2026-06-13",
    )
    content = _profile(tmp_memory)
    assert "## identity.name" in content
    assert "## identity.age" not in content
    assert "## identity.occupation" not in content
    assert "## identity.financial_literacy" not in content


def test_write_profile_writes_no_money_figures(tmp_memory):
    writers.write_profile(
        "vedant", name="Vedant", relationship="self", as_of="2026-06-13",
        earning_status="earning",
    )
    content = _profile(tmp_memory).lower()
    for forbidden in ("income", "salary", "amount", "loan", "asset", "₹", "rupee"):
        assert forbidden not in content


def test_write_profile_unchanged_resubmit_is_noop(tmp_memory):
    kwargs = dict(
        name="Vedant", relationship="self", as_of="2026-06-13", age=25,
        earning_status="earning",
    )
    writers.write_profile("vedant", **kwargs)
    out = writers.write_profile("vedant", **kwargs)
    assert out["name"] is UpsertOutcome.NOOP
    assert out["age"] is UpsertOutcome.NOOP
    # Exactly one CURRENT name block, no duplication.
    content = _profile(tmp_memory)
    assert content.count("## identity.name") == 1


def test_write_profile_changed_field_supersedes(tmp_memory):
    writers.write_profile(
        "vedant", name="Vedant", relationship="self", as_of="2026-06-13",
    )
    out = writers.write_profile(
        "vedant", name="Veds", relationship="self", as_of="2026-06-14",
    )
    assert out["name"] is UpsertOutcome.SUPERSEDED
    content = _profile(tmp_memory)
    assert "- name: Veds" in content
    assert "- status: CURRENT" in content
    assert "- status: SUPERSEDED" in content
    # relationship unchanged -> idempotent NOOP, not a second block.
    assert out["relationship"] is UpsertOutcome.NOOP


def test_write_profile_writes_under_own_member_tree_only(tmp_memory):
    # writer == target member, so the cross-member guard passes naturally and
    # each profile is self-authored (architect's isolation-preserving design).
    writers.write_profile(
        "mom", name="Mom", relationship="mother", as_of="2026-06-13",
    )
    assert (tmp_memory / "members" / "mom" / "profile.md").exists()
    assert "## identity.name" in _profile(tmp_memory, "mom")
