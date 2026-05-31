# Heaven

Unified dashboard for Uma Musume: breeding optimizer + Team Trials analysis.

## Quick Start

```bash
git clone https://github.com/Nighty3333/Heaven.git
cd Heaven
pip install -r requirements.txt
.\start.bat
```

Open http://127.0.0.1:1620

Character portraits download automatically from gametora the first time they're needed.

---

## Team Trials Capture Setup

The Team Trials tabs (Overview, Planner, Skill Lookup, Track & Condition) need live data captured from the game via a local proxy. This is a **one-time setup**.

### 1. Install mitmproxy certificate

The proxy needs a trusted certificate so it can read HTTPS traffic from the game.

```bash
pip install mitmproxy
mitmdump
```

Run `mitmdump` once and close it immediately (Ctrl+C). This generates the CA certificate at:

```
C:\Users\<YOU>\.mitmproxy\mitmproxy-ca-cert.cer
```

Now install it:

1. Double-click `mitmproxy-ca-cert.cer`
2. Click **Install Certificate...**
3. Select **Local Machine** (requires admin)
4. Choose **Place all certificates in the following store**
5. Click **Browse** > select **Trusted Root Certification Authorities**
6. Click OK > Next > Finish

> **Verify**: open `certmgr.msc` > Trusted Root Certification Authorities > Certificates, and look for **mitmproxy**.

### 2. Configure DMM/game proxy

The game needs to route traffic through the local proxy at `127.0.0.1:8080`.

#### Option A: System proxy (simplest)

Heaven handles this automatically when you click **Start Capture** in the Track & Condition tab. It sets the Windows system proxy to `127.0.0.1:8080` and restores it when you stop.

#### Option B: Manual (if Option A doesn't work)

Windows Settings > Network & Internet > Proxy > Manual proxy setup:
- Address: `127.0.0.1`
- Port: `8080`
- Turn **ON**

Remember to turn it **OFF** when done.

### 3. Capture data

1. Open Heaven at http://127.0.0.1:1620
2. Go to the **Track & Condition** tab
3. Click **Start Capture**
4. Play Team Trials matches in the game (the proxy intercepts match data automatically)
5. Click **Stop Capture** when done
6. Go to the **Team Trials** tab to see your captured results

The proxy auto-detects your `udid` from request headers on first capture. If it fails, place your udid manually in `data/udid.txt` (one line, 32 hex characters).

### 4. Troubleshooting

| Problem | Fix |
|---------|-----|
| `SEC_ERROR` or SSL errors in game | Certificate not installed correctly. Redo step 1, make sure you pick **Local Machine** and **Trusted Root** store |
| Capture starts but no data appears | Make sure the game traffic goes through the proxy. Check Windows proxy is set to `127.0.0.1:8080` |
| Game won't connect at all | The proxy might be blocking. Stop capture, check your internet works, then try again |
| `udid` not detected | Grab it manually from your game's request headers (32 hex chars) and save to `data/udid.txt` |
| Proxy stays on after crash | Windows Settings > Proxy > turn OFF manual proxy. Heaven tries to restore it on exit but crashes can skip that |

---

## Tabs

| Tab | What it does |
|-----|-------------|
| **Inventory** | Browse your character factor inventory |
| **Affinity** | Calculate breeding affinity between parents |
| **Breed** | Optimize parent combinations for target builds |
| **Team Trials** | Analyze captured TT match results |
| **Skill Planner** | Plan skill builds with activation rate data |
| **Skill Lookup** | Search skills by name/effect |
| **Track & Condition** | Stadium observations + capture control |
