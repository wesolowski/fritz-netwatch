#!/bin/zsh
# fritz-netwatch installer: sets up config, keychain, ntfy topic and the launchd schedule.
set -e
DIR="${0:A:h}"
PLIST="$HOME/Library/LaunchAgents/com.user.netwatch.plist"

echo "==> fritz-netwatch install"

# 1) config
if [ ! -f "$DIR/.env" ]; then
  cp "$DIR/.env.example" "$DIR/.env"
  echo "Created .env from template — edit it now with your IPs, then re-run install."
fi

# 2) ntfy topic (generate if empty)
if ! grep -qE '^NTFY_TOPIC="[^"]+"' "$DIR/.env"; then
  TOPIC="fritz-netwatch-$(openssl rand -hex 4)"
  /usr/bin/sed -i '' "s/^NTFY_TOPIC=.*/NTFY_TOPIC=\"$TOPIC\"/" "$DIR/.env"
  echo "Generated ntfy topic: $TOPIC  (subscribe to it in the ntfy app)"
fi

# 3) keychain password
source "$DIR/.env"
if ! security find-generic-password -a "${KEYCHAIN_ITEM:-netwatch-repeater}" -w >/dev/null 2>&1; then
  echo -n "Enter your FRITZ!Repeater password (stored in macOS Keychain): "
  read -s RPW; echo
  security add-generic-password -a "${KEYCHAIN_ITEM}" -s "${KEYCHAIN_ITEM}" -w "$RPW" -U
  echo "Password stored in Keychain as '${KEYCHAIN_ITEM}'."
fi

# 4) launchd
sed "s#__DIR__#$DIR#g" "$DIR/com.user.netwatch.plist.template" > "$PLIST"
launchctl unload "$PLIST" 2>/dev/null || true
launchctl load "$PLIST"
echo "Scheduled: runs every 15 min (com.user.netwatch)."

# 5) first run
/bin/zsh "$DIR/netcheck.sh" >/dev/null 2>&1 || true
echo "Done. Open the dashboard with:  ./show.sh"
