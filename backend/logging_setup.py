"""Application logging setup: console + durable rotating file.

Runtime logs (classifier decisions, latencies, warnings, exceptions) used to go
to stdout only — ephemeral, gone on restart. This adds a RotatingFileHandler so
a week of logs survives for the weekly audit, while keeping console output.

Idempotent: a re-call removes the handlers it previously installed instead of
stacking new ones (matters under uvicorn reload and in tests). Handlers we own
are tagged with a sentinel so we never touch handlers added by anything else.
"""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.config import settings

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
_MANAGED = "_ffa_managed"  # sentinel marking handlers this module installed


def configure_logging(*, log_dir: Path | None = None, level: int = logging.INFO) -> Path:
    """Configure root logging with a console handler and a durable rotating file
    handler. Returns the path to the active log file."""
    target_dir = Path(log_dir) if log_dir is not None else settings.resolve(settings.log_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "app.log"

    root = logging.getLogger()
    root.setLevel(level)

    # Drop handlers from a prior call so reloads/tests don't pile up (and so we
    # don't duplicate every log line). Only ones we tagged are removed.
    for handler in [h for h in root.handlers if getattr(h, _MANAGED, False)]:
        root.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    setattr(console, _MANAGED, True)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    setattr(file_handler, _MANAGED, True)
    root.addHandler(file_handler)

    # Keep the HTTP client quiet (preserves prior basicConfig behavior).
    logging.getLogger("httpx").setLevel(logging.WARNING)

    return log_file
