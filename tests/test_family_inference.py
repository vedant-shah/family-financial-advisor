"""The cross-member relevance index writer (`write_family_inference`).

The index is a MAP, not a COPY: it records THAT a relative's situation bears on
others (relevance prose) and WHERE the authoritative figure lives (a pointer),
never the figure itself. Keyed by subject + topic so distinct topics about the
same member coexist while the same topic supersedes. `lifecycle` retires a
relationship that stopped being true.
"""
from __future__ import annotations

import inspect

from backend.agent import writers
from backend.agent.context_registry import entry_by_name
from backend.agent.current_value import UpsertOutcome


def test_writes_values_free_pointer_entry(tmp_memory):
    out = writers.write_family_inference(
        "vedant",
        about="mom",
        topic="home_loan",
        relevance="big EMI competing for the same surplus",
        pointer="members/mom/finances.md#liability.home_loan",
        confidence="high",
        as_of="2026-06-23",
        dedup_id="fi:mom:home_loan:1",
    )
    assert out is UpsertOutcome.INSERTED
    content = (tmp_memory / "family" / "inferences.md").read_text()
    assert "## mom.home_loan" in content
    assert "- subject: mom" in content
    assert "competing for the same surplus" in content
    assert "members/mom/finances.md#liability.home_loan" in content
    assert "- lifecycle: ACTIVE" in content
    assert "status: CURRENT" in content


def test_distinct_topics_about_same_member_coexist(tmp_memory):
    # Key = subject + topic, so a second topic about mom must NOT clobber the
    # first (the current-value clobber bug the architect flagged).
    writers.write_family_inference(
        "vedant", about="mom", topic="home_loan", relevance="big EMI",
        pointer="members/mom/finances.md#liability.home_loan",
        confidence="high", as_of="2026-06-23", dedup_id="fi:mom:home_loan:1",
    )
    writers.write_family_inference(
        "vedant", about="mom", topic="retirement", relevance="retires in 2 yrs, income stops",
        pointer="members/mom/profile.md#identity.earning_status",
        confidence="med", as_of="2026-06-23", dedup_id="fi:mom:retirement:1",
    )
    content = (tmp_memory / "family" / "inferences.md").read_text()
    assert "## mom.home_loan" in content
    assert "## mom.retirement" in content
    assert content.count("status: CURRENT") == 2


def test_same_topic_supersedes(tmp_memory):
    writers.write_family_inference(
        "vedant", about="mom", topic="home_loan", relevance="big EMI",
        pointer="members/mom/finances.md#liability.home_loan",
        confidence="high", as_of="2026-06-23", dedup_id="fi:mom:home_loan:1",
    )
    out = writers.write_family_inference(
        "vedant", about="mom", topic="home_loan", relevance="loan now nearly paid off",
        pointer="members/mom/finances.md#liability.home_loan",
        confidence="high", as_of="2026-07-01", dedup_id="fi:mom:home_loan:2",
    )
    assert out is UpsertOutcome.SUPERSEDED
    content = (tmp_memory / "family" / "inferences.md").read_text()
    assert "nearly paid off" in content
    assert "status: SUPERSEDED" in content  # prior kept as history


def test_lifecycle_ended_supported(tmp_memory):
    out = writers.write_family_inference(
        "vedant", about="mom", topic="home_loan", relevance="loan closed, no longer relevant",
        pointer="members/mom/finances.md#liability.home_loan",
        lifecycle="ENDED",
        confidence="high", as_of="2026-07-01", dedup_id="fi:mom:home_loan:end",
    )
    assert out is UpsertOutcome.INSERTED
    content = (tmp_memory / "family" / "inferences.md").read_text()
    assert "- lifecycle: ENDED" in content


def test_writer_has_no_value_parameter():
    # Structural guarantee that the index never stores a figure: there is simply
    # no `value` to pass. Callers supply relevance prose + a pointer instead.
    sig = inspect.signature(writers.write_family_inference)
    assert "value" not in sig.parameters


def test_family_inferences_is_always_loaded():
    entry = entry_by_name("family.inferences")
    assert entry is not None
    assert entry.preload == "always"
    assert entry.scope == "family"
