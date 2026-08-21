"""Mini Militia LAN "sponge" probe (no root required).

Honesty note: this tool only records what the network actually sends back.
Every payload it sends is an educated GUESS (INFERRED); anything received is
OBSERVED evidence. It never claims to know what bytes mean.

Why a different shape from sweep.py: a full-port sweep sends EMPTY probes to
each port sequentially. A strict game server silently drops unknown payloads,
and discovery traffic in LAN games is usually BROADCAST-based, not unicast.
So this tool combines three techniques in one run:

1. **Broadcast probes** — sends every probe payload to the LAN broadcast
   address on candidate ports (255.255.255.255 and the subnet broadcast).
   LAN game discovery almost always answers broadcasts, and broadcasts reach
   every device on the segment — including hosts that ignore unicast.

2. **Multi-payload per port** — instead of one empty probe, sends several
   distinct payloads per port (empty, single common bytes, a "hello"-shaped
   guess). Different servers tolerate different shapes.

3. **Passive listener** — while probing, keeps a UDP listener open and records
   ANY packet addressed to it (hosts answering broadcasts, or spontaneous LAN
   chatter that happens to hit our ephemeral port is impossible, but answers
   to our broadcasts are precisely what we want).

Usage (Termux on the same LAN as the Mini Militia LAN game):

    python3 ~/MiliPy/protocol/research/sponge.py --host 192.168.1.128 --out ~/sponge1

    # If you know the game server's subnet broadcast, use --broadcast too:
    python3 ~/MiliPy/protocol/research/sponge.py --host 192.168.1.128 \
        --broadcast 192.168.1.255 --out ~/sponge2

While running: keep the Mini Militia LAN session open/hosted on the target.
"""
from __future__ import annotations

import argparse
import datetime
import ipaddress
import json
import socket
import struct
import sys
import time
from pathlib import Path

PCAP_GLOBAL_HEADER = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 101)


def _pcap_record(ts: float, packet: bytes) -> bytes:
    return struct.pack("<IIII", int(ts), int(ts * 1e6) % 1_000_000, len(packet), len(packet)) + packet


def _subnet_broadcast(host: str) -> str:
    try:
        net = ipaddress.IPv4Network(f"{host}/24", strict=False)
        return str(net.broadcast_address)
    except ValueError:
        return "255.255.255.255"


# Candidate payloads per port. These are honest guesses (INFERRED), not known
# Mini Militia formats. Each entry is (name, bytes).
DEFAULT_PAYLOADS = [
    ("empty", b""),
    ("null", b"\x00"),
    ("ones", b"\xff"),
    ("mili", b"MILI"),
    ("hello_text", b"hello"),
    ("two_zeros_len", b"\x00\x00"),
    ("query_01", b"\x01"),
]


def run_sponge(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pcap_path = out.with_suffix(".pcap")
    log_path = out.with_suffix(".jsonl")

    broadcast = args.broadcast or _subnet_broadcast(args.host)

    meta = {
        "start": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host": args.host,
        "broadcast": broadcast,
        "tag": args.tag,
    }

    # Candidate ports: well-known LAN-game discovery ports + a spread of
    # common high ports. This is a guess list (INFERRED); silence is honest.
    if args.range:
        lo, hi = args.range.split("-")
        ports = list(range(int(lo), int(hi) + 1))
    else:
        ports = [
            8766, 8888, 9001, 27015, 27016, 27017, 44300, 44301, 44302, 44303,
            44304, 44305, 44306, 44307, 44308, 44309, 44310,
        ] + list(range(50000, 50020)) + list(range(7777, 7790))

    # The listener socket: we need a FIXED port so broadcast answers (which
    # come back to our source port) are catchable, and because the broadcast
    # answers are sent to the sender's address+port.
    # A single socket both sends (bound to a fixed source port, so replies
    # return here) and receives. Binding a SEPARATE listener socket would lose
    # the replies: they are delivered to the bound send socket, not a peer.
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        send_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except OSError:
        pass
    send_sock.bind(("0.0.0.0", 0))
    listen_port = send_sock.getsockname()[1]
    send_sock.settimeout(args.listen_timeout)

    print(
        f"[sponge] listener bound on :{listen_port}; probing broadcasts "
        f"({broadcast}) + unicast ({args.host}) on {len(ports)} ports x "
        f"{len(args.payloads)} payloads",
        flush=True,
    )



    seen: dict[tuple[str, int, bytes], float] = {}
    events: list[dict] = []

    def record(kind: str, **fields) -> None:
        entry = {"ts": time.time(), "kind": kind, **fields}
        events.append(entry)
        with open(log_path, "a") as lf:
            lf.write(json.dumps(entry) + "\n")
        print(f"[sponge] {kind}: {fields}", flush=True)

    with open(log_path, "w") as lf:
        lf.write(json.dumps({"meta": meta}) + "\n")
        with open(pcap_path, "wb") as pf:
            pf.write(PCAP_GLOBAL_HEADER)

            # Background passive reader: record anything arriving while we probe.
            import threading

            def reader() -> None:
                while not stop_event.is_set():
                    try:
                        data, addr = send_sock.recvfrom(65536)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if not data:
                        continue
                    ts = time.time()
                    record(
                        "reply",
                        src=addr[0],
                        sport=addr[1],
                        len=len(data),
                        first_hex=data[:32].hex(),
                        printable="".join(chr(b) if 32 <= b < 127 else "." for b in data[:32]),
                    )
                    key = (addr[0], addr[1], data[:64])
                    if key in seen and time.time() - seen[key] < 0.3:
                        continue  # dedupe flood
                    seen[key] = ts
                    with open(pcap_path, "ab") as p2:
                        p2.write(_pcap_record(ts, data))

            stop_event = threading.Event()
            t = threading.Thread(target=reader, daemon=True)
            t.start()

            time.sleep(args.warmup)
            for port in ports:
                for name, payload in args.payloads:
                    for dest, label in ((broadcast, "broadcast"), (args.host, "unicast")):
                        try:
                            send_sock.sendto(payload, (dest, port))
                        except OSError as exc:  # noqa: PERF203
                            print(f"[sponge] send {label} :{port} failed: {exc}", file=sys.stderr)
                time.sleep(args.pause)

            # Tail listener for a bit after the last probe (answers can be slow).
            time.sleep(args.tail)
            stop_event.set()
            t.join(2)

    print(
        f"[sponge] done. {len(events)} recorded events -> see {log_path} / {pcap_path}",
        flush=True,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Mini Militia LAN broadcast sponge — no root needed")
    p.add_argument("--host", required=True, help="IP of the Mini Militia host phone (for unicast probes)")
    p.add_argument("--broadcast", help="subnet broadcast address (default: derived from host IP)")
    p.add_argument("--range", help="port range, e.g. 44000-44320 (default: candidate LAN-game ports)")
    p.add_argument("--payloads", help="comma-separated payload names: " + ",".join(n for n, _ in DEFAULT_PAYLOADS))
    p.add_argument("--pause", type=float, default=0.05, help="seconds between probe batches")
    p.add_argument("--listen-timeout", type=float, default=0.3, help="recv timeout for the listener")
    p.add_argument("--warmup", type=float, default=1.0, help="seconds before first probe")
    p.add_argument("--tail", type=float, default=2.0, help="seconds to keep listening after last probe")
    p.add_argument("--tag", default="sponge", help="human tag for the log")
    p.add_argument("--out", default="sponge", help="output base name")
    args = p.parse_args()

    if args.payloads:
        names = {n for n, _ in DEFAULT_PAYLOADS}
        want = {n.strip() for n in args.payloads.split(",")}
        bad = want - names
        if bad:
            p.error(f"unknown payload names: {sorted(bad)}")
        args.payloads = [(n, b) for n, b in DEFAULT_PAYLOADS if n in want]
    else:
        args.payloads = DEFAULT_PAYLOADS

    run_sponge(args)


if __name__ == "__main__":
    main()
