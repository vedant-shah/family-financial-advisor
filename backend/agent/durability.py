"""
Startup catch-up + idle sweep — disk-driven session durability.

Solves the silent-forget bug: when the host sleeps/shuts down before the
60-second APScheduler sweep fires, JSONL transcripts survive on disk but no
summary is ever written to memory. This module scans all transcript files at
startup (and on every sweep interval) using real wall-clock timestamps, so
sessions are closed correctly even after an arbitrary sleep/restart gap.

A session is considered "needs processing" when its transcript carries no
terminal post-processing-completed event (the durable status — there is no
sibling marker file) and its last message is stale.

Public API:
    last_message_ts(member, session_id) -> datetime | None
    scan_and_close_stale(now: datetime) -> int
"""
from __future__ import annotations

import json
import logging
from datetime import datetime

from backend.agent.memory_updater import close_session
from backend.agent.sessions import STALE_AFTER_SECONDS, adopt, evict_if_active
from backend.agent.transcripts import is_post_processed, read_turns, transcript_path
from backend.config import settings

logger = logging.getLogger(__name__)


def last_message_ts(member: str, session_id: str) -> datetime | None:
    """Return the tz-aware datetime parsed from the LAST non-empty line's `ts`
    field in the JSONL transcript.  Never raises — returns None on any error
    (missing file, empty file, malformed JSON, missing ts field)."""
    path = transcript_path(member, session_id)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    last_line: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            last_line = stripped

    if last_line is None:
        return None

    try:
        record = json.loads(last_line)
    except json.JSONDecodeError:
        return None

    raw_ts = record.get("ts")
    if not raw_ts:
        return None

    try:
        return datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _stale_open_sessions(now: datetime) -> list[tuple[str, str]]:
    """Walk every member directory under sessions_dir, find JSONL transcripts
    that have no completed post-processing event and whose last message is older
    than STALE_AFTER_SECONDS.  Returns a new list of (member, session_id) pairs."""
    sessions_root = settings.resolve(settings.sessions_dir)
    results: list[tuple[str, str]] = []

    if not sessions_root.is_dir():
        return results

    for member_dir in sessions_root.iterdir():
        if not member_dir.is_dir():
            continue
        member = member_dir.name
        for jsonl_file in member_dir.glob("*.jsonl"):
            session_id = jsonl_file.stem
            if is_post_processed(member, session_id):
                continue
            ts = last_message_ts(member, session_id)
            if ts is None:
                continue
            age = (now - ts).total_seconds()
            if age > STALE_AFTER_SECONDS:
                results.append((member, session_id))

    return results


def _latest_open_session(member: str, now: datetime) -> str | None:
    """The member's most recent transcript (by last-message ts) that is neither
    post-processed nor stale — i.e. the session a returning client should resume.
    None if nothing qualifies."""
    member_dir = settings.resolve(settings.sessions_dir) / member
    if not member_dir.is_dir():
        return None

    best_sid: str | None = None
    best_ts: datetime | None = None
    for jsonl_file in member_dir.glob("*.jsonl"):
        session_id = jsonl_file.stem
        if is_post_processed(member, session_id):
            continue
        ts = last_message_ts(member, session_id)
        if ts is None or (now - ts).total_seconds() > STALE_AFTER_SECONDS:
            continue
        if best_ts is None or ts > best_ts:
            best_ts, best_sid = ts, session_id
    return best_sid


def adopt_recent_session(member: str, now_mono: float, now_wall: datetime) -> str | None:
    """Rehydrate the member's most recent unclosed, non-stale session from its
    transcript into in-memory state and return its id, or None if there's nothing
    to resume. Lets a client recover its conversation after a backend restart
    wiped the in-memory session map. `now_mono` is the monotonic clock used by
    session bookkeeping; `now_wall` is the wall clock used for staleness."""
    sid = _latest_open_session(member, now_wall)
    if sid is None:
        return None
    adopt(member, sid, read_turns(member, sid), now_mono)
    return sid


async def scan_and_close_stale(now: datetime) -> int:
    """Close every stale open session found on disk.

    `now` is injected (tz-aware datetime) for deterministic tests.  Per-session
    failures are isolated: a bad transcript never aborts the rest of the sweep.
    Returns the count of sessions successfully closed."""
    stale = _stale_open_sessions(now)
    closed = 0
    for member, session_id in stale:
        try:
            await close_session(member, session_id)
            evict_if_active(member, session_id)
            closed += 1
        except Exception:
            logger.exception("durability: failed to close %s/%s", member, session_id)
    return closed
