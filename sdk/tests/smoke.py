"""Quick smoke test: Bot + SimAdapter lifecycle."""

import asyncio

from milipy import Bot
from milipy.protocol import CapabilityError
from milipy.sim import SimAdapter, SimWorld


async def main() -> None:
    world = SimWorld(enemies=2)
    adapter = SimAdapter(world)
    bot = Bot(adapter)

    seen = []
    states = []

    @bot.on("ready")
    def on_ready():
        print("READY, capabilities:", bot.capabilities.to_dict())

    @bot.on("player_seen")
    def on_seen(player):
        seen.append(player)
        print("player_seen:", player.name, player.position)

    @bot.on("state_update")
    def on_state(state):
        states.append(state)
        if state.player:
            print("tick", state.tick, "self:", state.player.position, "hp:", state.player.health)

    await bot.connect_async()
    bot.move("right")
    bot.fire()
    bot.aim(0.5, 0.5)
    await asyncio.sleep(1.5)
    bot.stop_movement()
    bot.stop_fire()
    bot.request_state()
    await asyncio.sleep(0.5)

    # Unsupported capability must raise, not silently pass.
    try:
        bot.throw_grenade()
    except CapabilityError as exc:
        print("CapabilityError as expected:", exc)

    # Aim at a player without position must refuse to fabricate.
    from milipy.state import Player
    try:
        bot.aim_at(Player(id="ghost"))
    except ValueError as exc:
        print("ValueError as expected:", exc)

    nearest = bot.nearest_enemy()
    print("nearest_enemy:", nearest)
    await bot.disconnect_async()
    await adapter.close()
    print(f"OK: {len(states)} state updates, {len(seen)} players seen")


asyncio.run(main())
