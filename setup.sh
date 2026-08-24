#!/bin/bash
# BidBuddy — one-time setup script
# Run this once on a new Mac. Takes ~2 minutes.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_DIR="$HOME/Library/Application Support/Claude"
CONFIG_FILE="$CONFIG_DIR/claude_desktop_config.json"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  BidBuddy Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Check Python ────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌  Python 3 is not installed."
    echo ""
    echo "    Download it from: https://www.python.org/downloads/"
    echo "    Install it, then run this script again."
    echo ""
    exit 1
fi
echo "✅  Python $(python3 --version | cut -d' ' -f2)"

# ── 2. Install dependencies ────────────────────────────────────────────────────
echo "    Installing dependencies..."
python3 -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet --disable-pip-version-check
echo "✅  Dependencies installed"

# ── 3. Check Claude Desktop is installed ──────────────────────────────────────
if [ ! -d "$HOME/Applications/Claude.app" ] && [ ! -d "/Applications/Claude.app" ]; then
    echo ""
    echo "⚠️   Claude Desktop not found."
    echo "    Download from: https://claude.ai/download"
    echo "    Install it, then run this script again."
    echo ""
    exit 1
fi
echo "✅  Claude Desktop found"

# ── 4. Write Claude Desktop MCP config ────────────────────────────────────────
echo "    Configuring Claude Desktop..."
mkdir -p "$CONFIG_DIR"

# Create config if it doesn't exist
if [ ! -f "$CONFIG_FILE" ]; then
    echo '{"mcpServers":{}}' > "$CONFIG_FILE"
fi

# Merge bidbuddy entry into existing config (preserves any other MCP servers)
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

echo "✅  Claude Desktop configured"

# ── Done ───────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Next — do these 3 things once in Claude Desktop:"
echo ""
echo "  1. Quit Claude Desktop and reopen it"
echo "     (you should see a 🔨 icon in the chat bar)"
echo ""
echo "  2. Create a new Project named 'BidBuddy'"
echo "     → Click 'New Project' in the left sidebar"
echo ""
echo "  3. Upload the 14 KB documents to the Project"
echo "     → See README.md → 'KB Documents' for the list"
echo ""
echo "  4. Paste the Project Instructions into the Project"
echo "     → See README.md → 'Project Instructions'"
echo ""
echo "After that: just open a chat in the BidBuddy project and start talking."
echo ""
