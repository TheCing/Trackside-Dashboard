# Heaven

[![Discord](https://img.shields.io/badge/Discord-Join%20the%20server-5865F2?logo=discord&logoColor=white)](https://discord.com/invite/SpCGcXMeFt)

Local dashboard for Uma Musume: **breeding optimizer**, **Team Trials analyzer**,
**skill planner** and **stadium tracker**. Runs as a small web
app on your own machine.

> **The dashboard is passive — it does not inject code, hook the game, modify
> game memory, or send anything to the game server.** It only reads files you
> give it. Everything runs locally at **http://127.0.0.1:1620**.

### Where the data comes from

| Data | How it's read |
|------|---------------|
| **Inventory / breeding** | A `data.json` you import — from the Trackside overlay's veterans export, or [UmaExtractor](https://github.com/xancia/UmaExtractor) |
| **Team Trials** | Imported from the in-game Trackside overlay's own capture |

> This fork removed the **Frida** (in-game credential capture) and **mitmproxy**
> (HTTPS interception) paths that upstream uses. Both existed to reach data the
> overlay now provides directly, and neither is worth the risk: Frida attaches a
> debugger to the game and needs your Steam password, and mitmproxy re-routes
> **all** of your machine's traffic through a local proxy. Nothing here injects,
> hooks, or asks for credentials. See [FORK.md](FORK.md).

---

## Requirements

- **Python 3.10+** (tested on 3.12 / 3.13)
- **Windows**
- Uma Musume (Steam/Global) + the Trackside overlay

## Quick Start

```bash
git clone https://github.com/TheCing/Heaven.git
cd Heaven
python -m pip install -r requirements.txt
.\start.bat
```

Opens at **http://127.0.0.1:1620**.

> Use `python -m pip` (not bare `pip`) so the dependencies install into the
> **same** Python that runs the app. On a PC with more than one Python, a bare
> `pip` can install into a different environment.

---

## Features (tabs)

### Inventory
Your full character/factor inventory. Cards show the complete factor breakdown
(blue stats, pink aptitudes, green uniques, white skills/races) with star counts,
proc percentages, and your own contribution highlighted.
- Filter by name / note / tag / owner; source toggle (All / Yours / Friends).
- Sort by Affinity, G1 wins, white count, score, or newest.
- **Target picker** — pick any uma as breeding target to see exact individual
  affinity on every card.
- Inheritance-factor filters (uma.moe-style), progressive loading, quick "assign
  as Parent 1/2" actions.

### Breed Optimizer
Pick a target build (running style + distance) and your wanted skills; the
optimizer ranks the best parent pairs from your inventory.
- Uses an **expected-proc model**: the real probability of each spark proccing
  across all 6 tree entities (parents + 4 grandparents), each with its own
  individual affinity from the exact in-game formula (chara relation + winning
  saddle bonus + relation level).
- **Pair detail** — visual lineage tree with portraits + affinity badges, spark
  proc odds `P(>=1)` over a full run with per-source breakdown, and the combined
  inherited factors.
- A persistent **breeding tray** lets you assign parents while browsing.

### Team Trials
Every match you've played: your team vs the opponent, per-race results, skill
activations and win/loss verdicts.
- **Race Analysis** — compact per-uma rows: AVG score, CV% (consistency), BEST /
  WORST, ACT% (skill activation), a sparkline trend, and a verdict pill
  (GOAT / STRONG / SOLID / WEAK / BENCH). Click to expand a score heatmap, gap to
  top, stddev and full skill breakdown.
- **Re-train Comparison** — trained the same character more than once? Any uma with
  multiple versions gets a dropdown comparing them side by side (average, trimmed
  average, consistency, best/worst, win rate, skill activation and a per-distance
  breakdown) so you can see whether a re-train actually improved — older versions
  are kept for comparison instead of being hidden.
- The page **refreshes on its own** as new matches come in — no manual reload.

### Skill Planner
For a given (character, distance, running style), shows **how often each skill
actually fires** in your captured matches — so you pick skills that consistently
activate instead of ones that look good on paper but never trigger.

### Skill Lookup
Type any skill name and see **how often it actually activates** across all your
data — your Team Trials plus every race you've run (career, champions, room
matches). Filter the activation rate by **distance** and **running style**, with a
per-uma breakdown of who runs it and how reliably it fires.
- **Community pool** — the dashboard ships with a shared activation dataset and
  merges in any skill data you (or others) import, so the numbers get more
  reliable over time. Everything is **deduplicated** — the same race never counts
  twice.
- **Export / Import / Sync** — share your skill data or pull in someone else's;
  imports only ever *add* to your pool, never replace it.

### Track & Condition
Stadium conditions across your captured matches: top tracks, starting-gate
distribution, ground/surface/weather/season breakdowns and a full rounds table.

---

## Setup

### 1) Import your account (Inventory / Breeding)

Open **http://127.0.0.1:1620** → the setup dialog asks for a `data.json`. Get one
either way:

**From Trackside (recommended)** — in the overlay, open **Plugins → Export
veterans (data.json)**. It writes `trackside_umas/data.json` next to the game.

**From UmaExtractor** — go to **Enhance → List** (Veteran List) in-game, run
[UmaExtractor](https://github.com/xancia/UmaExtractor), and it writes `data.json`.

Either way, click **Import data.json** and pick the file.

> Both sources read only *your own* umas, so friends' borrowable parents aren't
> available and the Breed Optimizer's rental pool will be empty. Upstream filled
> that gap with the Frida path; this fork doesn't, on purpose.

### 2) Team Trials data

Run the Trackside overlay, enable its **Team Trials** capture, and play a match.
Then click **Import in-game** on the Team Trials tab — it reads the overlay's
per-trial captures and merges them into your history. No proxy, no certificate.

---

## Backups & importing data

Every import is **additive and deduplicated** — it only ever *adds* new data and
never overwrites or deletes what you already have, and it always takes a backup
first.

### Import & merge (Team Trials tab)
Pulls extra data into your dashboard. It auto-detects and accepts:
- a **Heaven export** bundle (from the *Export data* button),
- raw **horseACT / Team Trials** dumps,
- raw **UmaTTAnalyzer** data files (`team_trials_history.jsonl`,
  `stadium_observations.jsonl`).

You can select several files at once. Everything is deduplicated, so re-importing
the same data never doubles anything.

### Migrating from UmaTTAnalyzer
Moving over from UmaTTAnalyzer keeps **all** your history. Just take the files in
its `data/` folder (`team_trials_history.jsonl` and `stadium_observations.jsonl`)
and load them with **Import & merge** — your Team Trials, Track & Condition and
skill activation all come across in one step. Skill-only files can also go into
**Skill Lookup → Import data**, where they enrich your activation numbers without
touching your scores. Importing only *reads* those files; your original
UmaTTAnalyzer data is never modified.

### Backups
The **Backups** menu (top-left of the header) keeps dated restore points. A backup
is taken automatically before every import, and you can also make one any time
with **Backup now**. Pick any snapshot to roll back to it in one click — and since
your current data is snapshotted first, even a restore is undoable.

---

## Updating

```bash
cd Heaven
git pull
python -m pip install -r requirements.txt
.\start.bat
```

Your data (`data/` folder, notes, cached images) is local-only and untouched by
updates. Character portraits/icons are cached locally on first view (downloaded
from gametora on demand) — they are not redistributed in the repo.
