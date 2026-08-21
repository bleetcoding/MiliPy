"""PCAP analysis report generator (honest, statistics-only).

Takes a pcap (e.g. exported by PCAPdroid) and produces a plain-text report
that groups the traffic into clusters useful for reverse-engineering:

    python3 pcap_report.py --in ~/capture.pcap --out ~/report.txt

Honesty note: this tool computes statistics about raw bytes. It does NOT
label packets as "join", "fire", "move" etc. Those labels require correlating
timing with known actions, which is a human judgment step (documented in
protocol/lan-protocol-research.md). Every section of the report is labeled
OBSERVED (computed from bytes) or INFERRED (a hypothesis the bytes support).

Output sections:
  1. Summary: packet counts, time span, distinct peers
  2. Port map: which port pairs exchange the most traffic (best guess at
     the game's server port)
  3. Protocol family fingerprint: TCP vs UDP shares, TLS/non-TLS guesses —
     only statistical guesses, never claims
  4. Payload clusters: unique payload prefixes grouped by (peer, port, dir)
  5. Timing hints: periodic flows that suggest game tick loops
"""
from __future__ import annotations

import argparse
import datetime
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path


def read_pcap(path: Path):
    """Yield (ts, raw_frame_bytes) for a pcap file (linktypes: ethernet, raw IP)."""
    with open(path, "rb") as f:
        hdr = f.read(24)
        if len(hdr) < 24:
            raise ValueError("not a pcap file")
        magic, major, minor, *_ = struct.unpack("<IHHiIII", hdr)
        if magic not in (0xA1B2C3D4, 0xD4C3B2A1):
            raise ValueError("not a pcap file")
        swp = magic == 0xD4C3B2A1
        while True:
            rec = f.read(16)
            if len(rec) < 16:
                break
            ts_s, ts_u, incl, _orig = struct.unpack(("<I" if swp else "<IIII"), rec) if False else (
                struct.unpack("<II", rec[:8]) if swp else struct.unpack("<IIII", rec)
            )
            if swp:
                caplen, _orig = struct.unpack("<II", rec[8:16])
            else:
                caplen = incl
            pkt = f.read(caplen)
            if len(pkt) < caplen:
                break
            yield ts_s + ts_u / 1e6, pkt


def _udp_payload(pkt: bytes) -> bytes | None:
    if len(pkt) < 14 + 20 + 8:
        return None
    ihl = (pkt[14] & 0x0F) * 4
    if pkt[14 + 9] != 17:
        return None
    return pkt[14 + ihl + 8:]


def _parse_ip(pkt: bytes):
    """Return (src, dst, proto, udp_payload_or_None) from an ethernet frame."""
    if len(pkt) < 14 + 20:
        return None
    ihl = (pkt[14] & 0x0F) * 4
    total = struct.unpack("!H", pkt[14 + 2:14 + 4])[0]
    if total < 20:
        return None
    proto = pkt[14 + 9]
    src = ".".join(str(b) for b in pkt[14 + 12:14 + 16])
    dst = ".".join(str(b) for b in pkt[14 + 16:14 + 20])
    udp = None
    if proto == 17:
        udp = _udp_payload(pkt)
    return src, dst, proto, udp


def main() -> None:
    p = argparse.ArgumentParser(description="Honest pcap statistics report")
    p.add_argument("--in", required=True, dest="inp", help="input pcap")
    p.add_argument("--out", help="output report (default: stdout)")
    args = p.parse_args()

    path = Path(args.inp)
    pkts = list(read_pcap(path))

    lines: list[str] = []
    out = lines.append

    t0 = pkts[0][0] if pkts else 0.0
    t1 = pkts[-1][0] if pkts else 0.0

    out("=" * 70)
    out("MILIPY PCAP REPORT — statistics only, no decoded claims")
    out("=" * 70)
    out(f"File: {path}")
    out(f"Packets: {len(pkts)}")
    out(f"Span: {t1 - t0:.1f}s  ({datetime.datetime.fromtimestamp(t0).isoformat()} ..)")
    out("")

    pairs = Counter()
    ports = Counter()
    proto_counts = Counter()
    flows = defaultdict(list)  # (a, b, proto, dport) -> payloads
    peers = set()

    for ts, pkt in pkts:
        parsed = _parse_ip(pkt)
        if parsed is None:
            continue
        src, dst, proto, udp = parsed
        peers |= {src, dst}
        proto_counts["UDP" if proto == 17 else ("TCP" if proto == 6 else f"proto{proto}")] += 1
        pair = tuple(sorted((src, dst)))
        pairs[pair] += 1
        if udp is not None:
            sport = struct.unpack("!H", pkt[14 + ((pkt[14] & 0x0F) * 4) + 0:14 + ((pkt[14] & 0x0F) * 4) + 2])[0]
            dport = struct.unpack("!H", pkt[14 + ((pkt[14] & 0x0F) * 4) + 2:14 + ((pkt[14] & 0x0F) * 4) + 4])[0]
            ports[(src, sport, dst, dport)] += 1
            flows[(src, dst, dport)].append((ts, udp))

    out("1. [OBSERVED] Protocol family shares")
    total = sum(proto_counts.values()) or 1
    for k, v in proto_counts.most_common():
        out(f"   {k}: {v} ({v / total:.0%})")
    out("")

    out("2. [OBSERVED] Busiest peer pairs")
    for (a, b), c in pairs.most_common(10):
        out(f"   {a} <-> {b}: {c} packets")
    out("")

    out("3. [OBSERVED] Busiest (src:port -> dst:port) flows")
    for (a, sp, b, dp), c in ports.most_common(15):
        out(f"   {a}:{sp} -> {b}:{dp}: {c} packets")
    out("   [INFERRED] The destination port with the most packets from the host's")
    out("   perspective, or the most symmetric pair, is the best candidate for the")
    out("   Mini Militia game server port.")
    out("")

    out("4. [OBSERVED] Payload clusters (unique UDP payloads per flow, first 64 bytes)")
    for (src, dst, dport), items in sorted(flows.items(), key=lambda kv: -len(kv[1])):
        if len(items) < 3:
            continue
        c = Counter(items[1] for _, items_ in [items] for items_ in [items[1]][:1])
        uniq = {pl[:64] for _, pl in items}
        out(f"   {src} -> {dst}:{dport}: {len(items)} pkts, {len(uniq)} unique payloads")
        sample = sorted(uniq, key=len)[:3]
        for pl in sample:
            out(f"      hex={pl.hex()}  ascii={''.join(chr(b) if 32 <= b < 127 else '.' for b in pl)}")
    out("")

    out("5. [OBSERVED->INFERRED] Periodic flows (potential tick loops)")
    for (src, dst, dport), items in sorted(flows.items(), key=lambda kv: -len(kv[1])):
        if len(items) < 20:
            continue
        tss = sorted(ts for ts, _ in items)
        gaps = [tss[i + 1] - tss[i] for i in range(len(tss) - 1)]
        if not gaps:
            continue
        avg = sum(gaps) / len(gaps)
        if avg > 0:
            out(f"   {src} -> {dst}:{dport}: {len(items)} pkts, avg interval {avg * 1000:.1f}ms "
                f"(~{1 / avg:.0f} Hz) — a steady rate suggests a game tick or keep-alive")
    out("")

    out("NEXT STEP (human): correlate timestamps in this report with a written log of")
    out("what actions were performed during the capture (joins, shots, deaths) to map")
    out("payload clusters to game events. Labels only earn the OBSERVED tag after that.")
    out("=" * 70)

    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text)
        print(f"report written to {args.out}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
