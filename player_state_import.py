"""Import the overlay's player-state captures into player_state.jsonl.

The "Your status" panel reads `player_state.jsonl`, whose rows come from
`player_state.extract_state({endpoint: payload})` — a handful of fields spread across
four Team Trials responses (index / start / decide_frame_order / all_race_end).

Upstream produced those rows in `tt_analyze.py`, fed by the mitmproxy capture, which was
the only thing recording each response separately. Removing the proxy took the writer
with it and left the panel permanently empty. The Trackside overlay now captures the
same four responses off the wire and writes one JSON per trial into
`<data>/player_state/`, keyed by endpoint — this module turns those into rows.

Dedup: by the trial's identity where we can see it (`all_race_end` is emitted once per
trial), else by the file's own timestamp, so re-importing never doubles a trial up.
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonl_util
import player_state
import safe_store

STATE_PATH = safe_store.player_state_path()


def _row_key(row: dict) -> str:
    """Identity of a captured trial. Prefer real content over the file name: the same
    trial re-imported must collapse, but two genuine trials must not."""
    parts = [row.get("viewer_id"), row.get("trial_final_score"),
             row.get("trial_mvp_chara_id"), row.get("opponent_viewer_id")]
    if any(p is not None for p in parts):
        return "|".join(str(p) for p in parts)
    return f"ts:{row.get('ts')}"


def _existing_keys() -> set:
    keys: set = set()
    if not STATE_PATH.exists():
        return keys
    with open(STATE_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                keys.add(_row_key(json.loads(line)))
            except Exception:
                continue
    return keys


def import_dir(target: "Path | str | None" = None) -> dict:
    """Scan the capture folder and append any new player-state rows (deduped)."""
    src = Path(target) if target else safe_store.player_state_dir()
    if not src.exists():
        return {"ok": True, "imported": 0, "skipped": 0,
                "note": f"no player-state captures yet ({src})"}

    files = sorted(src.glob("state_*.json"))
    if not files:
        return {"ok": True, "imported": 0, "skipped": 0,
                "note": "no player-state captures yet — play a Team Trial with the overlay running"}

    existing = _existing_keys()
    new_rows: list[dict] = []
    imported = skipped = errors = 0

    for fp in files:
        try:
            by_ep = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! could not read {fp.name}: {e}")
            errors += 1
            continue
        if not isinstance(by_ep, dict) or not by_ep:
            errors += 1
            continue
        row = player_state.extract_state(by_ep)
        # Nothing but the timestamp resolved → the capture is useless, don't persist it.
        if not any(v is not None for k, v in row.items() if k != "ts"):
            errors += 1
            continue
        key = _row_key(row)
        if key in existing:
            skipped += 1
            continue
        existing.add(key)
        new_rows.append(row)
        imported += 1

    if new_rows:
        # Oldest first, so the panel's history/trends read in order.
        new_rows.sort(key=lambda r: r.get("ts") or 0)
        jsonl_util.append_jsonl(STATE_PATH, new_rows, json_kwargs={"default": str})

    return {"ok": True, "imported": imported, "skipped": skipped,
            "errors": errors, "files": len(files)}
