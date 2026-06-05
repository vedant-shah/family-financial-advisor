"""
Per-turn orchestration spine.

`run_chat_turn` owns the lifecycle: session resolve → assemble → stream →
history append → transcript write. `backend/main.py` is the only consumer and
maps the yielded TurnEvent union to the FROZEN SSE event shape.

The TurnEvent union below is frozen at end of Day 2 — pipeline never emits raw
SSE strings.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

from backend.agent import sessions, transcripts
from backend.agent.assembler import AssemblyError, assemble
from backend.agent.classifier import classify
from backend.agent.llm_provider import (
    LLMProvider,
    StreamEnd,
    StreamError,
    TextDelta,
    ToolUseRequest,
)
from backend.agent.orchestrator import run_turn
from backend.agent.transcripts import TranscriptRecord

logger = logging.getLogger(__name__)


# --- TurnEvent union (FROZEN at end of Day 2) ---


@dataclass(frozen=True)
class TurnToken:
    text: str


@dataclass(frozen=True)
class TurnDone:
    session_id: str
    turn_id: str


@dataclass(frozen=True)
class TurnError:
    message: str


TurnEvent = TurnToken | TurnDone | TurnError


async def run_chat_turn(
    *,
    provider: LLMProvider,
    member: str,
    user_message: str,
    memory_root: Path,
    skills_root: Path,
    max_tokens: int,
) -> AsyncIterator[TurnEvent]:
    try:
        now = time.monotonic()
        active_sid, _ = sessions.resolve_session(member, now)
        sessions.touch(member, active_sid, now)
        snapshot = sessions.get_history(member, active_sid)

        classification = await classify(
            provider=provider,
            member=member,
            user_message=user_message,
            history=snapshot,
            session_id=active_sid,
        )

        try:
            prompt = assemble(
                active_member=member,
                classifier_output=classification.output,
                in_session_history=snapshot,
                user_message=user_message,
                memory_root=memory_root,
                skills_root=skills_root,
            )
        except AssemblyError as e:
            yield TurnError(str(e))
            return

        logger.info(
            "assembler: intent=%s level=%s loaded=%s missing=%s",
            classification.intent,
            prompt.context_level,
            prompt.debug.get("loaded", []),
            prompt.debug.get("missing", []),
        )

        parts: list[str] = []
        async for ev in run_turn(
            provider=provider, prompt=prompt, max_tokens=max_tokens
        ):
            if isinstance(ev, TextDelta):
                parts.append(ev.text)
                yield TurnToken(ev.text)
            elif isinstance(ev, ToolUseRequest):
                logger.info("pipeline: tool use ignored on Day 2: %s", ev.name)
                continue
            elif isinstance(ev, StreamError):
                # Exponential-retry seam: wrap the `async for` above with
                # backoff before yielding TurnError. Mid-stream failure
                # currently aborts the turn — no history/transcript write.
                yield TurnError(ev.message)
                return
            elif isinstance(ev, StreamEnd):
                logger.info(
                    "llm: model=%s in=%d out=%d cache_r=%d cache_w=%d "
                    "latency_ms=%.0f cost_usd=%.6f stop=%s",
                    ev.model,
                    ev.input_tokens,
                    ev.output_tokens,
                    ev.cache_read_tokens,
                    ev.cache_write_tokens,
                    ev.latency_ms,
                    ev.cost_usd,
                    ev.stop_reason,
                )
                break

        assistant_msg = "".join(parts)
        turn_id = transcripts.turn_id_for(len(snapshot))

        sessions.append_history(member, active_sid, "user", user_message)
        sessions.append_history(member, active_sid, "assistant", assistant_msg)

        transcripts.append_turn(
            TranscriptRecord(
                ts=transcripts.now_iso(),
                member=member,
                session_id=active_sid,
                turn_id=turn_id,
                user_msg=user_message,
                assistant_msg=assistant_msg,
                intent=classification.intent,
            )
        )

        logger.info("turn complete: %s/%s/%s", member, active_sid, turn_id)
        yield TurnDone(active_sid, turn_id)

    except Exception as exc:
        logger.exception("run_chat_turn failed")
        yield TurnError(str(exc))
