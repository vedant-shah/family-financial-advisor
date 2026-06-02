"""
Day 3 end-to-end smoke test (no server needed).

Runs one real chat turn through the pipeline, then closes the session through
the summarizer, and prints the memory files before/after. Logging is set to
INFO so you can watch the classifier, pipeline, and summarizer do their thing.

Usage:
    python day3_smoke.py
    python day3_smoke.py "where should I park 5 lakh that just matured?" vedant

This hits the real Anthropic API (one classify + one stream + one summarize,
all Haiku — a few tenths of a cent total).
"""
from __future__ import annotations

import asyncio
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

# Turn on INFO so the app's logger.info(...) lines are visible. This is the
# only thing standing between you and the classifier/summarizer logs.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)-7s %(name)s: %(message)s",
)
# Quiet the noisy HTTP client logs from the SDK.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("anthropic").setLevel(logging.WARNING)

from backend.agent import memory_updater, sessions  # noqa: E402
from backend.agent.llm_provider import get_provider  # noqa: E402
from backend.agent.pipeline import TurnDone, TurnError, TurnToken, run_chat_turn  # noqa: E402
from backend.config import settings  # noqa: E402
from backend.utils.markdown_io import read_markdown_or_none  # noqa: E402

DEFAULT_MESSAGE = "where should I park 5 lakh that just matured?"
DEFAULT_MEMBER = "vedant"


def _show(member: str, label: str) -> None:
    base = settings.resolve(settings.memory_dir) / "members" / member
    print(f"\n========== {label} ==========")
    for fname in ("conversations.md", "recommendations.md", "goals.md", "life_events.md"):
        content = read_markdown_or_none(base / fname)
        if content is None:
            continue
        print(f"\n--- {fname} ---")
        print(content.rstrip() or "(empty)")


async def main() -> None:
    message = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_MESSAGE
    member = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MEMBER

    provider = get_provider()
    _show(member, "MEMORY BEFORE")

    print(f"\n>>> chat as '{member}': {message!r}\n")
    print("ASSISTANT: ", end="", flush=True)
    session_id = None
    async for ev in run_chat_turn(
        provider=provider,
        member=member,
        user_message=message,
        memory_root=settings.resolve(settings.memory_dir),
        skills_root=settings.resolve(settings.skills_dir),
        max_tokens=settings.max_response_tokens,
    ):
        if isinstance(ev, TurnToken):
            print(ev.text, end="", flush=True)
        elif isinstance(ev, TurnDone):
            session_id = ev.session_id
            print(f"\n\n[turn done: session={ev.session_id} turn={ev.turn_id}]")
        elif isinstance(ev, TurnError):
            print(f"\n\n[turn error: {ev.message}]")
            return

    if session_id is None:
        print("no session produced; aborting close")
        return

    print(f"\n>>> closing session {session_id} (summarizer writes memory)\n")
    await memory_updater.close_session(member, session_id)
    sessions.close(member)

    _show(member, "MEMORY AFTER")


if __name__ == "__main__":
    asyncio.run(main())
