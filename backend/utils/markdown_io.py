import json
import logging
import os
import tempfile
from pathlib import Path

import frontmatter

logger = logging.getLogger(__name__)


def read_markdown(path: Path) -> str:
    return Path(path).read_text(encoding="utf-8")


def read_markdown_or_none(path: Path) -> str | None:
    try:
        return read_markdown(path)
    except FileNotFoundError:
        return None


def strip_frontmatter(content: str) -> str:
    post = frontmatter.loads(content)
    return post.content


def list_member_dirs(memory_root: Path) -> list[str]:
    members_dir = Path(memory_root) / "members"
    if not members_dir.exists():
        return []
    return [d.name for d in sorted(members_dir.iterdir()) if d.is_dir()]


# --- write tier (not called on Day 1, but shipped now for forward compatibility) ---

def write_markdown_atomic(path: Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def append_markdown(path: Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)


def append_jsonl(path: Path, record: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def touch_marker(path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def marker_exists(path: Path) -> bool:
    return Path(path).exists()
