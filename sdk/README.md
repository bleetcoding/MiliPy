# milipy — Python SDK

The Python package behind [MiliPy](https://github.com/bleetcoding/MiliPy), a Mineflayer-style standalone client for Mini Militia that runs entirely from Termux.

## Install

```bash
git clone https://github.com/bleetcoding/MiliPy.git
cd MiliPy && pip install -e sdk
```

## Quick start

```python
from milipy import Bot

bot = Bot("192.168.1.x")

bot.on("spawn", lambda: print("Bot has spawned"))
bot.connect()
```

> **Current state:** the Mini Militia LAN packet codec is not yet validated against a real game (no public protocol documentation exists), so connecting to a raw LAN host raises a `CapabilityError` with a pointer to the protocol research document. Offline use is fully supported through the bundled simulator (`Bot(SimAdapter(...))`), which drives all SDK tests. See the root README and `protocol/lan-protocol-research.md` for the honesty model and the capture framework that fills this gap.

## Offline demo (no phone, no network)

```bash
python3 ../examples/first_bot.py --simulate
```

## Test

```bash
cd sdk && python3 -m pytest   # 124 tests
```
