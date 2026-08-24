#!/bin/bash
# ─────────────────────────────────────────────────────────────────
#  BidBuddy — First-Time Setup Script
#  Run this once when setting up on a new Mac.
#  It will walk you through everything.
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
echo "  This script will do 3 things automatically:"
echo "    1. Check that Python is installed on your Mac"
echo "    2. Install the packages BidBuddy needs to run"
echo "    3. Tell Claude Desktop where to find BidBuddy"
echo ""
echo "  After this script finishes, you'll see 3 manual"
echo "  steps to complete inside Claude Desktop."
echo ""
echo "  ──────────────────────────────────────────────"
echo "  Press ENTER to start, or Ctrl+C to cancel."
read -r


# ── STEP 1 — Check Python ──────────────────────────────────────────────────────

echo ""
echo "  [ STEP 1 of 3 ]  Checking Python..."
echo ""

if ! command -v python3 &>/dev/null; then
    echo "  ✗  Python is not installed on this Mac."
    echo ""
    echo "  ┌─ What to do ──────────────────────────────────────┐"
    echo "  │  1. Open this link in your browser:               │"
    echo "  │     https://www.python.org/downloads/             │"
    echo "  │  2. Click the big yellow 'Download Python' button │"
    echo "  │  3. Install it (just click through the steps)     │"
    echo "  │  4. Come back here and run this script again      │"
    echo "  └────────────────────────────────────────────────────┘"
    echo ""
    exit 1
fi

PYTHON_VER="$(python3 --version 2>&1)"
echo "  ✓  $PYTHON_VER is installed — good to go."


# ── STEP 2 — Install packages ─────────────────────────────────────────────────

echo ""
echo "  [ STEP 2 of 3 ]  Installing required packages..."
echo "  (These let BidBuddy read Excel files, PDFs, and generate Word docs.)"
echo ""

if python3 -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet --disable-pip-version-check 2>&1; then
    echo "  ✓  All packages installed."
else
    echo ""
    echo "  ✗  Package install failed."
    echo ""
    echo "  ┌─ What to do ──────────────────────────────────────┐"
    echo "  │  Try running this command manually:               │"
    echo "  │    python3 -m pip install -r requirements.txt     │"
    echo "  │  If it still fails, contact your team lead.       │"
    echo "  └────────────────────────────────────────────────────┘"
    echo ""
    exit 1
fi


# ── STEP 3 — Configure Claude Desktop ─────────────────────────────────────────

echo ""
echo "  [ STEP 3 of 3 ]  Connecting BidBuddy to Claude Desktop..."
echo "  (Adding BidBuddy to Claude's settings file so it can use the tools.)"
echo ""

# Check Claude Desktop is installed
if [ ! -d "$HOME/Applications/Claude.app" ] && [ ! -d "/Applications/Claude.app" ]; then
    echo "  ✗  Claude Desktop is not installed."
    echo ""
    echo "  ┌─ What to do ──────────────────────────────────────┐"
    echo "  │  1. Open: https://claude.ai/download              │"
    echo "  │  2. Download and install Claude Desktop for Mac   │"
    echo "  │  3. Come back here and run this script again      │"
    echo "  └────────────────────────────────────────────────────┘"
    echo ""
    exit 1
fi

mkdir -p "$CONFIG_DIR"

if [ ! -f "$CONFIG_FILE" ]; then
    echo '{"mcpServers":{}}' > "$CONFIG_FILE"
fi

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

echo "  ✓  Claude Desktop configured."
echo "     Settings saved to:"
echo "     $CONFIG_FILE"


# ── ALL DONE — What to do next ────────────────────────────────────────────────

echo ""
echo "  ══════════════════════════════════════════════"
echo "  ✓  Setup complete! 3 steps left — in Claude."
echo "  ══════════════════════════════════════════════"
echo ""
echo "  Do these steps inside Claude Desktop:"
echo ""
echo "  ┌─ Step A ──────────────────────────────────────────────┐"
echo "  │  Quit Claude Desktop and reopen it.                   │"
echo "  │  (Press ⌘Q to quit, then reopen from Applications)   │"
echo "  │                                                        │"
echo "  │  → Look for the 🔨 icon in the chat bar.              │"
echo "  │    If you see it, BidBuddy is connected.              │"
echo "  └────────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─ Step B ──────────────────────────────────────────────┐"
echo "  │  Create a new Project in Claude Desktop.              │"
echo "  │                                                        │"
echo "  │  → Click 'New Project' in the left sidebar            │"
echo "  │  → Name it: BidBuddy                                  │"
echo "  └────────────────────────────────────────────────────────┘"
echo ""
echo "  ┌─ Step C ──────────────────────────────────────────────┐"
echo "  │  Add the KB files and instructions to the Project.    │"
echo "  │  ⚠  These are handed to you by your admin/team lead.  │"
echo "  │     Do NOT download them from anywhere else.          │"
echo "  │                                                        │"
echo "  │  → Upload the KB documents via 'Add Content'          │"
echo "  │  → Paste the Project Instructions text                │"
echo "  └────────────────────────────────────────────────────────┘"
echo ""
echo "  Once all 3 are done, open a chat in the BidBuddy project"
echo "  and start talking. You're all set!"
echo ""
