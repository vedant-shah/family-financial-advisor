from __future__ import annotations

import pytest

from backend.agent import memory_updater
from backend.agent.memory_updater import close_session
from backend.agent.transcripts import transcript_path
from backend.config import settings


@pytest.fixture(autouse=True)
def reset_provider():
    memory_updater._provider = None
    yield
    memory_updater._provider = None


def _write_transcript(member: str, session_id: str) -> None:
    path = transcript_path(member, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"user_msg":"where to park 5L","assistant_msg":"liquid fund"}\n')


async def test_happy_path_writes_summary_and_recommendation(tmp_memory, fake_provider):
    fake_provider.payload = {
        "summary_3_lines": ["talked surplus", "park 5L", "liquid fund"],
        "new_recommendations": [
            {"title": "Park surplus", "priority": 1, "assumptions": "5L matured"}
        ],
    }
    memory_updater._provider = fake_provider
    _write_transcript("vedant", "sess1")

    await close_session("vedant", "sess1")

    conv = (tmp_memory / "members" / "vedant" / "conversations.md").read_text()
    rec = (tmp_memory / "members" / "vedant" / "recommendations.md").read_text()
    assert "park 5L" in conv
    assert "Status: PROPOSED" in rec
    marker = settings.resolve(settings.sessions_dir) / "vedant" / "sess1.closed"
    assert marker.exists()
    assert fake_provider.calls == 1


async def test_existing_marker_is_noop(tmp_memory, fake_provider):
    memory_updater._provider = fake_provider
    _write_transcript("vedant", "sess1")
    marker = settings.resolve(settings.sessions_dir) / "vedant" / "sess1.closed"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.touch()

    await close_session("vedant", "sess1")

    # No model call, no files written.
    assert fake_provider.calls == 0
    assert not (tmp_memory / "members" / "vedant" / "conversations.md").exists()


async def test_no_transcript_marks_closed_only(tmp_memory, fake_provider):
    memory_updater._provider = fake_provider
    # No transcript file written for this session.
    await close_session("vedant", "ghost")
    marker = settings.resolve(settings.sessions_dir) / "vedant" / "ghost.closed"
    assert marker.exists()
    assert fake_provider.calls == 0  # never reached the model


async def test_empty_response_marks_closed_without_entries(tmp_memory, fake_provider):
    fake_provider.payload = {}
    memory_updater._provider = fake_provider
    _write_transcript("vedant", "sess2")

    await close_session("vedant", "sess2")

    marker = settings.resolve(settings.sessions_dir) / "vedant" / "sess2.closed"
    assert marker.exists()
    assert not (tmp_memory / "members" / "vedant" / "conversations.md").exists()
    assert not (tmp_memory / "members" / "vedant" / "recommendations.md").exists()


async def test_second_close_adds_no_duplicate(tmp_memory, fake_provider):
    fake_provider.payload = {"summary_3_lines": ["one", "two", "three"]}
    memory_updater._provider = fake_provider
    _write_transcript("vedant", "sess3")

    await close_session("vedant", "sess3")
    await close_session("vedant", "sess3")  # marker present → no-op

    conv = (tmp_memory / "members" / "vedant" / "conversations.md").read_text()
    assert conv.count("## ") == 1  # exactly one dated block
    assert fake_provider.calls == 1
