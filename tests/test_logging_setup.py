"""Durable, rotating file logging so a week of runtime logs + errors survive
process restarts (gap #3). Console output is preserved, and configure_logging is
idempotent so repeated calls (uvicorn reload, tests) don't pile up handlers."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

import pytest

from backend.logging_setup import configure_logging


@pytest.fixture
def restore_root_logging():
    # configure_logging mutates the root logger; snapshot and restore so this
    # doesn't bleed into other tests or pytest's own capture.
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_level = root.level
    yield
    for h in list(root.handlers):
        if h not in saved_handlers:
            root.removeHandler(h)
    root.setLevel(saved_level)


def _managed_file_handlers():
    return [h for h in logging.getLogger().handlers if isinstance(h, RotatingFileHandler)]


def test_writes_to_durable_file(tmp_path, restore_root_logging):
    log_file = configure_logging(log_dir=tmp_path)
    logging.getLogger("ffa.test").info("audit-marker-123")
    for h in logging.getLogger().handlers:
        h.flush()

    assert log_file == tmp_path / "app.log"
    assert log_file.exists()
    assert "audit-marker-123" in log_file.read_text()


def test_idempotent_no_handler_pileup(tmp_path, restore_root_logging):
    configure_logging(log_dir=tmp_path)
    configure_logging(log_dir=tmp_path)
    configure_logging(log_dir=tmp_path)
    # Repeated calls must not stack file handlers (which would duplicate lines).
    assert len(_managed_file_handlers()) == 1
