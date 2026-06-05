from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import AsyncIterator, Protocol

import anthropic

from backend.config import settings

logger = logging.getLogger(__name__)


# --- Frozen dataclasses (Day 1 contracts — do not change without coordinated update) ---


@dataclass(frozen=True)
class SystemBlock:
    text: str
    cache: bool = False


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolUseRequest:
    tool_use_id: str
    name: str
    input: dict


@dataclass(frozen=True)
class StreamEnd:
    stop_reason: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    model: str = ""
    latency_ms: float = 0.0
    cost_usd: float = 0.0


@dataclass(frozen=True)
class StreamError:
    message: str
    code: str


StreamEvent = TextDelta | ToolUseRequest | StreamEnd | StreamError


# --- Provider protocol ---


class LLMProvider(Protocol):
    async def stream(
        self,
        *,
        system: list[SystemBlock],
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
        model: str | None = None,
    ) -> AsyncIterator[StreamEvent]: ...

    async def complete_json(
        self,
        *,
        system: list[SystemBlock],
        messages: list[dict],
        tool: dict,
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> dict:
        """Non-streaming forced tool-use. Returns the tool's input dict, or {} on
        empty/error — callers degrade gracefully and must never see an exception."""
        ...


# (input_$/M_tokens, output_$/M_tokens) — approximate public pricing
_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (0.80, 4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7": (15.00, 75.00),
}


def _compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    for prefix, (in_rate, out_rate) in _PRICING.items():
        if model.startswith(prefix):
            return round((input_tokens * in_rate + output_tokens * out_rate) / 1_000_000, 6)
    return 0.0


def _render_system(blocks: list[SystemBlock]) -> list[dict]:
    rendered: list[dict] = []
    for block in blocks:
        item: dict = {"type": "text", "text": block.text}
        if block.cache and settings.enable_cache:
            item["cache_control"] = {"type": "ephemeral"}
        rendered.append(item)
    return rendered


# --- Anthropic implementation (the ONLY file that may `import anthropic`) ---


class AnthropicProvider:
    def __init__(self, api_key: str, default_model: str):
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._default_model = default_model

    async def stream(
        self,
        *,
        system: list[SystemBlock],
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 2048,
        model: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        chosen_model = model or self._default_model
        rendered_system = _render_system(system)

        input_tokens = 0
        output_tokens = 0
        cache_read_tokens = 0
        cache_write_tokens = 0
        stop_reason = "end_turn"
        tool_blocks: dict[int, dict] = {}

        kwargs: dict = {
            "model": chosen_model,
            "max_tokens": max_tokens,
            "system": rendered_system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools

        t0 = time.monotonic()
        try:
            async with self._client.messages.stream(**kwargs) as stream:
                async for event in stream:
                    event_type = getattr(event, "type", None)

                    if event_type == "message_start":
                        usage = getattr(event.message, "usage", None)
                        if usage is not None:
                            input_tokens = getattr(usage, "input_tokens", 0) or 0
                            cache_read_tokens = getattr(usage, "cache_read_input_tokens", 0) or 0
                            cache_write_tokens = getattr(usage, "cache_creation_input_tokens", 0) or 0

                    elif event_type == "content_block_start":
                        block = event.content_block
                        if getattr(block, "type", None) == "tool_use":
                            tool_blocks[event.index] = {
                                "tool_use_id": block.id,
                                "name": block.name,
                                "input_json": "",
                            }

                    elif event_type == "content_block_delta":
                        delta = event.delta
                        delta_type = getattr(delta, "type", None)
                        if delta_type == "text_delta":
                            yield TextDelta(text=delta.text)
                        elif delta_type == "input_json_delta":
                            if event.index in tool_blocks:
                                tool_blocks[event.index]["input_json"] += delta.partial_json

                    elif event_type == "content_block_stop":
                        if event.index in tool_blocks:
                            tb = tool_blocks.pop(event.index)
                            try:
                                parsed_input = json.loads(tb["input_json"]) if tb["input_json"] else {}
                            except json.JSONDecodeError:
                                parsed_input = {}
                            yield ToolUseRequest(
                                tool_use_id=tb["tool_use_id"],
                                name=tb["name"],
                                input=parsed_input,
                            )

                    elif event_type == "message_delta":
                        delta = getattr(event, "delta", None)
                        if delta is not None:
                            stop_reason = getattr(delta, "stop_reason", None) or stop_reason
                        usage = getattr(event, "usage", None)
                        if usage is not None:
                            output_tokens = getattr(usage, "output_tokens", 0) or 0

            yield StreamEnd(
                stop_reason=stop_reason,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read_tokens,
                cache_write_tokens=cache_write_tokens,
                model=chosen_model,
                latency_ms=round((time.monotonic() - t0) * 1000, 1),
                cost_usd=_compute_cost(chosen_model, input_tokens, output_tokens),
            )

        except anthropic.APIError as e:
            code = "api_error"
            status = getattr(e, "status_code", None)
            if isinstance(status, int):
                code = f"http_{status}"
            logger.exception("anthropic API error")
            yield StreamError(message=str(e), code=code)
        except Exception as e:
            logger.exception("unexpected provider error")
            yield StreamError(message=f"unexpected: {e!s}", code="unexpected_error")

    async def complete_json(
        self,
        *,
        system: list[SystemBlock],
        messages: list[dict],
        tool: dict,
        model: str | None = None,
        max_tokens: int = 1024,
    ) -> dict:
        """Forced single tool-use, non-streaming. Returns the first tool_use
        block's input as a dict; {} on empty result or API error (never raises)."""
        chosen_model = model or self._default_model
        try:
            resp = await self._client.messages.create(
                model=chosen_model,
                max_tokens=max_tokens,
                system=_render_system(system),
                messages=messages,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool["name"]},
            )
            for block in resp.content:
                if getattr(block, "type", None) == "tool_use":
                    return dict(block.input)
            return {}
        except anthropic.APIError:
            logger.exception("complete_json API error")
            return {}
        except Exception:
            logger.exception("complete_json unexpected error")
            return {}


def get_provider() -> LLMProvider:
    if settings.llm_provider == "anthropic":
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            default_model=settings.main_agent_model,
        )
    raise ValueError(f"unsupported llm_provider: {settings.llm_provider}")


# --- M2 smoke test (run via `python -m backend.agent.llm_provider`) ---


async def _smoke() -> None:
    provider = get_provider()
    system = [SystemBlock(text="You are a helpful assistant. Be very concise.")]
    messages = [{"role": "user", "content": "Count to three. Just say the numbers, comma-separated."}]
    print(f"streaming from {settings.main_agent_model}...")
    async for event in provider.stream(system=system, messages=messages, max_tokens=50):
        if isinstance(event, TextDelta):
            print(event.text, end="", flush=True)
        elif isinstance(event, ToolUseRequest):
            print(f"\n[tool_use {event.name} input={event.input}]")
        elif isinstance(event, StreamEnd):
            print(
                f"\n[done model={event.model} stop={event.stop_reason} "
                f"in={event.input_tokens} out={event.output_tokens} "
                f"cache_r={event.cache_read_tokens} cache_w={event.cache_write_tokens} "
                f"latency={event.latency_ms:.0f}ms cost=${event.cost_usd:.6f}]"
            )
        elif isinstance(event, StreamError):
            print(f"\n[ERROR {event.code}] {event.message}")


if __name__ == "__main__":
    asyncio.run(_smoke())
