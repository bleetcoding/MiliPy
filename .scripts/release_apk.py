#!/usr/bin/env python3
"""Replace the app-debug.apk asset on a MiliPy release. ANSI-safe gh wrapper."""
import json
import os
import subprocess
import sys

REPO = "bleetcoding/MiliPy"
APK = "experimental/bridge/app/build/outputs/apk/debug/app-debug.apk"
TAG = sys.argv[1] if len(sys.argv) > 1 else "v0.3.0"


import re

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def gh(*args):
    env = {**os.environ, "NO_COLOR": "1", "CLICOLOR": "0"}
    r = subprocess.run(
        ["gh"] + list(args), capture_output=True, text=True, env=env,
    )
    return r.returncode, _ANSI.sub("", r.stdout).strip()


rc, out = gh("api", f"repos/{REPO}/releases/tags/{TAG}")
if rc != 0:
    sys.exit(f"release lookup failed: {out}")
rel = json.loads(out)
rel_id = rel["id"]

rc, out = gh("api", f"repos/{REPO}/releases/{rel_id}/assets")
assets = json.loads(out) if rc == 0 else []
for a in assets:
    if a["name"] == "app-debug.apk":
        rc2, _ = gh("api", "-X", "DELETE", f"repos/{REPO}/releases/assets/{a['id']}")
        print(f"deleted asset {a['id']} (rc={rc2})")

rc, out = gh(
    "release", "upload", TAG, APK, "--repo", REPO, "--clobber",
)
print(out[:300])
sys.exit(rc)
