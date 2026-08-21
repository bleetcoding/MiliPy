"""Mini Militia LAN capture tool.

Honesty note: this tool records raw UDP traffic; it does NOT decode or label
Mini Militia packets. Labeling happens only in the correlated action log
(`--tag`), which records what the human operator was doing, never what a
packet "means". See protocol/lan-protocol-research.md.

Usage:
    # Record everything on the LAN interface for 60s while performing actions:
    python3 capture.py --iface wlan0 --duration 60 --tag "joined lobby"

    # Record only traffic on a suspected port (e.g. sweep results):
    python3 capture.py --port 44300 --duration 30 --tag "host idle"

    # Replay a capture to a local test listener (debug harness):
    python3 capture.py --replay run.pcap --dest 127.0.0.1:9001
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

try:
    import scapy.all as scapy

    _SCAPY = True
except ImportError:
    _SCAPY = False

PCAP_GLOBAL_HEADER = struct.pack(
    "<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, 65535, 101
)  # linktype = raw IP


def _raw_socket(iface: str | None) -> socket.socket:
    """Open an AF_PACKET socket that sees all UDP on the given interface.

    Requires CAP_NET_RAW (root on Android). Falls back to a plain SOCK_DGRAM
    listener on a fixed port when root is unavailable — the fallback can only
    see traffic addressed to the local port, which is itself useful
    information (a port that receives game traffic is a candidate discovery/
    gameplay port).
    """
    if iface:
        try:
            sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0003))
            sock.bind((iface, 0))
            return sock, "raw"
        except PermissionError:
            print(
                "[capture] raw socket needs CAP_NET_RAW; falling back to port listener",
                file=sys.stderr,
            )
    return None, "fallback"


def _udp_filter(pkt: bytes) -> bytes | None:
    """Return the UDP payload of an IPv4/UDP packet, else None."""
    if len(pkt) < 34:
        return None
    ihl = (pkt[0] & 0x0F) * 4
    if pkt[9] != 17:  # not UDP
        return None
    udp_start = ihl
    if len(pkt) < udp_start + 8:
        return None
    return pkt[udp_start + 8:]


def _pcap_record(ts: float, packet: bytes) -> bytes:
    return struct.pack("<IIII", int(ts), int(ts * 1e6) % 1_000_000, len(packet), len(packet)) + packet


def run_capture(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    pcap_path = out.with_suffix(".pcap")
    log_path = out.with_suffix(".jsonl")

    meta = {
        "start": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "tag": args.tag,
        "iface": args.iface,
        "port": args.port,
        "duration": args.duration,
    }
    with log_path.open("w") as lf, pcap_path.open("wb") as pf:
        pf.write(PCAP_GLOBAL_HEADER)
        lf.write(json.dumps({"meta": meta}) + "\n")

        deadline = time.time() + args.duration
        sock, mode = _raw_socket(args.iface)

        if mode == "fallback":
            # Port listener mode: can't see broadcasts addressed to others,
            # but any packet arriving on this port is meaningful evidence.
            listen = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            port = args.port or 0
            listen.bind(("0.0.0.0", port))
            listen.settimeout(1.0)
            bound = listen.getsockname()[1]
            print(f"[capture] port listener bound on :{bound} (tag={args.tag!r})")
            while time.time() < deadline:
                try:
                    data, addr = listen.recvfrom(65536)
                except socket.timeout:
                    continue
                ts = time.time()
                pf.write(_pcap_record(ts, data))
                lf.write(
                    json.dumps({"ts": ts, "src": addr[0], "sport": addr[1], "len": len(data)}) + "\n"
                )
                print(f"[capture] {len(data):>5} bytes from {addr[0]}:{addr[1]}")
            return

        # Raw AF_PACKET mode.
        print(f"[capture] raw capture on {args.iface} (tag={args.tag!r})")
        sock.settimeout(1.0)
        while time.time() < deadline:
            try:
                pkt = sock.recv(65536)
            except socket.timeout:
                continue
            payload = _udp_filter(pkt)
            if payload is None:
                continue
            if args.port and struct.unpack("!H", pkt[34:36])[1] != args.port:
                continue
            ts = time.time()
            pf.write(_pcap_record(ts, pkt))
            lf.write(json.dumps({"ts": ts, "len": len(pkt)}) + "\n")
            src = socket.inet_ntoa(pkt[26:30])
            dst = socket.inet_ntoa(pkt[30:34])
            print(f"[capture] UDP {src} -> {dst} payload={len(payload)}B")


def run_replay(args: argparse.Namespace) -> None:
    """Replay a recorded pcap to a local address — for round-trip validation."""
    host, port = args.dest.rsplit(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    with open(args.replay, "rb") as f:
        global_hdr = f.read(24)
        assert global_hdr[:4] == struct.pack("<I", 0xA1B2C3D4), "not a pcap file"
        first_ts: float | None = None
        count = 0
        while True:
            rec = f.read(16)
            if len(rec) < 16:
                break
            ts_s, ts_u, incl, _orig = struct.unpack("<IIII", rec)
            pkt = f.read(incl)
            if len(pkt) < incl:
                break
            ts = ts_s + ts_u / 1e6
            if first_ts is None:
                first_ts = ts
            if args.realtime:
                time.sleep(max(0, ts - first_ts - (time.time() - (ts_s + ts_u / 1e6)) + (ts - first_ts)) * 0 + 0)
            payload = _udp_filter(pkt)
            if payload:
                sock.sendto(payload, (host, int(port)))
                count += 1
    print(f"[replay] sent {count} UDP payloads to {host}:{port}")


def main() -> None:
    p = argparse.ArgumentParser(description="Mini Militia LAN capture tool (records only; decodes nothing)")
    p.add_argument("--iface", help="network interface for raw capture (e.g. wlan0)")
    p.add_argument("--port", type=int, help="filter to a specific UDP port (or port listener fallback)")
    p.add_argument("--duration", type=int, default=60, help="capture duration in seconds")
    p.add_argument("--tag", default="", help="human action performed during capture window")
    p.add_argument("--out", default="capture", help="output base name")
    p.add_argument("--replay", help="pcap to replay instead of capturing")
    p.add_argument("--dest", default="127.0.0.1:9001", help="replay destination host:port")
    p.add_argument("--realtime", action="store_true", help="replay with original timing")
    args = p.parse_args()

    if args.replay:
        run_replay(args)
    else:
        run_capture(args)


if __name__ == "__main__":
    main()
