#!/usr/bin/env python3
"""Create GitHub release v0.4.0 with the bridge APK (ANSI-safe gh wrapper)."""
import json
import os
import re
import subprocess
import sys

REPO = "bleetcoding/MiliPy"
APK = "experimental/bridge/app/build/outputs/apk/debug/app-debug.apk"
TAG = "v0.4.0"
BODY = """Architecture correction: MiliPy is now a Mineflayer-style standalone Mini Militia LAN client.

- Core: Python Bot on Termux targeting the Mini Militia LAN protocol directly (no phone automation required).
- protocol/lan-protocol-research.md: honesty model (KNOWN / OBSERVED / INFERRED / UNKNOWN). All 15 wire areas currently UNKNOWN — no public packet docs exist; nothing fabricated.
- protocol/research/: capture.py / analyze.py / replay.py — tagged UDP capture, statistics-only probes, round-trip replay harness.
- SDK honesty gate: Bot("<host>") raises CapabilityError until LAN captures promote the codec out of UNKNOWN; adapter path (simulator / bridge) unchanged. 124 tests pass.
- Android bridge demoted to experimental/bridge/ (optional).
- APK on this release = v0.3.0 build (bridge unchanged since then; no bridge code changes in v0.4.0).

Tests: 124 passing (simulator-driven). No Mini Militia interoperability claimed — the capture framework exists precisely to earn that claim.
"""

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def gh(*args):
    env = {**os.environ, "NO_COLOR": "1", "CLICOLOR": "0"}
    r = subprocess.run(["gh"] + list(args), capture_output=True, text=True, env=env)
    return r.returncode, _ANSI.sub("", r.stdout).strip()


# Ensure APK exists (rebuild if missing)
if not os.path.exists(APK):
    print("APK missing, rebuilding bridge...")
    subprocess.run(
        ["bash", "-lc",
         "cd /home/ubuntu/milipy/experimental/bridge && "
         "export ANDROID_HOME=$HOME/android-sdk && "
         "source ~/.sdkman/bin/sdkman-init.sh && sdk use gradle 8.9 2>/dev/null >/dev/null && "
         "gradle assembleDebug"],
        check=True,
    )

rc, out = gh("release", "create", TAG, "--title",
             "v0.4.0 — standalone LAN client architecture",
             "--notes", BODY, APK, "--repo", REPO)
print(out[:500] if out else f"rc={rc}")
sys.exit(rc)
