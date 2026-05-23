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
import uuid
from typing import AsyncIterator

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.agent.assembler import AssemblyError, ClassifierOutput, assemble
from backend.agent.llm_provider import (
    StreamEnd,
    StreamError,
    TextDelta,
    ToolUseRequest,
    get_provider,
)
from backend.agent.orchestrator import run_turn
from backend.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(title="Family Financial Advisor")

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
    session_id: str | None = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": settings.main_agent_model}


@app.post("/chat")
async def chat(
    req: ChatRequest,
    x_member_id: str = Header(..., alias="X-Member-Id"),
):
    session_id = req.session_id or str(uuid.uuid4())
    turn_id = str(uuid.uuid4())

    classifier_output: ClassifierOutput = {
        "context_level": "FULL",
        "relevant_memory_files": [],
        "is_followup": False,
    }

    # Assemble BEFORE opening the stream so we can return HTTP 400 cleanly.
    try:
        prompt = assemble(
            active_member=x_member_id,
            classifier_output=classifier_output,
            in_session_history=[],
            user_message=req.message,
            memory_root=settings.resolve(settings.memory_dir),
            skills_root=settings.resolve(settings.skills_dir),
        )
    except AssemblyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async def event_stream() -> AsyncIterator[dict]:
        try:
            async for event in run_turn(
                provider=_provider,
                prompt=prompt,
                max_tokens=settings.max_response_tokens,
            ):
                if isinstance(event, TextDelta):
                    yield {"event": "token", "data": json.dumps({"text": event.text})}
                elif isinstance(event, ToolUseRequest):
                    logger.info("orchestrator: tool use ignored on Day 1: %s", event.name)
                    continue
                elif isinstance(event, StreamEnd):
                    logger.info(
                        "stream end: stop_reason=%s in=%d out=%d cache_r=%d cache_w=%d",
                        event.stop_reason,
                        event.input_tokens,
                        event.output_tokens,
                        event.cache_read_tokens,
                        event.cache_write_tokens,
                    )
                elif isinstance(event, StreamError):
                    yield {"event": "error", "data": json.dumps({"message": event.message})}
                    return
            yield {
                "event": "done",
                "data": json.dumps({"session_id": session_id, "turn_id": turn_id}),
            }
        except Exception as exc:
            logger.exception("chat stream failed")
            yield {"event": "error", "data": json.dumps({"message": str(exc)})}

    return EventSourceResponse(event_stream())
