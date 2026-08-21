# Running MiliPy in Termux

This guide walks through installing the MiliPy Python SDK in Termux on Android, connecting to a MiliPy Bridge, and running the example bot. It ends with the single-phone setup, where the bridge and the bot run on the same device.

## Prerequisites

You need Termux installed (from [F-Droid](https://f-droid.org/packages/com.termux/) or [GitHub releases](https://github.com/termux/termux-app/releases) — avoid the Play Store version, which is unmaintained) and Android 9 or newer. The SDK requires Python 3.10 or later; current Termux ships Python 3.11/3.12, so no pinning is needed.

## Install

Open Termux and run:

```bash
pkg update -y && pkg install -y python git

git clone https://github.com/bleetcoding/MiliPy.git ~/MiliPy
cd ~/MiliPy
pip install -e sdk
```

The `pip install -e sdk` step installs the `milipy` package in editable mode from the repository you just cloned. Optionally, run the offline test suite to confirm everything works before connecting to a real bridge:

```bash
pip install pytest pytest-asyncio
cd sdk && python3 -m pytest
python3 ../examples/first_bot.py --simulate
```

## Connect to a bridge

The bot needs a running MiliPy Bridge somewhere on a reachable network. There are three common arrangements.

### Arrangement 1: Bridge on the same phone (simplest)

Install `app-debug.apk` on your own phone, start the bridge, and connect to it over localhost:

```bash
export MILIPY_HOST=127.0.0.1
export MILIPY_PORT=8765
export MILIPY_PAIRING=<code shown in the bridge app>
python3 ~/MiliPy/examples/first_bot.py
```

### Arrangement 2: Bridge on another phone on the same Wi-Fi

Start the bridge on the other phone and point the bot at its LAN IP, which the bridge app shows in its notification. Keep both devices on the same Wi-Fi network:

```bash
export MILIPY_HOST=192.168.1.37
export MILIPY_PORT=8765
export MILIPY_PAIRING=<code shown in the bridge app>
python3 ~/MiliPy/examples/first_bot.py
```

### Arrangement 3: Bridge on the hotspot host (LAN-game topology)

If the bridge phone is also the Mini Militia LAN host, it enables the hotspot and the Termux device (a second phone or a laptop) connects to that hotspot. The hotspot gateway is typically `192.168.43.1`, but discover it properly with `ip route`:

```bash
ip route | awk '/default/ {print $3}'   # prints the gateway, e.g. 192.168.43.1
export MILIPY_HOST=$(ip route | awk '/default/ {print $3}')
export MILIPY_PORT=8765
export MILIPY_PAIRING=<code>
python3 ~/MiliPy/examples/first_bot.py
```

## What to expect

On a successful connection you should see `Bot has spawned`, followed by `Game session:` lines and repeated enemy sightings with positions. Every accepted action receives an `ack` from the bridge. If you get `ConnectionRefusedError`, the bridge is not running or the IP is wrong; if you get `auth_error: invalid_token`, re-copy the pairing code from the bridge app.

## Keeping the bot running

Termux sessions are killed when the app is backgrounded unless you take one of these steps. For quick tests, just keep Termux visible. For longer runs, acquire a partial wake lock:

```bash
pkg install termux-api
termux-wake-lock
```

Then run the bot as usual. Release the lock with `termux-wake-unlock` when finished.

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `pkg: command not found` | You are not actually in Termux, or `proot`/`chroot` is misconfigured |
| `pip: command not found` | Install python first: `pkg install python`; then use `python3 -m pip install -e sdk` |
| `ModuleNotFoundError: websockets` | Run `python3 -m pip install websockets`; if compilation fails, `pkg install python-pip build-essential` first |
| `ConnectionRefusedError` | Bridge not started, or Termux and the bridge are on different networks (e.g., cellular vs. Wi-Fi) |
| `auth_error: invalid_token` | The pairing code changed or was copied with whitespace; the bridge rotates it on restart |
| Actions raise `CapabilityError` | Enable the bridge's accessibility service and grant MediaProjection capture consent |
| Python older than 3.10 | Update packages (`pkg upgrade`) — current Termux always ships a new enough Python |
