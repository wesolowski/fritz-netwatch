#!/usr/bin/env python3
"""Reboot a FRITZ!Repeater via TR-064. Password is read from the macOS Keychain.
Config comes from environment (set by netcheck.sh) or falls back to .env / defaults."""
import subprocess, urllib.request, urllib.error, sys, os

def env(key, default=""):
    if key in os.environ:
        return os.environ[key]
    envfile = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(envfile):
        for line in open(envfile):
            line = line.strip()
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return default

IP = env("REPEATER_IP", "192.168.178.26")
KEYCHAIN_ITEM = env("KEYCHAIN_ITEM", "netwatch-repeater")
SERVICE = "urn:dslforum-org:service:DeviceConfig:1"
PATH = "/upnp/control/deviceconfig"

def pw():
    return subprocess.check_output(
        ["security", "find-generic-password", "-a", KEYCHAIN_ITEM, "-w"]
    ).decode().strip()

def reboot():
    url = f"http://{IP}:49000{PATH}"
    env_xml = (f'<?xml version="1.0"?>\n'
               f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
               f's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">'
               f'<s:Body><u:Reboot xmlns:u="{SERVICE}"></u:Reboot></s:Body></s:Envelope>')
    mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    mgr.add_password(None, url, "", pw())
    op = urllib.request.build_opener(urllib.request.HTTPDigestAuthHandler(mgr))
    req = urllib.request.Request(url, data=env_xml.encode(),
          headers={"Content-Type": 'text/xml; charset="utf-8"',
                   "SOAPACTION": f'"{SERVICE}#Reboot"'})
    op.open(req, timeout=15).read()

if __name__ == "__main__":
    try:
        reboot()
        print("OK: reboot command sent to repeater")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
