# fritz-netwatch

Self-healing watchdog for a **FRITZ!Box + FRITZ!Repeater** mesh on macOS.
It detects the classic *repeater broadcast-storm* — when a repeater locks up and floods
the whole network, killing Wi-Fi and LAN for every device — and automatically reboots the
repeater before you even notice. Plus a local dashboard and phone push alerts.

> Born from a real incident: throughput was fine one hour, then every device in the house
> crawled. A router reboot didn't help — power-cycling the **repeater** did. This tool watches
> for that exact signature and fixes it on its own.

## What it does

- **Every 15 minutes** pings the router and measures packet loss + round-trip time.
- If loss/latency crosses your thresholds, it's a **storm** → reboots the repeater via **TR-064**.
- Tells apart a repeater storm from an ISP-line problem (also pings an external host).
- **Alerts** via macOS notification **and** phone push (via [ntfy](https://ntfy.sh)).
- Writes a rolling log and a **local HTML dashboard** with uptime %, latency chart and event history.
- A 1-hour cooldown prevents reboot loops; if a storm persists after a reboot it warns you to check the cable/ISP instead.

## Requirements

- macOS (uses `launchd`, `security` Keychain, `osascript`)
- A FRITZ!Box and a FRITZ!Repeater with **TR-064 enabled**
  (FRITZ!Box UI → Home Network → Network → Network Settings → *Allow access for applications*)
- Python 3 (system or Homebrew)

## Install

```bash
git clone git@github.com:wesolowski/fritz-netwatch.git
cd fritz-netwatch
cp .env.example .env      # then edit .env with your router/repeater IPs
./install.sh              # asks for the repeater password (stored in Keychain), sets up the schedule
```

Then subscribe to the generated **ntfy topic** (printed by the installer) in the
[ntfy app](https://ntfy.sh) on your phone to receive push alerts.

## Usage

```bash
./show.sh                 # regenerate + open the dashboard
cat netcheck.log          # raw history
./netcheck.sh             # run a check right now
./netcheck.sh selftest    # send a test alert (Mac + phone)
```

Thresholds and IPs live in `.env`:

| Key | Meaning | Default |
|-----|---------|---------|
| `ROUTER_IP` | your FRITZ!Box | `192.168.178.1` |
| `REPEATER_IP` | your repeater | `192.168.178.26` |
| `INTERNET_IP` | external ping target | `1.1.1.1` |
| `LOSS_MAX` | % packet loss → storm | `30` |
| `RTT_MAX` | ms round-trip → storm | `800` |
| `COOLDOWN` | seconds between reboots | `3600` |
| `NTFY_TOPIC` | phone push topic (empty = off) | — |

## Security

- The repeater password is stored in the **macOS Keychain**, never in a file.
- `.env` (IPs, ntfy topic) and all runtime data are **git-ignored** — nothing private is committed.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.user.netwatch.plist
rm ~/Library/LaunchAgents/com.user.netwatch.plist
security delete-generic-password -a netwatch-repeater   # optional
```

## Notes & limitations

- Runs only while the Mac is awake (checks resume on wake). For 24/7 coverage, run it on an always-on box (e.g. a Raspberry Pi) — the scripts are portable, only the macOS-specific notify/Keychain bits need swapping.
- Rebooting the repeater is a soft TR-064 reboot, equivalent to a power-cycle for clearing a stuck state.

## License

MIT — see [LICENSE](LICENSE).
