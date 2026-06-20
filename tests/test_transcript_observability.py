"""Turn transcripts capture the observability fields the weekly audit needs.

Each turn line records not just the text exchanged but WHAT the agent knew
(context_level + which memory files loaded), what its tools returned, the model
usage/latency, and any error — so an audit can explain *why* a turn behaved as
it did, not just *that* it did. New fields are appended with safe defaults so
older readers and records keep working.
"""
from __future__ import annotations

import json

from backend.agent import transcripts
from backend.agent.transcripts import TranscriptRecord


def _read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_new_fields_serialized(tmp_memory):
    rec = TranscriptRecord(
        ts="2026-06-19T00:00:00.000Z",
        member="vedant",
        session_id="s1",
        turn_id="t01",
        user_msg="hi",
        assistant_msg="hey",
        tool_calls=(
            {
                "name": "read_context",
                "input": {"name": "member.finances"},
                "ok": True,
                "result": "income 1.15l",
            },
        ),
        intent="general",
        context_level="FULL",
        loaded_context=("skill.core_system", "member.finances"),
        missing_context=("member.goals",),
        model="claude-sonnet-4-6",
        input_tokens=1200,
        output_tokens=80,
        cache_read_tokens=900,
        cache_write_tokens=0,
        latency_ms=2310.5,
        cost_usd=0.0042,
        stop_reason="end_turn",
        error=None,
    )
    transcripts.append_turn(rec)

    [line] = _read_lines(transcripts.transcript_path("vedant", "s1"))
    assert line["context_level"] == "FULL"
    assert line["loaded_context"] == ["skill.core_system", "member.finances"]
    assert line["missing_context"] == ["member.goals"]
    assert line["model"] == "claude-sonnet-4-6"
    assert line["input_tokens"] == 1200
    assert line["latency_ms"] == 2310.5
    assert line["cost_usd"] == 0.0042
    assert line["stop_reason"] == "end_turn"
    assert line["error"] is None
    assert line["tool_calls"][0]["result"] == "income 1.15l"


def test_defaults_backward_compatible(tmp_memory):
    # An old-style record (only the original fields) still appends, with the new
    # observability fields present at safe defaults.
    rec = TranscriptRecord(
        ts="2026-06-19T00:00:00.000Z",
        member="vedant",
        session_id="s2",
        turn_id="t01",
        user_msg="hi",
        assistant_msg="hey",
    )
    transcripts.append_turn(rec)

    [line] = _read_lines(transcripts.transcript_path("vedant", "s2"))
    assert line["context_level"] == "unknown"
    assert line["loaded_context"] == []
    assert line["missing_context"] == []
    assert line["model"] == ""
    assert line["input_tokens"] == 0
    assert line["stop_reason"] == ""
    assert line["error"] is None
