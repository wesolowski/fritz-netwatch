#!/bin/zsh
# fritz-netwatch: detects a FRITZ!Repeater "broadcast storm" (packet loss / high RTT
# to the router) and auto-heals by rebooting the repeater via TR-064.
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin"
set -u
DIR="${0:A:h}"
LOG="$DIR/netcheck.log"
STATE="$DIR/last_reboot.txt"

# --- load config ---
[ -f "$DIR/.env" ] && source "$DIR/.env"
ROUTER_IP="${ROUTER_IP:-192.168.178.1}"
INTERNET_IP="${INTERNET_IP:-1.1.1.1}"
NTFY_TOPIC="${NTFY_TOPIC:-}"
LOSS_MAX="${LOSS_MAX:-30}"
RTT_MAX="${RTT_MAX:-800}"
COOLDOWN="${COOLDOWN:-3600}"
export REPEATER_IP KEYCHAIN_ITEM   # used by reboot_repeater.py

# regenerate dashboard on every exit
trap 'python3 "$DIR/gen_dashboard.py" >/dev/null 2>&1' EXIT

ts() { date "+%Y-%m-%d %H:%M:%S"; }
notify() {  # $1=title  $2=body
  osascript -e "display notification \"$2\" with title \"$1\" sound name \"Basso\"" 2>/dev/null
  [ -n "$NTFY_TOPIC" ] && curl -s -m 8 -H "Title: $1" -d "$2" "https://ntfy.sh/$NTFY_TOPIC" >/dev/null 2>&1
}

# self-test mode
if [ "${1:-}" = "selftest" ]; then
  notify "fritz-netwatch test" "If you see this (Mac + phone), alerts work."
  echo "$(ts) SELFTEST notification sent" >> "$LOG"
  exit 0
fi

# measure router
OUT=$(ping -c 20 -i 0.2 -t 3 "$ROUTER_IP" 2>/dev/null)
LOSS=$(echo "$OUT" | grep -oE '[0-9.]+% packet loss' | grep -oE '^[0-9.]+' | cut -d. -f1)
MAXR=$(echo "$OUT" | grep -oE '= [0-9./]+ ms' | tr '/' ' ' | awk '{print int($4)}')
LOSS=${LOSS:-100}; MAXR=${MAXR:-9999}

# measure internet (to tell repeater-storm from ISP-line problems)
IOUT=$(ping -c 10 -i 0.2 -t 3 "$INTERNET_IP" 2>/dev/null)
ILOSS=$(echo "$IOUT" | grep -oE '[0-9.]+% packet loss' | grep -oE '^[0-9.]+' | cut -d. -f1)
ILOSS=${ILOSS:-100}

# DOCSIS line quality (best-effort; cable models only)
DOC=$(python3 "$DIR/fritz_docsis.py" 2>/dev/null)
[ -n "$DOC" ] && echo "$(ts) $DOC" >> "$DIR/docsis.log"

STORM=0
[ "$LOSS" -ge "$LOSS_MAX" ] && STORM=1
[ "$MAXR" -ge "$RTT_MAX" ] && STORM=1

if [ "$STORM" -eq 0 ]; then
  echo "$(ts) OK  Router: ${LOSS}% Verlust, ${MAXR}ms | Internet: ${ILOSS}% Verlust" >> "$LOG"
  exit 0
fi

echo "$(ts) STURM Router: ${LOSS}% Verlust, max ${MAXR}ms | Internet: ${ILOSS}%" >> "$LOG"

NOW=$(date +%s); LAST=$(cat "$STATE" 2>/dev/null || echo 0); DIFF=$(( NOW - LAST ))
if [ "$DIFF" -lt "$COOLDOWN" ]; then
  echo "$(ts) -> Reboot uebersprungen (vor $((DIFF/60))min neugestartet)" >> "$LOG"
  notify "Netz-Stoerung besteht weiter" "Router ${LOSS}% loss. Repeater already rebooted $((DIFF/60))min ago - check cable / ISP."
  exit 0
fi

notify "Repeater storm detected" "Router ${LOSS}% loss, ${MAXR}ms. Rebooting repeater..."
if python3 "$DIR/reboot_repeater.py" >> "$LOG" 2>&1; then
  echo "$NOW" > "$STATE"
  echo "$(ts) -> Repeater-Reboot ausgeloest" >> "$LOG"
  notify "Repeater rebooting" "Should recover in ~2 min. Next check in 15 min."
else
  echo "$(ts) -> Reboot FEHLGESCHLAGEN" >> "$LOG"
  notify "Reboot failed" "Could not reboot repeater. Please power-cycle it manually."
fi
