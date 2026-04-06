#!/bin/bash
# setup.sh — Install dependencies and configure Mac cron job for the Telegram bot.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON=$(which python3)
LOGFILE="$SCRIPT_DIR/bot.log"

echo "=== Telegram Finance Bot Setup ==="
echo "Project dir : $SCRIPT_DIR"
echo "Python      : $PYTHON"
echo ""

# ── 1. Install dependencies ─────────────────────────────────────────────────
echo "[1/3] Installing Python dependencies..."
"$PYTHON" -m pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
echo "      Done."

# ── 2. Verify .env exists ───────────────────────────────────────────────────
if [ ! -f "$SCRIPT_DIR/.env" ]; then
    echo ""
    echo "⚠️  .env not found. Copying .env.example → .env"
    cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
    echo "    Please fill in your keys in: $SCRIPT_DIR/.env"
    echo "    Then re-run this script."
    exit 1
fi
echo "[2/3] .env found."

# ── 3. Set up cron jobs ──────────────────────────────────────────────────────
# TZ=America/New_York lets cron interpret the times directly in ET,
# handling DST automatically without needing separate UTC entries.

CRON_CMD_MORNING="0 11 * * * $PYTHON $SCRIPT_DIR/main.py >> $LOGFILE 2>&1"
CRON_CMD_EVENING="0 23 * * * $PYTHON $SCRIPT_DIR/main.py >> $LOGFILE 2>&1"

echo "[3/3] Configuring cron jobs..."

# Remove any existing entries for this script
EXISTING=$(crontab -l 2>/dev/null | grep -v "$SCRIPT_DIR/main.py" | grep -v "^TZ=" || true)

NEW_CRON="$EXISTING
TZ=America/New_York
# Telegram Finance Bot — 11:00 AM ET
$CRON_CMD_MORNING
# Telegram Finance Bot — 11:00 PM ET
$CRON_CMD_EVENING"

echo "$NEW_CRON" | crontab -

echo "      Cron jobs registered:"
crontab -l | grep -E "TZ=|main\.py"
echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Fill in $SCRIPT_DIR/.env with your keys"
echo "  2. Test manually: python3 $SCRIPT_DIR/main.py"
echo "  3. View logs:    tail -f $LOGFILE"
