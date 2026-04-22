#!/usr/bin/env bash
# run_agent.sh — Daily investment agent runner
#
# Manual:  ./run_agent.sh
# Cron:    0 7 * * 1-5  /full/path/to/investmentAgent/run_agent.sh
#
# Pulls latest data from main, runs run1 → waits → run2, then pushes updated data back.
# All output is logged to logs/agent.log with timestamps.

set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
WAIT_MINUTES=0            # No wait — run2 executes immediately after run1
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/agent.log"

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
# Load TELEGRAM_* vars from ~/.bashrc (bypasses the interactive-only guard)
if [[ -f "$HOME/.bashrc" ]]; then
  eval "$(grep -E '^(export\s+)?TELEGRAM_' "$HOME/.bashrc")"
fi

mkdir -p "$SCRIPT_DIR/logs"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cd "$SCRIPT_DIR"

PYTHON="$SCRIPT_DIR/.venv/bin/python3"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(which python3)"
fi

log "========================================"
log "Investment Agent — daily run starting"
log "========================================"

# ---------------------------------------------------------------------------
# Sync — pull latest portfolio data from main
# ---------------------------------------------------------------------------
log "--- SYNC: pulling latest data from main ---"
if git pull origin master 2>&1 | tee -a "$LOG_FILE"; then
  log "Pull complete"
else
  log "ERROR: git pull failed — aborting to avoid data conflict"
  exit 1
fi

# ---------------------------------------------------------------------------
# Run 1 — market scan + Claude analysis
# ---------------------------------------------------------------------------
log "--- RUN1: market scan + Claude analysis ---"
if $PYTHON -m agent.main run1 2>&1 | tee -a "$LOG_FILE"; then
  log "RUN1 complete"
else
  log "ERROR: run1 failed — aborting"
  exit 1
fi

# ---------------------------------------------------------------------------
# Run 2 — execute the trade plan
# ---------------------------------------------------------------------------
log "--- RUN2: executing trade plan ---"
if $PYTHON -m agent.main run2 2>&1 | tee -a "$LOG_FILE"; then
  log "RUN2 complete"
else
  log "ERROR: run2 failed"
  exit 1
fi

# ---------------------------------------------------------------------------
# Sync — push updated portfolio data back to main
# ---------------------------------------------------------------------------
log "--- SYNC: pushing updated data to main ---"
git add data/portfolio.db data/run1_plan.json 2>&1 | tee -a "$LOG_FILE"

if git diff --cached --quiet; then
  log "No data changes to commit"
else
  TODAY="$(date '+%Y-%m-%d')"
  git commit -m "data: daily run $TODAY" 2>&1 | tee -a "$LOG_FILE"
  if git push origin master 2>&1 | tee -a "$LOG_FILE"; then
    log "Push complete"
  else
    log "WARNING: git push failed — run data saved locally but not synced"
  fi
fi

log "========================================"
log "Daily run finished"
log "========================================"

# ---------------------------------------------------------------------------
# Cron reference — weekly digest
# ---------------------------------------------------------------------------
# Weekly digest (Sunday 1pm PT = 20:00 UTC during PDT)
# 0 20 * * 0  cd /path/to/investmentAgent && python -m agent.main weekly >> logs/agent.log 2>&1
