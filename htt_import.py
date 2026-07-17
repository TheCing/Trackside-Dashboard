"""Import Heaven's native Team Trials captures into the history file.

The in-game Heaven overlay (heaven_overlay.dll) reads the game's own
TeamStadiumResult response object and writes a compact per-trial file to
  data/htt/native/<trial_id>.json
in OUR own compact schema (targeted field reads, no generic object dump):

  {
    "trial_id": "tt_<race_instance_id>",
    "captured_ms": <int>,
    "support_card_bonus": <int>,            # e.g. 1425 == +14.25%
    "races": [
      {
        "race_idx": 0, "round": 1, "distance_type": 1,
        "team_total_score": <int>,
        "race_scenario": "<base64(gzip(...))>",   # raw, parsed here
        "charas": [                                # YOUR team (team_id==1) only
          { "horse_idx": <int>,                    # index in chara_result_array
            "trained_chara_id": <int>, "card_id": <int>, "chara_id": <int>,
            "speed":.., "stamina":.., "power":.., "guts":.., "wiz":..,
            "running_style":.., "finish_order":.., "finish_time":..,
            "display_score":.., "owned_skills": [<skill_id>, ...] }
        ]
      }
    ]
  }

This module parses each race_scenario with tt_scenario.py (our own format RE)
to derive per-horse skill activations and raw scores,
then appends rows to data/team_trials_history.jsonl in the exact schema the
dashboard (skill_planner.py) already consumes. Dedup key:
  trial_id | race_idx | trained_chara_id

No proxy, no certificate, no external capture tool.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import jsonl_util
import master
import safe_store
import tt_scenario

DATA_DIR = Path(__file__).parent / "data"
# Native captures + history live in the safe (AppData) store (migrated on first use).
NATIVE_DIR = safe_store.native_dir()
HISTORY_PATH = safe_store.history_path()


def _row_key(r: dict) -> str:
    """Content-based dedup key. trial_id alone isn't unique (it derives from the
    race course id, which repeats across trials), so we also fold in finish_time
    and display_score — two genuinely different trial runs of the same uma in the
    same round differ there, while a re-import of the same capture is identical."""
    ft = r.get("finish_time")
    ft = round(ft, 3) if isinstance(ft, (int, float)) else ft
    return f"{r.get('trial_id')}|{r.get('race_idx')}|{r.get('trained_chara_id')}|{ft}|{r.get('display_score')}"


def _existing_keys() -> set:
    """Set of content keys already in history."""
    keys: set = set()
    if not HISTORY_PATH.exists():
        return keys
    with open(HISTORY_PATH, encoding="utf-8") as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            keys.add(_row_key(r))
    return keys


def _rows_for_trial(trial: dict) -> list[dict]:
    """Turn one native per-trial file into history rows (one per uma per race)."""
    trial_id = trial.get("trial_id") or ""
    support_bonus_raw = trial.get("support_card_bonus") or 0
    support_bonus_pct = support_bonus_raw / 100.0

    rows: list[dict] = []
    for race in trial.get("races") or []:
        scen = race.get("race_scenario")
        if not scen:
            continue
        try:
            parsed = tt_scenario.parse(scen)
        except Exception as e:
            print(f"  ! race_scenario parse failed (trial {trial_id}, "
                  f"race {race.get('race_idx')}): {e}")
            continue

        per_horse_acts = tt_scenario.activations_per_horse(parsed)
        per_horse_scores = tt_scenario.scores_per_horse(parsed)
        horse_results = parsed.get("horse_results") or []

        team_raw_sum = sum(per_horse_scores.values())
        team_total = race.get("team_total_score") or 0
        race_multiplier = (team_total / team_raw_sum) if team_raw_sum else 1.0

        race_idx = race.get("race_idx")
        distance_type = race.get("distance_type")

        for cr in race.get("charas") or []:
            hidx = cr.get("horse_idx")
            tcid = cr.get("trained_chara_id")
            owned = [s for s in (cr.get("owned_skills") or []) if s]
            owned_set = set(owned)

            activated = per_horse_acts.get(hidx, []) if hidx is not None else []
            activated_in_pool = [s for s in activated if s in owned_set]
            activated_extra = [s for s in activated if s not in owned_set]

            # Canonical per-horse results from the scenario (seconds, etc.) — keeps
            # the schema the dashboard already consumes. Fall back to the values
            # the native side read directly if the scenario lacks them.
            hr = horse_results[hidx] if (hidx is not None and hidx < len(horse_results)) else {}
            finish_order = hr.get("finish_order", cr.get("finish_order"))
            finish_time = hr.get("finish_time", cr.get("finish_time"))
            running_style = hr.get("running_style", cr.get("running_style"))

            card_id = cr.get("card_id")
            rows.append({
                "trial_id":          trial_id,
                "race_idx":          race_idx,
                "distance_type":     distance_type,
                "trained_chara_id":  tcid,
                "chara_id":          card_id,
                "chara_name":        master.chara_name_by_card_id(card_id) if card_id else "?",
                "stats": {
                    "speed":   cr.get("speed"),
                    "stamina": cr.get("stamina"),
                    "power":   cr.get("power"),
                    "guts":    cr.get("guts"),
                    "wiz":     cr.get("wiz"),
                },
                "finish_order":      finish_order,
                "finish_time":       finish_time,
                "running_style":     running_style,
                "raw_score":         per_horse_scores.get(hidx, 0) if hidx is not None else 0,
                "display_score":     cr.get("display_score", 0),
                "race_multiplier":   round(race_multiplier, 4),
                "team_total_score":  team_total,
                "support_bonus_raw": support_bonus_raw,
                "support_bonus_pct": support_bonus_pct,
                "owned_skills_n":    len(owned),
                "owned_skills":      owned,
                "activated_skills":  activated_in_pool,
                "activated_extra":   activated_extra,
                "activation_ratio":  (len(activated_in_pool) / len(owned)) if owned else 0,
            })
    return rows


def import_dir(target: "Path | str | None" = None) -> dict:
    """Scan the native capture dir, append any new rows to history (deduped).

    `target` overrides the source dir if given. Otherwise we scan this
    dashboard's own `data/htt/native/` plus the MOD's fallback location
    (`%LOCALAPPDATA%/Heaven/data/htt/native/`) — the latter is where the MOD
    writes if it ran before this dashboard published its path. Returns a small
    summary dict for the Flask endpoint.
    """
    if target:
        sources = [Path(target)]
    else:
        sources = [NATIVE_DIR]
        appdata = os.environ.get("LOCALAPPDATA")
        if appdata:
            fallback = Path(appdata) / "Heaven" / "data" / "htt" / "native"
            if fallback.resolve() != NATIVE_DIR.resolve():
                sources.append(fallback)

    files: list[Path] = []
    for s in sources:
        if s.exists():
            files.extend(sorted(s.glob("*.json")))

    if not files:
        looked = " | ".join(str(s) for s in sources)
        return {"ok": False, "error": "no native captures found — enable "
                "'Team Trials' capture in the in-game overlay and play a match. "
                f"(looked in: {looked})"}

    existing = _existing_keys()
    new_rows: list[dict] = []
    trials_seen = 0
    imported = 0      # trials that contributed at least one new row
    skipped = 0       # trials already fully in history
    parse_errors = 0

    for fp in files:
        try:
            trial = json.loads(fp.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  ! could not read {fp.name}: {e}")
            parse_errors += 1
            continue
        trials_seen += 1
        trial_new = 0
        for row in _rows_for_trial(trial):
            key = _row_key(row)
            if key in existing:
                continue
            existing.add(key)
            new_rows.append(row)
            trial_new += 1
        if trial_new:
            imported += 1
        else:
            skipped += 1

    if new_rows:
        jsonl_util.append_jsonl(HISTORY_PATH, new_rows, json_kwargs={"default": str})

    # ── Stadium / Track & Condition ────────────────────────────────────────
    # Native captures now carry each round's start fields (race_instance_id,
    # weather, ground_condition, season, random_seed) + my umas' frame_order,
    # so we can rebuild the `race_start_params_array` shape stadium_tracker
    # expects and re-populate observations straight from the overlay's capture.
    # Old captures (pre-DLL-update) lack these fields → they're skipped.
    stadium_saved = 0
    try:
        import stadium_tracker
        stad_payloads = []
        for fp in files:
            try:
                trial = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            rounds = []
            for race in trial.get("races") or []:
                if race.get("race_instance_id") is None:
                    continue  # legacy capture without stadium fields
                rounds.append({
                    "round":              race.get("round"),
                    "race_instance_id":   race.get("race_instance_id"),
                    "weather":            race.get("weather"),
                    "ground_condition":   race.get("ground_condition"),
                    "season":             race.get("season"),
                    "random_seed":        race.get("random_seed"),
                    # native `charas` are already my team only → all are my gates.
                    "race_horse_data_array": [
                        {"trained_chara_id": c.get("trained_chara_id"),
                         "chara_id":         c.get("chara_id"),
                         "card_id":          c.get("card_id"),
                         "running_style":    c.get("running_style"),
                         "frame_order":      c.get("frame_order"),
                         "viewer_id":        1}
                        for c in race.get("charas") or []
                    ],
                })
            if rounds:
                stad_payloads.append({
                    "endpoint": "team_stadium/start",
                    "payload": {"race_start_params_array": rounds},
                })
        if stad_payloads:
            stadium_saved = stadium_tracker.ingest_payloads(stad_payloads, my_viewer_id=1)
    except Exception as e:
        print(f"  ! stadium ingest failed: {e}")

    # Keys `imported` / `rows` / `skipped` are what the dashboard frontend reads;
    # the rest are kept for the CLI / debugging.
    return {
        "ok": True,
        "imported": imported,
        "rows": len(new_rows),
        "stadium": stadium_saved,
        "skipped": skipped,
        "files": len(files),
        "trials": trials_seen,
        "rows_added": len(new_rows),
        "parse_errors": parse_errors,
    }


if __name__ == "__main__":
    import sys
    tgt = sys.argv[1] if len(sys.argv) > 1 else None
    print(import_dir(tgt))
