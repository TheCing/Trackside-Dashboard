r"""
safe_store — keep user-generated Team Trials + Stadium data in a location that
survives deleting / re-cloning the project folder.

Problem: until now TT history, stadium observations and the raw native captures
lived inside the project's own `data/` folder. If a user deletes or replaces the
folder (e.g. re-downloading the app) they lose everything.

Fix: store those three artifacts under %LOCALAPPDATA%\Trackside\data instead, and
migrate any existing copies from the old project `data/` folder on first run.

`Trackside` is the shared namespace for the Trackside family — the overlay writes
its in-game captures to the same place (see paths.rs). It used to be `Heaven`;
_migrate_appdata_name() moves an old folder across on first run.

What moves to the safe dir:
  - team_trials_history.jsonl   (Team Trials history)
  - stadium_observations.jsonl  (Stadium / Track & Condition observations)
  - htt/native/*.json           (raw in-game captures from the MOD)
  - breeding/capture_*.jsonl    (your umas)
  - notes.json                  (your per-uma notes / tags)

Breeding traces go into a dedicated `breeding/` subfolder (NOT the data root):
breeding.find_trace() just picks the newest *.jsonl with no name filter, so mixing
them with team_trials_history.jsonl would make it grab the wrong file. (That same
no-name-filter glob is why the legacy `heir_capture_*.jsonl` files still load.)

What STAYS in the project folder (read-only seed / caches / per-account):
  - community_seed.jsonl, icons/, race_icons/, skill_export.json,
    auth_config.json, udid.txt, images/ ...

On non-Windows (or if LOCALAPPDATA is unset) the safe dir resolves back to the
project `data/` folder, so behaviour is unchanged there.
"""
from __future__ import annotations

import json
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_DATA = HERE / "data"


APPDATA_NAME = "Trackside"
APPDATA_NAME_LEGACY = "Heaven"


def _resolve_safe_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if base:
        return Path(base) / APPDATA_NAME / "data"
    return PROJECT_DATA  # non-Windows / no env → keep old behaviour


SAFE_DATA = _resolve_safe_dir()

# Names handled here (relative to a data dir).
_SAFE_FILES = ("team_trials_history.jsonl", "stadium_observations.jsonl",
               "player_state.jsonl")
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


def _move_glob(src_dir: Path, pattern: str, dest_dir: Path) -> None:
    """Move every file in src_dir matching `pattern` into dest_dir (skip dups)."""
    if not src_dir.exists():
        return
    for p in sorted(src_dir.glob(pattern)):
        if not p.is_file():
            continue
        dest = dest_dir / p.name
        if not dest.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(p), str(dest))
            except OSError:
                pass


def _move_file(old: Path, new: Path) -> None:
    """Move a single file old → new. If new exists, retire old as .migrated."""
    if not old.exists():
        return
    if not new.exists():
        new.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.move(str(old), str(new))
        except OSError:
            pass
    else:
        try:
            old.rename(old.with_name(old.name + ".migrated"))
        except OSError:
            pass


def _migrate_appdata_name() -> None:
    """Move %LOCALAPPDATA%\\Heaven → %LOCALAPPDATA%\\Trackside (the pre-rename name).

    Runs before anything reads SAFE_DATA. Only acts when the old folder exists and
    the new one doesn't — so it can't clobber a live install, and it's a no-op on
    every run after the first.
    """
    base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
    if not base:
        return
    old = Path(base) / APPDATA_NAME_LEGACY
    new = Path(base) / APPDATA_NAME
    if old.is_dir() and not new.exists():
        try:
            old.rename(new)
        except Exception:
            pass  # cross-device or locked → fall through, nothing lost


def ensure_migrated() -> Path:
    """Idempotent: create the safe dir and move any legacy project-folder data
    into it. Returns the safe data dir. Safe to call from many modules."""
    global _migrated
    if _migrated:
        return SAFE_DATA
    _migrated = True
    try:
        _migrate_appdata_name()
        if SAFE_DATA.resolve() == PROJECT_DATA.resolve():
            return SAFE_DATA  # nothing to do (non-Windows / same dir)
        SAFE_DATA.mkdir(parents=True, exist_ok=True)
        for name in _SAFE_FILES:
            _merge_jsonl(PROJECT_DATA / name, SAFE_DATA / name)
        for sub in _SAFE_TREES:
            _merge_tree(PROJECT_DATA / sub, SAFE_DATA / sub)
        # breeding traces (your umas + friends) → dedicated breeding/ subfolder
        # legacy prefix — pre-rename traces still live under the old name
        _move_glob(PROJECT_DATA, "heir_capture_*.jsonl", SAFE_DATA / "breeding")
        _move_glob(PROJECT_DATA, "capture_*.jsonl", SAFE_DATA / "breeding")
        # per-uma notes / tags (lives in the project ROOT, not data/)
        _move_file(HERE / "notes.json", SAFE_DATA / "notes.json")
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


def breeding_dir() -> Path:
    """Folder holding the breeding traces (capture_*.jsonl). Created on demand."""
    d = ensure_migrated() / "breeding"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_trace(load_res, pre_res):
    """Write a breeding trace (the shape breeding.py reads) into the safe store.

    Lives here, next to breeding_dir(), because it's a store concern. It used to
    sit in fetch.py alongside the Frida/Steam capture; that module is gone, but
    the data.json import path still needs this.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = breeding_dir() / f"capture_{ts}.jsonl"

    def _default(o):
        if isinstance(o, bytes):
            return o.hex()
        return str(o)

    with open(out, "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "ts": time.time(), "direction": "RES",
            "endpoint": "load/index", "data": load_res,
        }, ensure_ascii=False, default=_default) + "\n")
        f.write(json.dumps({
            "ts": time.time(), "direction": "RES",
            "endpoint": "pre_single_mode/index", "data": pre_res,
        }, ensure_ascii=False, default=_default) + "\n")
    return out


def notes_path() -> Path:
    return ensure_migrated() / "notes.json"


def player_state_path() -> Path:
    return ensure_migrated() / "player_state.jsonl"
