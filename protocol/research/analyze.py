"""Hypothesis-generating analysis of Mini Militia LAN captures.

Honesty note: every output line below is a STATISTIC about captured bytes,
never a decoded packet field. A "header length histogram" does not mean the
protocol has that header — it means packet sizes cluster there. Decoding
hypotheses must be validated with the replay round-trip before entering code.
See protocol/lan-protocol-research.md.

Usage:
    python3 analyze.py capture.jsonl            # statistical probes
    python3 analyze.py capture.pcap             # same, from pcap directly
    python3 analyze.py --sweep 127.0.0.1 44300-44310   # port sweep helper
"""
from __future__ import annotations

import argparse
import json
import math
import socket
import struct
import sys
from collections import Counter
from pathlib import Path


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def probe_payloads(payloads: list[bytes], tag: str) -> None:
    print(f"=== probes on {tag}: {len(payloads)} payloads ===")
    if not payloads:
        print("  (no payloads)")
        return

    lengths = sorted(len(p) for p in payloads)
    print(f"  length: min={lengths[0]} max={lengths[-1]} median={lengths[len(lengths)//2]}")

    lc = Counter(lengths)
    print(f"  length histogram (top 8): {lc.most_common(8)}")

    # Header-length hypothesis: if first-N bytes repeat across packets while
    # the tail varies, N is a candidate header size.
    for n in (1, 2, 3, 4, 8, 12, 16):
        heads = Counter(p[:n] for p in payloads if len(p) >= n)
        uniq = len(heads) / max(1, len(payloads))
        print(f"  first-{n} bytes unique ratio: {uniq:.2%}" + ("  <- candidate fixed header" if uniq < 0.1 else ""))

    # Common prefix: longest prefix shared by all packets.
    prefix_len = 0
    while all(len(p) > prefix_len for p in payloads) and len({p[prefix_len] for p in payloads}) == 1:
        prefix_len += 1
    print(f"  longest common prefix: {prefix_len} bytes = {payloads[0][:prefix_len]!r}")

    # Entropy: identifies encrypted vs plaintext regions.
    head_ent = _entropy(b"".join(p[:16] for p in payloads if len(p) >= 16))
    tail_ent = _entropy(b"".join(p[-16:] for p in payloads if len(p) >= 16))
    print(f"  entropy: head-16={head_ent:.2f} tail-16={tail_ent:.2f}" + (
        " (high entropy may indicate encryption)" if max(head_ent, tail_ent) > 7.5 else ""
    ))

    # Printable strings (candidate names/chats).
    strings = {p.decode("ascii", "ignore") for p in payloads if any(32 <= b < 127 for b in p)}
    for s in list(strings)[:10]:
        if len(s) >= 4:
            print(f"  printable candidate: {s!r}")


def from_jsonl(path: Path) -> list[bytes]:
    payloads, srcs = [], Counter()
    with path.open() as f:
        for line in f:
            rec = json.loads(line)
            if "payload" in rec:
                payloads.append(bytes(rec["payload"]))
                srcs[rec.get("src", "?")] += 1
    print(f"sources: {dict(srcs)}")
    return payloads


def from_pcap(path: Path) -> list[bytes]:
    payloads = []
    with path.open("rb") as f:
        f.read(24)  # global header
        while True:
            rec = f.read(16)
            if len(rec) < 16:
                break
            ts_s, ts_u, incl, _orig = struct.unpack("<IIII", rec)
            pkt = f.read(incl)
            if len(pkt) < incl:
                break
            if len(pkt) >= 34 and pkt[9] == 17:  # IPv4 UDP
                ihl = (pkt[0] & 0x0F) * 4
                payloads.append(pkt[ihl + 8:])
    return payloads


def port_sweep(host: str, ports: range, timeout: float = 0.5) -> None:
    """Send a UDP probe to each port; any response (ICMP unreachable suppressed
    here by design) suggests a live service. Pure reachability hint, nothing more."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    sock.bind(("0.0.0.0", 0))
    for port in ports:
        sock.sendto(b"\x00" * 8, (host, port))
        try:
            data, addr = sock.recvfrom(65536)
            print(f"  {host}:{port} -> response {len(data)} bytes")
        except socket.timeout:
            pass


def main() -> None:
    p = argparse.ArgumentParser(description="Mini Militia LAN capture probes (statistics only)")
    p.add_argument("file", help="capture.jsonl or capture.pcap")
    p.add_argument("--sweep", nargs=2, metavar=("HOST", "PORTSPEC"), help="port sweep, e.g. 192.168.43.1 44300-44320")
    p.add_argument("--tag", default="capture", help="label for output")
    args = p.parse_args()

    if args.sweep:
        host, spec = args.sweep
        a, b = spec.split("-")
        port_sweep(host, range(int(a), int(b) + 1))
        return

    path = Path(args.file)
    payloads = from_pcap(path) if path.suffix == ".pcap" else from_jsonl(path)
    probe_payloads(payloads, args.tag)


if __name__ == "__main__":
    main()
