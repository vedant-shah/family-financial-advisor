"""
Resuming a conversation after in-memory session state is lost (e.g. a backend
restart). History is served from RAM; these cover the disk fallback that
rehydrates the most recent unclosed, non-stale session from its transcript.

TDD: written FIRST (RED). Conventions mirror test_durability.py — tmp_memory
fixture, autouse reset of in-memory session state, ISO ts strings built relative
to a controllable `now`.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from backend.agent import durability, sessions
from backend.agent.transcripts import mark_post_processed, read_turns, transcript_path


@pytest.fixture(autouse=True)
def reset_state():
    sessions._active.clear()
    sessions._activity.clear()
    sessions._history.clear()
    yield
    sessions._active.clear()
    sessions._activity.clear()
    sessions._history.clear()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _ts(now: datetime, seconds_ago: int) -> str:
    return (now - timedelta(seconds=seconds_ago)).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _write_turns(member: str, session_id: str, turns: list[dict]) -> Path:
    """Write a transcript from a list of raw JSONL records. The last record's
    `ts` controls the session's wall-clock age."""
    path = transcript_path(member, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(t) for t in turns) + "\n")
    return path


# ---------------------------------------------------------------------------
# read_turns — reconstruct in-session history from a transcript
# ---------------------------------------------------------------------------

def test_read_turns_reconstructs_user_assistant_pairs(tmp_memory):
    _write_turns("vedant", "s1", [
        {"ts": "2026-06-21T10:00:00.000Z", "user_msg": "hi", "assistant_msg": "hello"},
        {"ts": "2026-06-21T10:01:00.000Z", "user_msg": "markets?", "assistant_msg": "up"},
    ])

    assert read_turns("vedant", "s1") == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "markets?"},
        {"role": "assistant", "content": "up"},
    ]


def test_read_turns_skips_error_and_terminal(tmp_memory):
    # Error turns are never committed to in-session history, and the terminal
    # post-processing event is not a turn — both must be skipped so the result
    # matches what in-memory state held.
    _write_turns("vedant", "s2", [
        {"ts": "2026-06-21T10:00:00.000Z", "user_msg": "ok", "assistant_msg": "sure"},
        {"ts": "2026-06-21T10:01:00.000Z", "user_msg": "boom", "assistant_msg": "", "error": "overloaded: x"},
        {"type": "post_processing", "status": "completed", "ts": "2026-06-21T10:05:00.000Z"},
    ])

    assert read_turns("vedant", "s2") == [
        {"role": "user", "content": "ok"},
        {"role": "assistant", "content": "sure"},
    ]


def test_read_turns_missing_file_returns_empty(tmp_memory):
    assert read_turns("vedant", "nope") == []


# ---------------------------------------------------------------------------
# adopt_recent_session — rehydrate the resumable session into memory
# ---------------------------------------------------------------------------

def test_adopt_recent_rehydrates_fresh_session(tmp_memory):
    now = _now_utc()
    _write_turns("vedant", "live", [
        {"ts": _ts(now, 600), "user_msg": "hi", "assistant_msg": "hello"},
        {"ts": _ts(now, 120), "user_msg": "more", "assistant_msg": "ok"},
    ])

    mono = time.monotonic()
    sid = durability.adopt_recent_session("vedant", mono, now)

    assert sid == "live"
    # Now reachable via the normal in-memory path the endpoint uses.
    assert sessions.get_active("vedant", mono) == "live"
    assert sessions.get_history("vedant", "live") == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
        {"role": "user", "content": "more"},
        {"role": "assistant", "content": "ok"},
    ]


def test_adopt_recent_ignores_post_processed(tmp_memory):
    now = _now_utc()
    _write_turns("vedant", "done", [
        {"ts": _ts(now, 120), "user_msg": "hi", "assistant_msg": "hello"},
    ])
    mark_post_processed("vedant", "done")

    assert durability.adopt_recent_session("vedant", time.monotonic(), now) is None


def test_adopt_recent_ignores_stale(tmp_memory):
    now = _now_utc()
    stale_ago = sessions.STALE_AFTER_SECONDS + 120
    _write_turns("vedant", "old", [
        {"ts": _ts(now, stale_ago), "user_msg": "hi", "assistant_msg": "hello"},
    ])

    assert durability.adopt_recent_session("vedant", time.monotonic(), now) is None


def test_adopt_recent_picks_most_recent_open(tmp_memory):
    now = _now_utc()
    _write_turns("vedant", "older", [
        {"ts": _ts(now, 800), "user_msg": "a", "assistant_msg": "1"},
    ])
    _write_turns("vedant", "newer", [
        {"ts": _ts(now, 100), "user_msg": "b", "assistant_msg": "2"},
    ])

    assert durability.adopt_recent_session("vedant", time.monotonic(), now) == "newer"


def test_adopt_recent_none_when_no_sessions(tmp_memory):
    assert durability.adopt_recent_session("vedant", time.monotonic(), _now_utc()) is None
