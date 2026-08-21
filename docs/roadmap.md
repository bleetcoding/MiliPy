# MiliPy Roadmap

The roadmap grows capability-by-capability, each time behind an honest capability flag, per the project's core engineering rule. Version numbers describe maturity, not promises.

## v0.1 — current (foundation)

Local bridge, versioned WebSocket protocol, Python SDK, Termux support, simulator, screen observation, and the initial input abstraction (movement holds, jump, crouch, aim, fire, punch) are all implemented and tested offline. Publication to GitHub completes this milestone.

## v0.2 — perception

A perception layer analyzes captured frames so the bridge can report `GAME_DETECTED`, `MAIN_MENU`, `LAN_MENU`, `LOBBY_VISIBLE`, `IN_LOBBY`, `IN_GAME`, and `GAME_OVER` truthfully. Player detection and tracking follow, which unblocks a real `bot.nearest_enemy()` that sees players on screen rather than only in simulation. Movement and aim APIs gain calibration so actions map accurately to each device.

## v0.3 — combat actions

Firing accuracy, weapon switching, pickup, grenade, and punch move from `CapabilityError` to backed implementations, gated on the perception layer knowing where weapons, grenades, and enemies are on screen.

## v0.4 — metagame

Player statistics, chat, settings round-trip for game-visible settings, and a richer event vocabulary (kill, death, respawn, lobby change) once the perception layer can read the relevant UI regions.

## v0.5 — platform

A stable protocol contract, a plugin architecture for reusable behaviors, integration testing against a hardware matrix, and documentation refresh. The protocol gains a formal compatibility policy before any external consumers are encouraged.

## v1.0 — stability

Declaring 1.0 happens only after the API and bridge have proven stable on real devices across multiple Mini Militia versions and both network topologies. No artificial timeline.
