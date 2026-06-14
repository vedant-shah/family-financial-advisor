"""run_chat_turn must sanitize the reply through text_utils before emitting it.

Every response goes through backend/text_utils.to_bubbles: em dashes are stripped
and the reply is normalized to blank-line-separated bubbles. The reply is
buffered and emitted sanitized (not streamed raw token-by-token), so a stray em
dash from the model never reaches the user, and the stored history matches.
"""
from __future__ import annotations

import time

from backend.agent.llm_provider import StreamEnd, TextDelta
from backend.agent.pipeline import TurnDone, TurnToken, run_chat_turn
from backend.agent import sessions
from backend.config import settings

_MINIMAL = {"context_level": "MINIMAL", "intent": "portfolio_review", "is_followup": False}


class StreamingFake:
    """Provider stub: complete_json drives the classifier, stream yields the
    given deltas then a StreamEnd."""

    def __init__(self, payload: dict, deltas: list[str]) -> None:
        self.payload = payload
        self.deltas = deltas

    async def complete_json(self, **kwargs) -> dict:
        return self.payload

    async def stream(self, **kwargs):
        for d in self.deltas:
            yield TextDelta(d)
        yield StreamEnd(
            stop_reason="end_turn",
            input_tokens=1,
            output_tokens=1,
            cache_read_tokens=0,
            cache_write_tokens=0,
        )


async def _collect(provider, tmp_memory):
    tokens, done = [], None
    async for ev in run_chat_turn(
        provider=provider,
        member="vedant",
        user_message="tell me about yourself",
        memory_root=tmp_memory,
        skills_root=settings.resolve(settings.skills_dir),
        max_tokens=100,
    ):
        if isinstance(ev, TurnToken):
            tokens.append(ev.text)
        elif isinstance(ev, TurnDone):
            done = ev
    return tokens, done


async def test_em_dash_stripped_from_emitted_reply(tmp_memory):
    provider = StreamingFake(
        _MINIMAL, ["lemme be straight with u — i know stuff", "\n\n", "thats it"]
    )
    tokens, done = await _collect(provider, tmp_memory)
    out = "".join(tokens)
    assert "—" not in out
    assert "thats it" in out
    assert done is not None


async def test_reply_buffered_into_blank_line_bubbles(tmp_memory):
    provider = StreamingFake(_MINIMAL, ["first beat", "\n\n", "second beat"])
    tokens, _ = await _collect(provider, tmp_memory)
    out = "".join(tokens)
    # Two bubbles survive as a blank-line break the frontend can split on.
    assert "first beat\n\nsecond beat" in out


async def test_stored_history_is_sanitized(tmp_memory):
    provider = StreamingFake(_MINIMAL, ["clean this — please"])
    await _collect(provider, tmp_memory)
    sid = sessions.get_active("vedant", time.monotonic())
    history = sessions.get_history("vedant", sid)
    assistant = [m for m in history if m["role"] == "assistant"][-1]
    assert "—" not in assistant["content"]
