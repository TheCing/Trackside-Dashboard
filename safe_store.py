r"""
safe_store — keep user-generated Team Trials + Stadium data in a location that
survives deleting / re-cloning the project folder.

Problem: until now TT history, stadium observations and the raw native captures
lived inside the project's own `data/` folder. If a user deletes or replaces the
folder (e.g. re-downloading the app) they lose everything.

Fix: store those three artifacts under %LOCALAPPDATA%\Heaven\data instead, and
migrate any existing copies from the old project `data/` folder on first run.

What moves to the safe dir:
  - team_trials_history.jsonl   (Team Trials history)
  - stadium_observations.jsonl  (Stadium / Track & Condition observations)
  - htt/native/*.json           (raw in-game captures from the MOD)

What STAYS in the project folder (read-only seed / caches / per-account):
  - community_seed.jsonl, icons/, race_icons/, heir_capture_*.jsonl,
    auth_config.json, udid.txt, skill_export.json, images/ ...

On non-Windows (or if LOCALAPPDATA is unset) the safe dir resolves back to the
project `data/` folder, so behaviour is unchanged there.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_DATA = HERE / "data"


def _resolve_safe_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / "Heaven" / "data"
    return PROJECT_DATA  # non-Windows / no env → keep old behaviour


SAFE_DATA = _resolve_safe_dir()

# Names handled here (relative to a data dir).
_SAFE_FILES = ("team_trials_history.jsonl", "stadium_observations.jsonl")
_SAFE_TREES = ("htt",)  # htt/native/*.json

_migrated = False


def _merge_jsonl(old: Path, new: Path) -> None:
    """Move `old` → `new`. If `new` already exists, append only the lines from
    `old` that aren't already present (byte-level), then retire `old`."""
    if not old.exists():
        return
    new.parent.mkdir(parents=True, exist_ok=True)
    if not new.exists():
        shutil.move(str(old), str(new))
        return
    seen = {ln.rstrip("\n") for ln in new.read_text(encoding="utf-8").splitlines()}
    add = []
    for ln in old.read_text(encoding="utf-8").splitlines():
        s = ln.rstrip("\n")
        if s and s not in seen:
            add.append(s)
            seen.add(s)
    if add:
        with new.open("a", encoding="utf-8") as f:
            for s in add:
                f.write(s + "\n")
    # keep a recoverable backup instead of hard-deleting
    try:
        old.rename(old.with_name(old.name + ".migrated"))
    except OSError:
        pass


def _merge_tree(old: Path, new: Path) -> None:
    """Move every file under `old` into `new` (skip files that already exist)."""
    if not old.exists():
        return
    for p in old.rglob("*"):
        if not p.is_file():
            continue
        dest = new / p.relative_to(old)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            try:
                shutil.move(str(p), str(dest))
            except OSError:
                pass


def ensure_migrated() -> Path:
    """Idempotent: create the safe dir and move any legacy project-folder data
    into it. Returns the safe data dir. Safe to call from many modules."""
    global _migrated
    if _migrated:
        return SAFE_DATA
    _migrated = True
    try:
        if SAFE_DATA.resolve() == PROJECT_DATA.resolve():
            return SAFE_DATA  # nothing to do (non-Windows / same dir)
        SAFE_DATA.mkdir(parents=True, exist_ok=True)
        for name in _SAFE_FILES:
            _merge_jsonl(PROJECT_DATA / name, SAFE_DATA / name)
        for sub in _SAFE_TREES:
            _merge_tree(PROJECT_DATA / sub, SAFE_DATA / sub)
    except Exception:
        # never let a migration hiccup block startup; worst case we fall back
        # to whatever path the caller uses.
        pass
    return SAFE_DATA


# ── path getters (each triggers the one-time migration) ─────────────────────
def history_path() -> Path:
    return ensure_migrated() / "team_trials_history.jsonl"


def stadium_path() -> Path:
    return ensure_migrated() / "stadium_observations.jsonl"


def native_dir() -> Path:
    return ensure_migrated() / "htt" / "native"
