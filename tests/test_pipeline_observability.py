"""run_chat_turn persists per-turn observability into the transcript.

The data (what context loaded, model usage, tool results, errors) already flows
through a turn; these tests pin that it lands on disk so the weekly audit can
explain behavior, including turns that errored (which previously left no trace).
"""
from __future__ import annotations

import json
import time

from backend.agent import sessions, transcripts
from backend.agent.llm_provider import StreamEnd, StreamError, TextDelta, ToolUseRequest
from backend.agent.pipeline import TurnError, run_chat_turn
from backend.config import settings

_CLASSIFY = {"context_level": "MINIMAL", "intent": "portfolio_review", "is_followup": False}


class ScriptedStreamProvider:
    """complete_json drives the classifier; stream pops one scripted round per call."""

    def __init__(self, payload, rounds):
        self.payload = payload
        self.rounds = [list(r) for r in rounds]

    async def complete_json(self, **kwargs):
        return self.payload

    async def stream(self, **kwargs):
        events = self.rounds.pop(0) if self.rounds else []
        for ev in events:
            yield ev


def _end(reason="end_turn", **kw):
    base = dict(input_tokens=1, output_tokens=1, cache_read_tokens=0, cache_write_tokens=0)
    base.update(kw)
    return StreamEnd(stop_reason=reason, **base)


async def _drain(provider):
    events = []
    async for ev in run_chat_turn(
        provider=provider,
        member="vedant",
        user_message="hey",
        memory_root=settings.memory_dir,
        skills_root=settings.resolve(settings.skills_dir),
        max_tokens=100,
    ):
        events.append(ev)
    return events


def _last_turn_line(member="vedant"):
    sid = sessions.get_active(member, time.monotonic())
    path = transcripts.transcript_path(member, sid)
    lines = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return [line for line in lines if line.get("turn_id")][-1]


async def test_context_and_usage_recorded(tmp_memory):
    provider = ScriptedStreamProvider(
        _CLASSIFY,
        [[TextDelta("hey"), _end(model="claude-sonnet-4-6", input_tokens=1200, output_tokens=42)]],
    )
    await _drain(provider)

    line = _last_turn_line()
    assert line["context_level"] == "MINIMAL"
    assert line["model"] == "claude-sonnet-4-6"
    assert line["input_tokens"] == 1200
    assert line["output_tokens"] == 42
    assert line["stop_reason"] == "end_turn"
    # The persona skill is always loaded; the audit can see what context the agent had.
    assert "skill.core_system" in line["loaded_context"]
    assert line["error"] is None


async def test_tool_result_captured(tmp_memory):
    provider = ScriptedStreamProvider(
        _CLASSIFY,
        [
            [
                TextDelta("lemme check"),
                ToolUseRequest(
                    tool_use_id="tu1", name="read_context", input={"name": "member.finances"}
                ),
                _end("tool_use"),
            ],
            [TextDelta("here it is"), _end()],
        ],
    )
    await _drain(provider)

    line = _last_turn_line()
    assert line["tool_calls"], "tool call should be recorded"
    call = line["tool_calls"][0]
    assert call["name"] == "read_context"
    assert "result" in call  # the tool's returned content is captured, not just ok/fail


async def test_stream_error_writes_error_line(tmp_memory):
    # A mid-stream provider failure used to abort with no transcript line. Now it
    # leaves an audit trail with the error recorded.
    provider = ScriptedStreamProvider(
        _CLASSIFY,
        [[TextDelta("partial"), StreamError(message="boom", code="http_500")]],
    )
    events = await _drain(provider)

    assert any(isinstance(e, TurnError) for e in events)
    line = _last_turn_line()
    assert line["error"] is not None
    assert "boom" in line["error"]
