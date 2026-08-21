# Mini Militia LAN Protocol Research Notes (Round 5)

## Established facts (from public sources, searched Aug 2026)

1. **Game identity**: Mini Militia — Doodle Army 2 (DA2), by Appsomniacs LLC.
   Google Play package: `com.appsomniacs.da2`. iOS: https://apps.apple.com/us/app/mini-militia-doodle-army-2/id405885221
   Up to 6 players online multiplayer (older marketing), LAN Wi-Fi up to 12 players
   (softonic description). 2D dual-stick shooter, Unity Android game.
2. **LAN works over local Wi-Fi/hotspot, no internet needed.** Public sources (Instagram
   reel, Unity discussions forum post) state it uses **UDP for low-latency gameplay** on
   the local network.
   - https://www.instagram.com/reel/DGNeM94yQwB/
   - https://discussions.unity.com/t/android-mobile-local-multiplayer-game-via-wifi/178881
3. **GameSpy-powered originally**; official online servers shut down ~2018; multiplayer
   mode shutdown announced Oct 1 2022, effective March 26 2024 (Stop Killing Games wiki:
   https://stopkillinggames.wiki.gg/wiki/Dead_game_list). LAN/local multiplayer
   reportedly still works offline because it is peer-hosted — host phone runs the game
   session, others join over LAN.
4. **Host model**: "One of the player hosts the game and all other players connect to
   that host" (Unity forum). Classic LAN flow: host creates game room, client sees lobby
   on LAN screen, taps to join, match starts.

## What is NOT publicly documented (searched multiple queries)
- No public packet documentation exists for the Mini Militia LAN protocol.
- No reverse-engineering writeups, no GitHub repos with working DA2 protocol
  implementations found in searches.
- Exact discovery mechanism (broadcast vs mDNS vs direct port), packet formats,
  serialization, crypto are all undocumented publicly.

## Unity networking era inference (must be labeled INFERRED, not assumed)
DA2 released 2011-2013 for Android (Unity era). Unity LAN multiplayer of that era
typically used either custom UDP on a fixed port, or Unity's old networking (now
deprecated UNet/MasterServer). Cannot be confirmed for DA2 without packet capture.
The current game ("Mini Militia - War.io") is heavily updated; online mode now uses
Gamesparks/Amazon GameLift-like backend. LAN mode remains local-hosted.

## Honest classification (for the research doc)
- KNOWN: game identity; LAN operates over local Wi-Fi; transport is UDP (gameplay) per
  public sources; host-client topology; offline-capable.
- OBSERVED: nothing yet — no packet captures exist in this project. This is the
  primary research gap.
- INFERRED: discovery likely via UDP broadcast on a known port; host runs authoritative
  session; lobby exchange precedes spawn; state syncs at ~30-60 Hz typical for Unity
  2D shooters. ALL marked INFERRED, not tested.
- UNKNOWN: packet formats, message types, serialization, auth, ports, discovery port,
  encryption, all 15 protocol areas the user listed.

## Research path (to be documented in protocol research layer)
1. Packet capture on a real device: tcpdump/wireshark on Termux rootless pcapdump,
   or a second phone running a hotspot with another device as bridge/router logging.
2. Identify the host's listening port: netstat on the host phone after creating a LAN
   room; look for non-standard UDP listeners.
3. Replay/simulator: a fake Mini Militia client or a capture-based replay harness that
   can play recorded captures and log decoded frames.
4. Iterative decode: strings analysis of the APK (jadx decompile) to find hardcoded
   ports, packet headers, magic numbers.

## User's 15 research areas (to structure the research doc)
1 LAN host discovery, 2 LAN lobby discovery, 3 host/client handshake, 4 lobby join,
5 player identity/session, 6 spawn messages, 7 player state sync, 8 movement, 9 aim,
10 weapon selection, 11 fire/actions, 12 projectile/grenade events, 13 damage/death,
14 chat, 15 clean disconnect.

## Round-5 user directive (verbatim intent)
- MiliPy = Mineflayer-like standalone client, Python on Termux, direct LAN protocol.
- Android bridge/A11y/MediaProjection NOT the core; demote to optional experimental module.
- Do NOT fabricate packet formats. Research layer must distinguish
  KNOWN / OBSERVED / INFERRED / UNKNOWN.
- Build packet capture/replay/test framework where possible.
- Bot API like mineflayer (spawn/player_join/player_leave/nearest_enemy/aim_at/fire).
- Android bridge not required for core client.
- Do NOT claim MM protocol support until real LAN interoperability demonstrated.
- Research what mineflayer is and how it works.
