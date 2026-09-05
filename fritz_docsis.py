#!/usr/bin/env python3
"""Read DOCSIS line quality from a FRITZ!Box (cable) and print one compact summary line.
Password from macOS Keychain. Config from env / .env. Silent-safe: prints nothing on failure."""
import subprocess, urllib.request, urllib.parse, hashlib, json, os, sys
import xml.etree.ElementTree as ET

def env(key, default=""):
    if key in os.environ: return os.environ[key]
    envfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(envfile):
        for line in open(envfile):
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default

BOX = env("BOX_IP", "192.168.178.1")
KC  = env("BOX_KEYCHAIN", "netmon-box")

def get(url, data=None):
    req = urllib.request.Request(url, data=data.encode() if data else None)
    return urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "replace")

def pw():
    return subprocess.check_output(["security","find-generic-password","-a",KC,"-w"]).decode().strip()

def login():
    x = ET.fromstring(get(f"http://{BOX}/login_sid.lua?version=2"))
    ch = x.findtext("Challenge"); user = x.findtext("Users/User") or ""
    _, i1, s1, i2, s2 = ch.split("$")
    h1 = hashlib.pbkdf2_hmac("sha256", pw().encode(), bytes.fromhex(s1), int(i1))
    h2 = hashlib.pbkdf2_hmac("sha256", h1, bytes.fromhex(s2), int(i2))
    body = urllib.parse.urlencode({"username": user, "response": f"{s2}${h2.hex()}"})
    sid = ET.fromstring(get(f"http://{BOX}/login_sid.lua?version=2", body)).findtext("SID")
    if sid == "0"*16: raise RuntimeError("login failed")
    return sid

def main():
    sid = login()
    body = urllib.parse.urlencode({"sid":sid,"page":"docInfo","lang":"de","xhr":"1","no_sidrenew":""})
    d = json.loads(get(f"http://{BOX}/data.lua", body)).get("data", {})
    uncorr = corr = 0
    ds_pwr = []; us_pwr = []
    for grp in ("channelDs",):
        for kind, arr in (d.get(grp) or {}).items():
            if isinstance(arr, list):
                for c in arr:
                    uncorr += int(c.get("nonCorrErrors", 0) or 0)
                    corr   += int(c.get("corrErrors", 0) or 0)
                    if c.get("powerLevel") not in (None, ""): ds_pwr.append(float(c["powerLevel"]))
    for kind, arr in (d.get("channelUs") or {}).items():
        if isinstance(arr, list):
            for c in arr:
                if c.get("powerLevel") not in (None, ""): us_pwr.append(float(c["powerLevel"]))
    dsr = f"{min(ds_pwr):.0f}..{max(ds_pwr):.0f}" if ds_pwr else "?"
    usr = f"{min(us_pwr):.0f}..{max(us_pwr):.0f}" if us_pwr else "?"
    print(f"DOCSIS uncorr={uncorr} corr={corr} ds_pwr={dsr} us_pwr={usr}")

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print(f"# docsis error: {e}", file=sys.stderr); sys.exit(1)
