from __future__ import annotations

import pytest

from backend.agent import writers
from backend.agent.writers import CrossMemberWriteError
from backend.config import settings


def test_own_recommendation_written_with_schema_fields(tmp_memory):
    writers.write_recommendation(
        "vedant", title="Park surplus", priority=1, body="5L FD matured", date="2026-06-01"
    )
    content = (tmp_memory / "members" / "vedant" / "recommendations.md").read_text()
    assert "## Park surplus" in content
    assert "Date: 2026-06-01" in content
    assert "Priority: P1" in content
    assert "Status: PROPOSED" in content
    assert "Assumptions_at_time: 5L FD matured" in content


def test_conversation_summary_appends_dated_block(tmp_memory):
    writers.append_conversation_summary(
        "vedant", date="2026-06-01", summary_lines=["talked surplus", "park 5L liquid"]
    )
    content = (tmp_memory / "members" / "vedant" / "conversations.md").read_text()
    assert "## 2026-06-01" in content
    assert "- talked surplus" in content
    assert "- park 5L liquid" in content


def test_goal_and_life_event_write_to_own_tree(tmp_memory):
    writers.write_goal("vedant", title="House", target="50L", horizon="7y", date="2026-06-01")
    writers.write_life_event("vedant", description="got married", date="2026-06-01")
    assert (tmp_memory / "members" / "vedant" / "goals.md").exists()
    assert (tmp_memory / "members" / "vedant" / "life_events.md").exists()


def test_cross_member_write_raises(tmp_memory):
    other = settings.resolve(settings.memory_dir) / "members" / "mom" / "recommendations.md"
    with pytest.raises(CrossMemberWriteError):
        writers._assert_writable("vedant", other)


def test_cross_member_via_public_writer_raises(tmp_memory, monkeypatch):
    # Force _member_file to resolve to another member's path, simulating a
    # hallucinated target, and confirm the guard catches it.
    bad = settings.resolve(settings.memory_dir) / "members" / "mom" / "recommendations.md"
    monkeypatch.setattr(writers, "_member_file", lambda writer, fname: bad)
    with pytest.raises(CrossMemberWriteError):
        writers.write_recommendation(
            "vedant", title="x", priority=2, body="y", date="2026-06-01"
        )


def test_family_write_allowed(tmp_memory):
    family_file = settings.resolve(settings.memory_dir) / "family" / "inferences.md"
    # Should not raise — family/ is a permitted destination for any writer.
    writers._assert_writable("vedant", family_file)
