"""Mini Militia host UDP port sweep (no root required).

Honesty note: this tool SENDS tiny UDP probes and RECORDS which ports answer.
It does not decode or label anything. An answering port is concrete evidence
(the host is listening there); silence on other ports is equally honest
evidence. See protocol/lan-protocol-research.md.

Why UDP sweep works without root: closed ports on most hosts simply ignore
bogus UDP packets (no ICMP reply needed for us — silence means closed), while
an OPEN port that belongs to a live service usually answers with a banner,
keep-alive, or protocol error. We record every answer.

Usage (Termux on the same LAN as the Mini Militia host):

    python3 ~/MiliPy/protocol/research/sweep.py --host 192.168.1.128 --out ~/sweep1

Default: all 65k UDP ports in ~2 minutes (concurrent). Use --range to focus:

    python3 ~/MiliPy/protocol/research/sweep.py --host 192.168.1.128 \
        --range 1-1024 --out ~/sweep2
"""
from __future__ import annotations

import argparse
import datetime
import json
import socket
import struct
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PCAP_GLOBAL_HEADER = struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 101)

# One probe per port. Two harmless payloads are tried on each port:
#   1) an empty datagram (some discovery protocols answer to empty)
#   2) a minimal binary that cannot be a valid command we don't know
PAYLOADS = [b""]


def _pcap_record(ts: float, packet: bytes) -> bytes:
    return struct.pack("<IIII", int(ts), int(ts * 1e6) % 1_000_000, len(packet), len(packet)) + packet


def probe_port(args: tuple) -> dict | None:
    host, port, timeout, tag = args
    for payload in PAYLOADS:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        try:
            sock.sendto(payload, (host, port))
            try:
                data, addr = sock.recvfrom(65536)
            except socket.timeout:
                continue
            # A zero-length reply is not evidence of a live service (loopback
            # and some OS stacks echo empty datagrams); keep only real bytes.
            if not data:
                continue
            return {
                "ts": time.time(),
                "port": port,
                "payload_len": len(payload),
                "src": addr[0],
                "sport": addr[1],
                "len": len(data),
                "first_hex": data[:32].hex(),
                "printable": "".join(chr(b) if 32 <= b < 127 else "." for b in data[:32]),
            }
        except OSError:
            continue
        finally:
            sock.close()
    return None


def run_sweep(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pcap_path = out.with_suffix(".pcap")
    log_path = out.with_suffix(".jsonl")

    meta = {
        "start": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "host": args.host,
        "range": args.range,
        "per_port_timeout": args.timeout,
        "tag": args.tag,
    }

    if args.range:
        lo, hi = args.range.split("-")
        ports = list(range(int(lo), int(hi) + 1))
    else:
        ports = list(range(1, 65536))

    print(f"[sweep] sweeping {args.host} ports {ports[0]}-{ports[-1]} "
          f"({len(ports)} ports, timeout {args.timeout}s each) — keep the game running", flush=True)

    replies: list[dict] = []
    t0 = time.time()
    jobs = [(args.host, p, args.timeout, args.tag) for p in ports]
    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        for result in ex.map(probe_port, jobs):
            if result:
                replies.append(result)
                print(
                    f"[sweep] ANSWER port={result['port']} {result['len']:>5} bytes "
                    f"from {result['sport']} first_bytes={result['first_hex']} "
                    f"printable={result['printable']!r}",
                    flush=True,
                )
    elapsed = time.time() - t0

    with log_path.open("w") as lf, pcap_path.open("wb") as pf:
        pf.write(PCAP_GLOBAL_HEADER)
        lf.write(json.dumps({"meta": meta}) + "\n")
        for r in replies:
            lf.write(json.dumps(r) + "\n")

    print(
        f"[sweep] done in {elapsed:.1f}s. {len(replies)} answered ports: "
        f"{sorted(r['port'] for r in replies)} -> see {log_path}",
        flush=True,
    )


def main() -> None:
    p = argparse.ArgumentParser(description="Mini Militia host UDP port sweep — no root needed")
    p.add_argument("--host", required=True, help="IP of the Mini Militia host phone")
    p.add_argument("--range", help="port range, e.g. 1-1024 (default: 1-65535)")
    p.add_argument("--timeout", type=float, default=0.4, help="seconds to wait for a reply per port")
    p.add_argument("--threads", type=int, default=64, help="concurrent probe workers")
    p.add_argument("--tag", default="sweep", help="human tag for the log")
    p.add_argument("--out", default="sweep", help="output base name")
    args = p.parse_args()
    run_sweep(args)


if __name__ == "__main__":
    main()
