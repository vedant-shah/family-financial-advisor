from __future__ import annotations

from typing import AsyncIterator

from backend.agent.assembler import AssembledPrompt
from backend.agent.llm_provider import LLMProvider, StreamEvent


async def run_turn(
    *,
    provider: LLMProvider,
    prompt: AssembledPrompt,
    tools: list[dict] | None = None,
    max_tokens: int = 2048,
    model: str | None = None,
) -> AsyncIterator[StreamEvent]:
    async for event in provider.stream(
        system=prompt.system,
        messages=prompt.messages,
        tools=tools,
        max_tokens=max_tokens,
        model=model,
    ):
        yield event
