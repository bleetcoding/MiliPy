#!/usr/bin/env python3
"""List assets of a MiliPy release (ANSI-safe)."""
import json
import os
import re
import subprocess
import sys

REPO = "bleetcoding/MiliPy"
_TAG = sys.argv[1] if len(sys.argv) > 1 else "v0.3.0"
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def gh(*args):
    env = {**os.environ, "NO_COLOR": "1", "CLICOLOR": "0"}
    r = subprocess.run(["gh"] + list(args), capture_output=True, text=True, env=env)
    return r.returncode, _ANSI.sub("", r.stdout).strip()


rc, out = gh("api", f"repos/{REPO}/releases/tags/{_TAG}")
rel = json.loads(out)
rc, out = gh("api", f"repos/{REPO}/releases/{rel['id']}/assets")
for a in json.loads(out):
    print(a["id"], a["name"], a["size"], a.get("browser_download_url"))
