"""
Family Financial Advisor — FastAPI app.

Frozen SSE event shape (Day 1):
  event: token  → data: {"text": "...chunk..."}
  event: done   → data: {"session_id": "...", "turn_id": "..."}
  event: error  → data: {"message": "..."}
"""
# SSE event shape FROZEN at end of Day 1 — do not change without updating frontend (Day 2)
from __future__ import annotations

import json
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.agent import pipeline, sessions
from backend.agent.llm_provider import get_provider
from backend.agent.memory_updater import close_session
from backend.agent.pipeline import TurnDone, TurnError, TurnToken
from backend.config import settings
from backend.utils import markdown_io

logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(name)s: %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# Idle poll cadence — sweep stale sessions to summarize and close them.
_IDLE_SWEEP_SECONDS = 60


async def _sweep_idle() -> None:
    """Summarize and close sessions that have gone idle past the staleness
    threshold. Runs on the scheduler; failures are isolated per session."""
    for member, sid in sessions.idle_sessions(time.monotonic()):
        try:
            await close_session(member, sid)
            sessions.close(member)
        except Exception:
            logger.exception("idle sweep failed: %s/%s", member, sid)


@asynccontextmanager
async def lifespan(app: FastAPI):
    sched = AsyncIOScheduler()
    sched.add_job(_sweep_idle, "interval", seconds=_IDLE_SWEEP_SECONDS)
    sched.start()
    try:
        yield
    finally:
        sched.shutdown(wait=False)


app = FastAPI(title="Family Financial Advisor", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_provider = get_provider()


class ChatRequest(BaseModel):
    message: str


class SessionCloseRequest(BaseModel):
    member: str | None = None


def _assert_member_exists(member: str) -> None:
    member_dir = settings.resolve(settings.memory_dir) / "members" / member
    if not member_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"unknown member: {member}")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": settings.main_agent_model}


@app.get("/api/members")
def list_members() -> dict:
    return {"members": markdown_io.list_member_dirs(settings.resolve(settings.memory_dir))}


@app.get("/api/history")
def history(x_member_id: str = Header(..., alias="X-Member-Id")) -> dict:
    _assert_member_exists(x_member_id)
    active_sid = sessions.get_active(x_member_id, time.monotonic())
    if active_sid is None:
        return {"session_id": None, "messages": []}
    return {
        "session_id": active_sid,
        "messages": sessions.get_history(x_member_id, active_sid),
    }


@app.post("/chat")
async def chat(
    req: ChatRequest,
    x_member_id: str = Header(..., alias="X-Member-Id"),
):
    _assert_member_exists(x_member_id)

    async def event_stream() -> AsyncIterator[dict]:
        # The block below is the ONLY place TurnEvent → SSE mapping exists.
        # SSE event shape is FROZEN — see module docstring.
        async for ev in pipeline.run_chat_turn(
            provider=_provider,
            member=x_member_id,
            user_message=req.message,
            memory_root=settings.resolve(settings.memory_dir),
            skills_root=settings.resolve(settings.skills_dir),
            max_tokens=settings.max_response_tokens,
        ):
            if isinstance(ev, TurnToken):
                yield {"event": "token", "data": json.dumps({"text": ev.text})}
            elif isinstance(ev, TurnDone):
                yield {
                    "event": "done",
                    "data": json.dumps(
                        {"session_id": ev.session_id, "turn_id": ev.turn_id}
                    ),
                }
            elif isinstance(ev, TurnError):
                yield {"event": "error", "data": json.dumps({"message": ev.message})}
                return

    return EventSourceResponse(event_stream())


@app.post("/session/close", status_code=204)
async def session_close(
    req: SessionCloseRequest,
    x_member_id: str | None = Header(default=None, alias="X-Member-Id"),
) -> Response:
    member = req.member or x_member_id
    if member:
        active_sid = sessions.get_active(member, time.monotonic())
        if active_sid is not None:
            await close_session(member, active_sid)
        sessions.close(member)
    return Response(status_code=204)
