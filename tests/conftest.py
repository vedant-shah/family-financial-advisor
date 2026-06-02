"""
Shared test fixtures.

`asyncio_mode = "auto"` (pyproject) means async tests need no decorator.
No test touches the network or the real `memory/` tree: a FakeProvider stands
in for the model, and `tmp_memory` repoints settings.memory_dir/sessions_dir at
a tmp_path.
"""
from __future__ import annotations

from typing import AsyncIterator

import pytest

from backend.config import settings


class FakeProvider:
    """In-memory stand-in for LLMProvider. `complete_json` returns a canned dict
    and records call count; `stream` is a no-op to satisfy the Protocol."""

    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload if payload is not None else {}
        self.calls = 0
        self.last_kwargs: dict | None = None

    async def stream(self, **kwargs) -> AsyncIterator:  # pragma: no cover - unused here
        if False:
            yield None

    async def complete_json(self, **kwargs) -> dict:
        self.calls += 1
        self.last_kwargs = kwargs
        return self.payload


@pytest.fixture
def fake_provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def tmp_memory(tmp_path, monkeypatch):
    """Point memory + sessions dirs at tmp_path and create the standard member
    tree (vedant, mom) plus family/. Returns the memory root Path."""
    memory_dir = tmp_path / "memory"
    sessions_dir = tmp_path / "sessions"
    for member in ("vedant", "mom"):
        (memory_dir / "members" / member).mkdir(parents=True)
    (memory_dir / "family").mkdir(parents=True)
    sessions_dir.mkdir(parents=True)
    monkeypatch.setattr(settings, "memory_dir", memory_dir)
    monkeypatch.setattr(settings, "sessions_dir", sessions_dir)
    return memory_dir
