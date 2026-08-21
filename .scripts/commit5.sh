#!/usr/bin/env bash
# Commit + push for round 5 (architecture correction: standalone LAN client)
set -e
cd /home/ubuntu/milipy
git add -A
git -c user.name="MiliPy CI" -c user.email="ci@milipy.local" commit -q -m "v0.4.0: architecture correction — standalone Mini Militia LAN client (Mineflayer-style)

- NEW CORE DIRECTION: MiliPy is a standalone Mini Militia LAN client that
  runs entirely from Termux and speaks the game's LAN protocol directly,
  appearing as an ordinary LAN client/player. The Android bridge is
  demoted to optional/experimental (experimental/bridge/).

- protocol/lan-protocol-research.md: honesty model
  KNOWN/OBSERVED/INFERRED/UNKNOWN. All 15 protocol areas (discovery,
  handshake, join, spawn, sync, movement, aim, weapons, fire, grenades,
  damage, chat, disconnect) currently UNKNOWN — no public packet docs
  exist; nothing is fabricated.

- protocol/research/: capture.py (UDP pcap+jsonl recorder with action
  tags, rootless port-listener fallback), analyze.py (statistics-only
  structure probes, never a decoder), replay.py (round-trip harness).

- SDK: Bot retargeted at the LAN host; honest gate in connect raises
  CapabilityError until LAN captures promote the codec out of UNKNOWN.
  Adapter path (SimAdapter, bridge adapter) unchanged. New
  tests/test_lan_gate.py (3 tests); 124 tests pass; -u added to CI
  example run.

- Docs: architecture.md, roadmap.md, termux.md rewritten for the new
  design; experimental/bridge/README.md documents its optional status;
  android-specific docs moved under experimental/docs/.

- Versions: SDK 0.4.0; v0.3.0 APK rebuilt in place on the release.

- Bridge builds green after move to experimental/bridge/; CI job
  renamed bridge-experimental."
git push origin main -q
git log -1 --format="%H %s"
