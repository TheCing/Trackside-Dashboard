"""Crash-safe JSONL append.

The various history/observation files are append-only JSONL. Writing them
line-by-line (`for r: f.write(json+"\\n")`) risks a half-written line if the
process dies mid-loop, and never flushes to disk. `append_jsonl` instead builds
the whole batch as ONE string, writes it in a single call, and fsyncs — so a
batch either lands fully or not at all (no truncated JSON lines), and is durable.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable


def append_jsonl(path, rows: Iterable[dict], *, json_kwargs: dict | None = None) -> int:
    """Append `rows` to the JSONL file at `path` as a single durable write.

    Returns the number of rows written. No-op (returns 0) if `rows` is empty.
    `json_kwargs` is passed to json.dumps (defaults to ensure_ascii=False).
    """
    rows = list(rows)
    if not rows:
        return 0
    jk = {"ensure_ascii": False}
    if json_kwargs:
        jk.update(json_kwargs)
    block = "".join(json.dumps(r, **jk) + "\n" for r in rows)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(block)
        f.flush()
        os.fsync(f.fileno())
    return len(rows)
