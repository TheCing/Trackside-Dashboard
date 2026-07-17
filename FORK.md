# Fork notes

This is a fork of [Nighty3333/Heaven](https://github.com/Nighty3333/Heaven), the
companion dashboard to that project's overlay. It exists to pair with
[Trackside](https://github.com/TheCing/Trackside) (an MIT fork of that overlay).

## Renamed to Trackside Dashboard

Upstream called this "Heaven" — the same name as the in-game overlay — while the
setup dialog called it "Heir" and the breeding engine lived in `heir.py`. Three
names for two programs. Here the overlay is **Trackside** and this is the
**Trackside Dashboard**; "Heir" is retired (`heir.py` → `breeding.py`).

What that touched on disk:

| Was | Now | Notes |
|-----|-----|-------|
| `%LOCALAPPDATA%\Heaven\` | `%LOCALAPPDATA%\Trackside\` | shared with the overlay; `safe_store._migrate_appdata_name()` renames an old folder on first run, and refuses if both exist |
| `<game>\heaven-races\` | `<game>\trackside-races\` | the overlay already wrote `trackside-races`, so this was **broken** before the rename |
| `heir_capture_*.jsonl` | `capture_*.jsonl` | old files still load — `find_trace()` globs `*.jsonl` with no name filter |
| `HEAVEN_RACES_DIR` | `TRACKSIDE_RACES_DIR` | now only an override; the game dir is auto-detected from Steam's `libraryfolders.vdf` |
| `heir_ui_state_v1` | `trackside_ui_state_v1` | localStorage key; resets saved UI state once |

`%LOCALAPPDATA%\Trackside\datadir.txt` is a **two-sided handshake**: this app
writes it (`server._publish_data_dir`), the overlay reads it (`paths.rs`). If you
change the folder name, change both — `safe_store.APPDATA_NAME` and
`paths.rs::resolve_appdata_root()`.

### The Windows Store Python trap

If you run this under the **Store** Python (`WindowsApps\python.exe` — the default
`python` on a stock Windows box), Windows silently redirects every
`%LOCALAPPDATA%` write into a per-package sandbox:

```
%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.<ver>_<hash>\LocalCache\Local\
```

So `datadir.txt` and all your data land *there*, while the overlay — a native
process with no redirection — looks at the real `%LOCALAPPDATA%`. The two never
meet and **Import in-game silently finds nothing**. Upstream has this bug today.

Python can't escape its own sandbox, so the fix lives in the overlay:
`paths.rs::resolve_appdata_root()` also searches those sandboxes, and
`data_dir_for()` **ignores `datadir.txt`'s contents when the root is sandboxed** —
under redirection the dashboard writes the path it *thinks* it used (the real
`%LOCALAPPDATA%`), which is a lie, and one that often names a directory the overlay
itself created, so an `is_dir()` check alone would happily follow it. The data is
always the `data/` sibling of the pointer. Covered by unit tests in `paths.rs`.

## What changed

**Removed the Frida path.** Upstream can attach [Frida](https://frida.re/) to the
running game, hook its TLS writes to lift your `auth_key`/`viewer_id`/`udid`, take
your Steam username + password to mint a session ticket, and call the game's API as
your client. It was opt-in and never ran at startup, and credentials were genuinely
DPAPI-encrypted at rest — but it attaches a debugger to the game process and wants
your Steam password, which is a lot of risk for a local dashboard to carry.

**Removed the mitmproxy path.** Upstream could flip your **system-wide** Windows
proxy and run [mitmproxy](https://mitmproxy.org/) with a trusted root CA to read
Team Trials results off the wire. It had no host allowlist, so while capture was on
*all* proxy-aware traffic on the machine was decrypted — and a crash could leave the
system proxy pointed at a dead port.

Both existed to reach data the overlay now provides directly:

| Data | Was | Now |
|------|-----|-----|
| Inventory | Frida + Steam → game API | `data.json` (Trackside's veterans export, or UmaExtractor) |
| Team Trials | mitmproxy capture | Trackside's own in-game capture → **Import in-game** |

**Known gap:** friends' borrowable parents came *only* from the Frida path, so the
Breed Optimizer's rental pool is empty here. The intended fix is to capture them
passively in Trackside — it already hooks `DecompressResponse`, and that list
arrives in a normal packet — rather than reintroduce injection.

## Files removed

| File | Why |
|------|-----|
| `fetch.py` | Frida capture, Steam ticket, game-API client. `write_trace()` survived — it's now in `safe_store.py`, since the `data.json` import still needs it |
| `tt_capture.py` | mitmproxy launcher + system-proxy toggle |
| `discover_addon.py` | mitmproxy addon |
| `decoder.py` | packet decode; used only by `discover_addon.py` |
| `tt_analyze.py` | read `data/raw_full.jsonl`, which only the mitmproxy addon ever wrote |
| `package.json` | `steam-user` (Node), only used to mint the Steam ticket |

Routes dropped: `/api/setup/start_capture`, `/api/setup/cancel_capture`,
`/api/setup/fetch`, `/api/capture/{status,start,stop}`, `/api/process`.
`/api/setup/status` no longer reports `has_auth`.

Dependencies dropped: `frida`, `mitmproxy`, `msgpack`, `pycryptodome`,
`curl_cffi` — the last three were only reachable from the two removed paths. What's
left is just the web stack (`fastapi`, `uvicorn`, `pydantic`, `python-multipart`).

## Merging from upstream

`upstream` is the original repo:

```bash
git fetch upstream
git merge upstream/master
```

Conflicts will land in `server.py`, `static/index.html`, `README.md` and
`requirements.txt`. When they do: **keep the removals.** If upstream adds a feature
that reaches for `fetch_mod` or `tt_capture`, it depends on a path that doesn't
exist here.
