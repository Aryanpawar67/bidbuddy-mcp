#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  BidBuddy — First-Time Setup
#  Run once on a new Mac. Takes about 1–2 minutes.
# ─────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/Library/Application Support/Claude"
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

# Add common uv install locations to PATH for this session
export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

clear
echo ""
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║         BidBuddy  —  First-time Setup               ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo ""
echo "  This will set up BidBuddy on your Mac."
echo "  It takes about 1–2 minutes — do NOT close this window."
echo ""
echo "  Press ENTER to start, or Ctrl+C to cancel."
read -r
echo ""


# ══════════════════════════════════════════════════════════════════
#  STEP 0 of 5 — Check Git is installed & pull latest code
# ══════════════════════════════════════════════════════════════════

echo "  [0/5]  Checking for Git..."

if ! command -v git &>/dev/null; then
    echo ""
    echo "  ✗  Git is not installed."
    echo ""
    echo "  ┌─ How to install Git ──────────────────────────────────┐"
    echo "  │  1. In Terminal, run:  git --version                  │"
    echo "  │  2. A popup will appear — click Install               │"
    echo "  │  3. Wait for it to finish (~2 min)                    │"
    echo "  │  4. Run this setup again                              │"
    echo "  └───────────────────────────────────────────────────────┘"
    echo ""
    echo "  First time on this Mac? Get the repo with:"
    echo "    cd ~/Desktop"
    echo "    git clone https://github.com/Aryanpawar67/bidbuddy-mcp.git"
    echo ""
    exit 1
fi

echo "         ✓  Git found"
echo ""
echo "         Pulling latest BidBuddy updates..."

if git -C "$SCRIPT_DIR" pull --ff-only --quiet 2>/dev/null; then
    echo "         ✓  Up to date"
else
    echo "         ↷  Could not auto-update (skipping — continuing with current version)"
fi


# ══════════════════════════════════════════════════════════════════
#  STEP 1 of 5 — Check Claude Desktop is installed
# ══════════════════════════════════════════════════════════════════

echo ""
echo "  [1/5]  Checking for Claude Desktop..."

if [ ! -d "$HOME/Applications/Claude.app" ] && [ ! -d "/Applications/Claude.app" ]; then
    echo ""
    echo "  ✗  Claude Desktop is not installed."
    echo ""
    echo "  ┌─ How to install Claude Desktop ───────────────────────┐"
    echo "  │  1. Open Safari                                       │"
    echo "  │  2. Go to:  claude.ai/download                        │"
    echo "  │  3. Click 'Download for Mac'                          │"
    echo "  │  4. Open the downloaded file and follow the steps     │"
    echo "  │  5. Once installed, run this setup again              │"
    echo "  └───────────────────────────────────────────────────────┘"
    echo ""
    exit 1
fi

echo "         ✓  Claude Desktop found"


# ══════════════════════════════════════════════════════════════════
#  STEP 2 of 5 — Install uv (manages Python for us)
# ══════════════════════════════════════════════════════════════════

echo ""
echo "  [2/5]  Installing BidBuddy's tools..."
echo "         (Downloads a small helper that handles everything else.)"
echo "         (Skipped automatically if already installed.)"
echo ""

if command -v uv &>/dev/null; then
    echo "         ✓  Already installed — skipping"
else
    if curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; then
        echo "         ✓  Tools installed"
    else
        echo ""
        echo "  ✗  Could not download the tools."
        echo ""
        echo "  ┌───────────────────────────────────────────────────────┐"
        echo "  │  Check that your Mac is connected to the internet,    │"
        echo "  │  then run this setup again.                           │"
        echo "  └───────────────────────────────────────────────────────┘"
        echo ""
        exit 1
    fi
fi

# Confirm uv is reachable
if ! command -v uv &>/dev/null; then
    echo ""
    echo "  ✗  Setup hit a snag — could not find the tools just installed."
    echo ""
    echo "  ┌───────────────────────────────────────────────────────┐"
    echo "  │  Close this window, open a new Terminal window,       │"
    echo "  │  and run setup again:                                 │"
    echo "  │    bash ~/Desktop/bidbuddy-mcp/setup.sh               │"
    echo "  └───────────────────────────────────────────────────────┘"
    echo ""
    exit 1
fi


# ══════════════════════════════════════════════════════════════════
#  STEP 3 of 5 — Pre-download BidBuddy's add-ons
# ══════════════════════════════════════════════════════════════════

echo ""
echo "  [3/5]  Downloading BidBuddy's add-ons..."
echo "         (Like app updates — happens once, then BidBuddy is fast.)"
echo ""

if uv sync --directory "$SCRIPT_DIR" --quiet 2>&1; then
    echo "         ✓  Add-ons ready"
else
    echo ""
    echo "  ✗  Could not download add-ons."
    echo ""
    echo "  ┌───────────────────────────────────────────────────────┐"
    echo "  │  Check your internet connection and run setup again.  │"
    echo "  └───────────────────────────────────────────────────────┘"
    echo ""
    exit 1
fi


# ══════════════════════════════════════════════════════════════════
#  STEP 4 of 5 — Connect BidBuddy to Claude Desktop
# ══════════════════════════════════════════════════════════════════

echo ""
echo "  [4/5]  Connecting BidBuddy to Claude Desktop..."

# Quit Claude Desktop first — changes are ignored while it is open
if pgrep -x "Claude" &>/dev/null; then
    echo "         Claude Desktop is open — closing it so changes can take effect..."
    osascript -e 'quit app "Claude"' 2>/dev/null || killall "Claude" 2>/dev/null || true
    sleep 2
fi

mkdir -p "$CONFIG_DIR"

# Create a minimal config if none exists yet
if [ ! -f "$CONFIG_FILE" ]; then
    echo '{"mcpServers":{}}' > "$CONFIG_FILE"
fi

# Merge bidbuddy entry — preserves any other MCP servers the user already has
uv run --directory "$SCRIPT_DIR" python3 - "$CONFIG_FILE" "$SCRIPT_DIR" <<'PYEOF'
import json, sys

config_path = sys.argv[1]
script_dir  = sys.argv[2]

with open(config_path) as f:
    try:
        config = json.load(f)
    except json.JSONDecodeError:
        config = {}

config.setdefault("mcpServers", {})["bidbuddy"] = {
    "command": "uv",
    "args": ["--directory", script_dir, "run", "server.py"]
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)
PYEOF

echo "         ✓  BidBuddy connected"

# Reopen Claude Desktop automatically
echo ""
echo "         Reopening Claude Desktop..."
open -a "Claude" 2>/dev/null || true


# ══════════════════════════════════════════════════════════════════
#  STEP 5 of 5 — Done! Two small steps left inside Claude Desktop
# ══════════════════════════════════════════════════════════════════

echo ""
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║   ✓  Setup complete!                                 ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo ""
echo "  Two quick steps left inside Claude Desktop:"
echo ""
echo "  ┌─ Step 1 — Turn on BidBuddy ───────────────────────────┐"
echo "  │  In the chat bar, click the  +  button.              │"
echo "  │  Go to Connectors (or Browse Connectors).            │"
echo "  │  Find BidBuddy and toggle it ON.                     │"
echo "  │                                                       │"
echo "  │  If BidBuddy is not listed, quit Claude (⌘Q)         │"
echo "  │  and reopen it, then try again.                      │"
echo "  └───────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─ Step 2 — Open the BidBuddy project ─────────────────┐"
echo "  │  Click 'New Project' in the left sidebar.            │"
echo "  │  Name it: BidBuddy                                   │"
echo "  │                                                       │"
echo "  │  Then ask your admin to share:                        │"
echo "  │    • the 14 KB files (upload them to the project)    │"
echo "  │    • the Project Instructions text (paste it in)     │"
echo "  └───────────────────────────────────────────────────────┘"
echo ""
echo "  Once those are in, open a chat in the BidBuddy project"
echo "  and you're ready to go."
echo ""
echo "  ┌─ Staying up to date ──────────────────────────────────┐"
echo "  │  When BidBuddy is updated, run in Terminal:           │"
echo "  │    cd ~/Desktop/bidbuddy-mcp && git pull              │"
echo "  │  Then run setup.sh again to apply the changes.        │"
echo "  └───────────────────────────────────────────────────────┘"
echo ""
