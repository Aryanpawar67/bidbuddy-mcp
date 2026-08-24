#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  BidBuddy — First-Time Setup Script
#  Run this once when setting up on a new Mac.
# ─────────────────────────────────────────────────────────────────

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/Library/Application Support/Claude"
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

clear
echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║           BidBuddy  —  Setup                 ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""
echo "  This script will:"
echo "    1. Check your Mac has everything it needs"
echo "    2. Install the packages BidBuddy depends on"
echo "    3. Connect BidBuddy to Claude Desktop"
echo ""
echo "  Your BidBuddy folder is at:"
echo "    $SCRIPT_DIR"
echo ""
echo "  ──────────────────────────────────────────────"
echo "  Press ENTER to start, or Ctrl+C to cancel."
read -r


# ══════════════════════════════════════════════════════════════════
#  PHASE 1 — CHECK EVERYTHING BEFORE DOING ANYTHING
# ══════════════════════════════════════════════════════════════════

echo ""
echo "  Checking your Mac..."
echo ""

ALL_OK=true


# ── Check 1: Python ───────────────────────────────────────────────

if command -v python3 &>/dev/null; then
    PYTHON_VER="$(python3 --version 2>&1)"
    echo "  ✓  $PYTHON_VER found"
else
    echo "  ✗  Python is not installed"
    ALL_OK=false
fi


# ── Check 2: Claude Desktop ───────────────────────────────────────

if [ -d "$HOME/Applications/Claude.app" ] || [ -d "/Applications/Claude.app" ]; then
    echo "  ✓  Claude Desktop found"
else
    echo "  ✗  Claude Desktop is not installed"
    ALL_OK=false
fi


# ── If anything is missing — stop and explain ─────────────────────

if [ "$ALL_OK" = false ]; then
    echo ""
    echo "  ──────────────────────────────────────────────────────"
    echo "  ✗  Setup cannot continue. Fix the items above first."
    echo "  ──────────────────────────────────────────────────────"
    echo ""

    if ! command -v python3 &>/dev/null; then
        echo "  ┌─ Install Python ───────────────────────────────────┐"
        echo "  │  1. Open:  https://www.python.org/downloads/       │"
        echo "  │  2. Click the yellow 'Download Python' button      │"
        echo "  │  3. Open the downloaded file and click through     │"
        echo "  └────────────────────────────────────────────────────┘"
        echo ""
    fi

    if [ ! -d "$HOME/Applications/Claude.app" ] && [ ! -d "/Applications/Claude.app" ]; then
        echo "  ┌─ Install Claude Desktop ───────────────────────────┐"
        echo "  │  1. Open:  https://claude.ai/download              │"
        echo "  │  2. Download Claude Desktop for Mac                │"
        echo "  │  3. Open the downloaded file and install it        │"
        echo "  └────────────────────────────────────────────────────┘"
        echo ""
    fi

    echo "  Once installed, run this script again:"
    echo "    bash ~/Desktop/bidbuddy-mcp/setup.sh"
    echo ""
    exit 1
fi

echo ""
echo "  ✓  All checks passed. Starting setup..."


# ══════════════════════════════════════════════════════════════════
#  PHASE 2 — INSTALL AND CONFIGURE
# ══════════════════════════════════════════════════════════════════

# ── Step 1: Install packages ──────────────────────────────────────

echo ""
echo "  ─────────────────────────────────────────────────────"
echo "  [ Step 1 of 2 ]  Installing required packages"
echo "  (These let BidBuddy read Excel files, PDFs, Word docs)"
echo "  ─────────────────────────────────────────────────────"
echo ""

if python3 -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet --disable-pip-version-check 2>&1; then
    echo "  ✓  Packages installed"
else
    echo ""
    echo "  ✗  Package install failed."
    echo ""
    echo "  ┌─ What to do ───────────────────────────────────────┐"
    echo "  │  Try running this command manually:                │"
    echo "  │    python3 -m pip install -r requirements.txt      │"
    echo "  │  If it still fails, send a screenshot to your      │"
    echo "  │  team lead.                                        │"
    echo "  └────────────────────────────────────────────────────┘"
    echo ""
    exit 1
fi


# ── Step 2: Write Claude Desktop config ──────────────────────────

echo ""
echo "  ─────────────────────────────────────────────────────"
echo "  [ Step 2 of 2 ]  Connecting BidBuddy to Claude Desktop"
echo "  ─────────────────────────────────────────────────────"
echo ""
echo "  Detected your BidBuddy server path as:"
echo "    $SCRIPT_DIR/server.py"
echo "  (This path is written into Claude's settings automatically.)"
echo ""

mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_FILE" ]; then
    echo '{"mcpServers":{}}' > "$CONFIG_FILE"
fi

# Merge bidbuddy into existing config — preserves any other MCP servers already set up
python3 - "$CONFIG_FILE" "$SCRIPT_DIR/server.py" <<'PYEOF'
import json, sys

config_path = sys.argv[1]
server_path = sys.argv[2]

with open(config_path) as f:
    try:
        config = json.load(f)
    except json.JSONDecodeError:
        config = {}

config.setdefault("mcpServers", {})["bidbuddy"] = {
    "command": "python3",
    "args": [server_path]
}

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)
PYEOF

echo "  ✓  Claude Desktop settings updated"
echo "     File: $CONFIG_FILE"


# ══════════════════════════════════════════════════════════════════
#  DONE — NEXT STEPS
# ══════════════════════════════════════════════════════════════════

echo ""
echo "  ╔══════════════════════════════════════════════╗"
echo "  ║   ✓  Setup complete!                         ║"
echo "  ║      Do these 3 steps in Claude Desktop:     ║"
echo "  ╚══════════════════════════════════════════════╝"
echo ""
echo "  ┌─ Step A — Restart Claude Desktop ─────────────────┐"
echo "  │  Quit Claude (⌘Q) and reopen it.                  │"
echo "  │  → You should see a 🔨 icon in the chat bar.      │"
echo "  │    That means BidBuddy is connected.              │"
echo "  └────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─ Step B — Create the BidBuddy Project ────────────┐"
echo "  │  In Claude Desktop:                               │"
echo "  │  → Click 'New Project' in the left sidebar        │"
echo "  │  → Name it: BidBuddy                              │"
echo "  └────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─ Step C — Add KB files + Instructions ────────────┐"
echo "  │  ⚠  Get these from your admin — not from GitHub.  │"
echo "  │                                                    │"
echo "  │  → In the BidBuddy project, click 'Add Content'   │"
echo "  │    and upload the 14 KB documents                 │"
echo "  │  → Paste the Project Instructions text            │"
echo "  └────────────────────────────────────────────────────┘"
echo ""
echo "  You're done. Open a chat in the BidBuddy project and start."
echo ""
