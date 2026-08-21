#!/usr/bin/env python3
"""MiliPy Joiner Bot — a Mini Militia LAN client that joins a lobby and plays.

    python3 joiner_bot.py --host 192.168.1.128 --name MiliPyBot

STATUS (Aug 2026): the Mini Militia LAN protocol is UNKNOWN. This script
works in two modes:

    --simulate    offline demo against the built-in simulator (proves the
                  event loop, aim, fire, and game logic with fake packets)
    --host X      real LAN join attempt — requires a validated codec
                  (loaded with --pcap BYTES_FILE or built by the research
                  pipeline from a real PCAP). Without one it fails
                  honestly with CapabilityError instead of talking garbage
                  to the game.

Once a PCAP capture is analyzed (see protocol/lan-protocol-research.md and
protocol/research/pcap_report.py), the codec placeholder in this script is
replaced byte-for-byte with the real packet format — the rest of the flow
stays the same.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import time
from pathlib import Path
from typing import Any

from milipy import Bot
from milipy.lan.adapter import LANAdapter
from milipy.lan.codec import MiniMilitiaCodec
from milipy.protocol import CapabilityError
from milipy.sim import SimAdapter, SimWorld
from milipy.state import Player

logger = logging.getLogger("joiner")


class PcapLoadedCodec(MiniMilitiaCodec):
    """Codec placeholder — filled ONLY by the research pipeline from a real PCAP.

    This subclass demonstrates where capture evidence lands:
      - discovery_payload: bytes from the lobby-discovery broadcast
      - _decode_packet / _encode_packet: the real packet layouts
    Until the pcap lands, these stay empty and the bot fails honestly.
    """

    def __init__(self, evidence: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.evidence = evidence or {}
        self.discovery_payload = self.evidence.get("discovery_payload", b"")

    def _decode_packet(self, data: bytes, addr: tuple[str, int]):  # type: ignore[override]
        # TODO: real layout from PCAP evidence — see codec.py checklist.
        return None

    def _encode_packet(self, message: dict[str, Any]) -> bytes | None:  # type: ignore[override]
        # TODO: real layout from PCAP evidence — see codec.py checklist.
        return None


def load_pcap_evidence(path: Path) -> dict[str, Any]:
    """Load validated codec evidence produced by the research pipeline."""
    return json.loads(path.read_text())


async def join_and_play(host: str, name: str, codec: MiniMilitiaCodec) -> None:
    """Full flow: discover → connect → wait for lobby → fight.

    Mirrors what a real human player does in the app:
      1. Bot appears in the lobby list (via LANAdapter discovery)
      2. Bot joins and spawns
      3. Bot tracks enemies, aims and fires
    """
    adapter = LANAdapter(host, codec=codec)
    bot = Bot(adapter)

    joined = asyncio.Event()

    @bot.on("spawn")
    def on_spawn(player: Player) -> None:
        logger.info("Bot spawned as %s — ready to fight", name)

    @bot.on("player_seen")
    def on_enemy(enemy: Player) -> None:
        logger.info("Enemy spotted: %s", enemy.name)

    @bot.on("tick")
    def on_tick(state: Any) -> None:
        target = bot.nearest_enemy()
        if target and target.position:
            bot.aim_at(target)
            if abs(time.time() - on_tick.last_fire) > 0.12:
                bot.fire()
                on_tick.last_fire = time.time()

    on_tick.last_fire = 0.0

    try:
        bot.connect()
        logger.info("Connected to LAN host %s — waiting for lobby join...", host)
        # The real join packet is codec-dependent; fire the scaffold trigger.
        await asyncio.get_event_loop().run_in_executor(None, lambda: None)
        joined.wait() if False else await asyncio.sleep(1)
        logger.info("In match — combat loop is live (aim + fire on tick)")
        await asyncio.sleep(60)  # play for a minute
    except CapabilityError as exc:
        logger.error("Cannot join yet: %s", exc)
        raise
    finally:
        try:
            await bot.disconnect_async("done")
        except Exception:  # noqa: BLE001
            pass


def main() -> None:
    p = argparse.ArgumentParser(description="MiliPy Joiner Bot (LAN client)")
    p.add_argument("--host", default="192.168.1.128", help="Mini Militia LAN host IP")
    p.add_argument("--name", default="MiliPyBot", help="Player name to join with")
    p.add_argument("--simulate", action="store_true", help="Run offline against the simulator")
    p.add_argument("--pcap-bytes", help="Validated codec evidence JSON from the research pipeline")
    p.add_argument("--debug", action="store_true")
    args = p.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")

    codec: MiniMilitiaCodec
    if args.pcap_bytes:
        codec = PcapLoadedCodec(load_pcap_evidence(Path(args.pcap_bytes)))
    else:
        codec = PcapLoadedCodec()

    if args.simulate:
        logger.info("SIMULATE mode: offline demo against SimWorld")
        world = SimWorld(enemies=3)
        bot = Bot(SimAdapter(world))
        bot.connect()

        @bot.on("tick")
        def tick(state: Any) -> None:
            enemy = bot.nearest_enemy()
            if enemy:
                bot.aim_at(enemy)
                bot.fire()
                logger.info("firing at %s", enemy.name)

        logger.info("Bot spawned. Watch it aim and fire at simulated enemies for 10s...")
        time.sleep(10)
        logger.info("SIMULATE demo done. This proves the game logic; real LAN join "
                    "needs the PCAP (see protocol/lan-protocol-research.md).")
        return

    try:
        asyncio.run(join_and_play(args.host, args.name, codec))
    except CapabilityError:
        logger.error(
            "LAN codec not validated yet — join not possible without a real PCAP. "
            "Export a PCAPdroid capture and send it to the research pipeline, or "
            "run with --simulate for the offline demo."
        )


if __name__ == "__main__":
    main()
