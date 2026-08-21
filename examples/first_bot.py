"""first_bot.py — the canonical MiliPy example.

Run against the real bridge:

    MILIPY_PAIRING=<code> python3 examples/first_bot.py

Run against the simulator (no phone needed):

    python3 examples/first_bot.py --simulate
"""
import sys
import time

from milipy import Bot, SimAdapter, SimWorld, CapabilityError


def make_bot() -> Bot:
    if "--simulate" in sys.argv:
        return Bot(SimAdapter(world=SimWorld(enemies=2)))
    import os
    host = os.environ.get("MILIPY_HOST", "192.168.43.1")
    port = int(os.environ.get("MILIPY_PORT", "8765"))
    pairing = os.environ.get("MILIPY_PAIRING", "")
    return Bot(host=host, port=port, pairing_token=pairing)


bot = make_bot()


@bot.on("ready")
def ready():
    print("Bot has spawned")


@bot.on("player_seen")
def on_enemy(player):
    print("Enemy:", player.name, player.position)


@bot.on("game_session")
def on_game_session(session):
    print("Game session:", session.value)


@bot.on("tick")
def tick(state):
    enemy = bot.nearest_enemy()
    if enemy:
        try:
            bot.aim_at(enemy)
            bot.fire()
        except CapabilityError as exc:
            print("input unavailable:", exc)


if __name__ == "__main__":
    bot.connect()
    bot.run()
