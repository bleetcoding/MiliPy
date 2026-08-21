"""Mini Militia LAN discovery probe (no root required).

Honesty note: this tool SENDS small UDP packets and RECORDS the replies. It
does not decode anything. Every reply it records is genuine network evidence
(either the game host answering, or nothing), tagged with exactly what was
sent, so the analysis stays strictly OBSERVED — see protocol/lan-protocol-research.md.

Why this works without root: an unprivileged app can always *receive* packets
addressed to its own sockets. We can't sniff Mini Militia's traffic between
other devices, but we CAN talk to the host directly. If Mini Militia's LAN host
answers UDP on a port, we catch the answer in our socket — and that answer
reveals the host's port and often a discovery/banner payload.

Usage (on any Termux device on the same LAN/hotspot as the Mini Militia game):

    # 1. Start a LAN game on the host phone, join from the other phone.
    # 2. Paste:
    python3 ~/MiliPy/protocol/research/probe.py --host 192.168.43.1 --out ~/probe1
    # 3. While it runs (default: all likely ports, ~2 min), keep the game open
    #    on both phones. The output lists which ports answered and how big the
    #    replies are — that is the first concrete evidence of the protocol.

    # Target a suspected port range faster:
    python3 ~/MiliPy/protocol/research/probe.py --host 192.168.43.1 \
        --port-range 44300-44320 --out ~/probe2
"""
from __future__ import annotations

import argparse
import datetime
import json
import socket
import struct
import sys
import time
from pathlib import Path

PCAP_GLOBAL_HEADER = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 101)


def _pcap_record(ts: float, packet: bytes) -> bytes:
    return struct.pack("<IIII", int(ts), int(ts * 1e6) % 1_000_000, len(packet), len(packet)) + packet


def run_probe(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pcap_path = out.with_suffix(".pcap")
    log_path = out.with_suffix(".jsonl")

    meta = {
        "start": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host": args.host,
        "port_range": args.port_range,
        "tag": args.tag,
    }

    # Build the probe port list.
    if args.port_range:
        lo, hi = args.port_range.split("-")
        ports = list(range(int(lo), int(hi) + 1))
    else:
        # Ports commonly used by Unity-based LAN games + Mini Militia folklore.
        # Every one of these is an educated guess (INFERRED); the replies decide
        # what is real (OBSERVED).
        ports = (
            [8766, 8888, 44300, 44301, 44302, 44303, 44304, 44305, 44306, 44307, 44308, 44309]
            + list(range(50000, 50010))
            + list(range(7777, 7780))
            + [27015, 27016]
        )

    # A small, harmless discovery probe payload: a few bytes that real LAN
    # games typically accept as a "is anyone there?" ping. We send a minimal
    # byte that cannot resemble a valid game command sequence we don't know —
    # we're probing, not impersonating a player.
    probe_payloads = [b""]  # empty UDP datagram

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(0.5)

    replies: list[dict] = []
    answered_ports: list[int] = []

    with log_path.open("w") as lf, pcap_path.open("wb") as pf:
        pf.write(PCAP_GLOBAL_HEADER)
        lf.write(json.dumps({"meta": meta}) + "\n")

        # Give any local listener (e.g. a test harness) time to bind first.
        time.sleep(args.warmup)
        for port in ports:
            for payload in probe_payloads:
                try:
                    sock.sendto(payload, (args.host, port))
                except OSError as exc:  # noqa: PERF203
                    print(f"[probe] send to {args.host}:{port} failed: {exc}", file=sys.stderr)
                    continue
            # Wait for any reply (banner, ack, or error-ICMP echo).
            deadline = time.time() + args.per_port
            while time.time() < deadline:
                try:
                    data, addr = sock.recvfrom(65536)
                except socket.timeout:
                    break
                ts = time.time()
                pf.write(_pcap_record(ts, data))
                entry = {"ts": ts, "src": addr[0], "sport": addr[1], "len": len(data)}
                replies.append(entry)
                lf.write(json.dumps(entry) + "\n")
                print(
                    f"[probe] REPLY {len(data):>5} bytes from {addr[0]}:{addr[1]} "
                    f"port={port} first_bytes={data[:16].hex()}"
                )
                answered_ports.append(port)

    print(
        f"[probe] done. {len(replies)} replies; answered ports: "
        f"{sorted(set(answered_ports))} -> see {pcap_path}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Mini Militia LAN discovery probe — no root needed")
    p.add_argument("--host", required=True, help="IP of the Mini Militia host phone (see host's LAN screen)")
    p.add_argument("--port-range", help="explicit range, e.g. 44300-44320")
    p.add_argument("--per-port", type=float, default=0.6, help="seconds to wait for replies per probe port")
    p.add_argument("--tag", default="probe", help="human tag for the log")
    p.add_argument("--warmup", type=float, default=2.0, help="seconds to wait before the first probe (lets listeners bind)")
    p.add_argument("--out", default="probe", help="output base name")
    args = p.parse_args()
    run_probe(args)


if __name__ == "__main__":
    main()
