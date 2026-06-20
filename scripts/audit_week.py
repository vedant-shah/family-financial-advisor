#!/usr/bin/env python3
"""Weekly conversation audit renderer.

Reads the session transcripts the pipeline writes and renders the last N days
into one readable view. It surfaces the observability fields (intent, context
level, loaded files, tool results, model usage) and FLAGS any turn that errored
or had a failed tool call — the raw material for the weekly behavior review.

Usage (from the repo root, so `backend` is importable):
    python -m scripts.audit_week [days]      # default 7

`render_week` is a pure function (stdlib only) so it can be tested without the
app; the `backend` import lives inside main().
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_FLAG = "!! FLAG"


def _parse_ts(ts: str) -> datetime | None:
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def load_records(path: Path) -> list[dict]:
    """All JSON objects in a transcript, skipping blanks and torn/malformed lines."""
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            records.append(rec)
    return records


def _last_activity(records: list[dict]) -> datetime | None:
    stamps = [_parse_ts(r["ts"]) for r in records if r.get("ts")]
    stamps = [s for s in stamps if s is not None]
    return max(stamps) if stamps else None


def _clip(text: str, n: int) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= n else text[: n - 3] + "..."


def _render_turn(rec: dict) -> tuple[str, bool]:
    tools = rec.get("tool_calls") or []
    failed_tool = any(not t.get("ok", True) for t in tools)
    errored = bool(rec.get("error"))
    flagged = failed_tool or errored

    ts = _parse_ts(rec.get("ts", ""))
    when = ts.strftime("%Y-%m-%d %H:%M") if ts else "?"

    lines = []
    head = (
        f"  [{rec.get('turn_id', '?')} | {when}] "
        f"intent={rec.get('intent', '?')} level={rec.get('context_level', '?')}"
    )
    if flagged:
        head += f"    {_FLAG}"
    lines.append(head)
    lines.append(f"    you      : {_clip(rec.get('user_msg', ''), 200)}")
    lines.append(f"    advisor  : {_clip(rec.get('assistant_msg', ''), 400)}")

    loaded = rec.get("loaded_context") or []
    if loaded:
        lines.append(f"    loaded   : {', '.join(loaded)}")

    for t in tools:
        ok = "ok" if t.get("ok", True) else "FAIL"
        lines.append(
            f"    tool     : {t.get('name', '?')}({t.get('input', {})}) "
            f"-> {ok}: {_clip(t.get('result', ''), 160)}"
        )

    lines.append(
        f"    usage    : model={rec.get('model', '') or '-'} "
        f"in={rec.get('input_tokens', 0)} out={rec.get('output_tokens', 0)} "
        f"latency={rec.get('latency_ms', 0):.0f}ms stop={rec.get('stop_reason', '') or '-'}"
    )
    if errored:
        lines.append(f"    error    : {rec.get('error')}")
    return "\n".join(lines), flagged


def render_week(sessions_dir: Path, *, days: int = 7, now: datetime | None = None) -> str:
    """Render every session with activity within the last `days` into one report."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)

    body: list[str] = []
    sessions_total = turns_total = flagged_total = 0

    member_dirs = (
        sorted(p for p in sessions_dir.iterdir() if p.is_dir()) if sessions_dir.exists() else []
    )
    for member_dir in member_dirs:
        for path in sorted(member_dir.glob("*.jsonl")):
            records = load_records(path)
            last = _last_activity(records)
            if last is None or last < cutoff:
                continue
            sessions_total += 1
            body.append("")
            body.append(
                f"=== {member_dir.name} | session {path.stem[:8]} | "
                f"last {last.strftime('%Y-%m-%d %H:%M')} ==="
            )
            for rec in [r for r in records if r.get("turn_id")]:  # skip terminal markers
                turns_total += 1
                text, flagged = _render_turn(rec)
                flagged_total += 1 if flagged else 0
                body.append(text)

    session_word = "session" if sessions_total == 1 else "sessions"
    header = (
        f"Audit -- last {days} days (as of {now.strftime('%Y-%m-%d %H:%M UTC')})\n"
        f"{sessions_total} {session_word} | {turns_total} turns | {flagged_total} flagged"
    )
    if not body:
        return header + "\n(no sessions in window)"
    return header + "\n" + "\n".join(body)


def main() -> None:
    from backend.config import settings

    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    sessions_dir = settings.resolve(settings.sessions_dir)
    print(render_week(sessions_dir, days=days))


if __name__ == "__main__":
    main()
