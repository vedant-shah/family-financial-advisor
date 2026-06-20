"""The weekly audit renderer turns raw session transcripts into one readable
view, surfacing the observability fields and FLAGGING turns that errored or had
a failed tool call. Sessions older than the window are excluded.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from scripts.audit_week import render_week

NOW = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)


def _write(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def _turn(turn_id, ts, **kw):
    base = dict(
        ts=ts,
        member="vedant",
        session_id="s",
        turn_id=turn_id,
        user_msg="u",
        assistant_msg="a",
        tool_calls=[],
        intent="general",
        context_level="FULL",
        loaded_context=["skill.core_system"],
        model="claude-sonnet-4-6",
        input_tokens=100,
        output_tokens=10,
        latency_ms=1234.0,
        stop_reason="end_turn",
        error=None,
    )
    base.update(kw)
    return base


def test_renders_recent_session(tmp_path):
    sdir = tmp_path / "sessions"
    _write(
        sdir / "vedant" / "s1.jsonl",
        [
            _turn("t01", "2026-06-19T10:00:00.000Z", user_msg="what do you know about me"),
            {"type": "post_processing", "status": "completed", "ts": "2026-06-19T10:30:00.000Z"},
        ],
    )
    out = render_week(sdir, days=7, now=NOW)
    assert "what do you know about me" in out
    assert "intent=general" in out
    assert "skill.core_system" in out
    assert "1 session" in out


def test_flags_error_and_failed_tool(tmp_path):
    sdir = tmp_path / "sessions"
    _write(
        sdir / "vedant" / "s2.jsonl",
        [
            _turn("t01", "2026-06-19T10:00:00.000Z", error="http_500: boom"),
            _turn(
                "t02",
                "2026-06-19T10:01:00.000Z",
                tool_calls=[
                    {"name": "read_context", "input": {"name": "x"}, "ok": False, "result": "[tool error]"}
                ],
            ),
        ],
    )
    out = render_week(sdir, days=7, now=NOW)
    assert out.count("FLAG") >= 2
    assert "2 flagged" in out
    assert "http_500: boom" in out


def test_excludes_sessions_outside_window(tmp_path):
    sdir = tmp_path / "sessions"
    _write(
        sdir / "vedant" / "old.jsonl",
        [_turn("t01", "2026-05-01T10:00:00.000Z", user_msg="ancient message")],
    )
    out = render_week(sdir, days=7, now=NOW)
    assert "ancient message" not in out
    assert "0 sessions" in out
