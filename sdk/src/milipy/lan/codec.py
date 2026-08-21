"""MiniMilitiaCodec — turns raw LAN datagrams into Bot frames.

HONEST STATUS (Aug 2026): the Mini Militia LAN packet format is UNKNOWN.
This file contains:

- ``LANPacket``: a typed wrapper for a raw datagram + its decoded fields.
- ``MiniMilitiaCodec``: the parse/encode entry points the adapter calls.
- ``_decode_packet`` / ``_encode_packet``: deliberately NOT IMPLEMENTED —
  they raise ``NotImplementedError`` with the exact field layout that MUST
  be filled in from PCAP evidence (see
  ``protocol/lan-protocol-research.md`` and ``protocol/research/pcap_report.py``).

Filling rule: a field may only be documented in this file when it has the
OBSERVED tag in the research notes, i.e. it was read byte-for-byte from a
capture AND a replay/send of the same bytes produced the expected effect on
a real Mini Militia host. Until then, any guess silently corrupts the game
state and gets the bot kicked or banned from LAN lobbies.

Once a real packet format is proven, the scaffold ``to_frame`` mapping also
needs replacing — it currently emits JSON frames so the Bot's existing
event machinery works for testing the adapter wiring.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LANPacket:
    """One raw LAN datagram with the fields we expect to decode.

    Fields are all UNKNOWN until proven by capture evidence. Their types
    (uint8 tag, float positions, etc.) are placeholders matching the current
    public-source INFERRED guesses in ``protocol/lan-protocol-research.md``.
    """

    raw: bytes
    peer: tuple[str, int] = ("", 0)
    packet_type: int = -1  # UNKNOWN — guessed tag byte
    payload: bytes = b""


class MiniMilitiaCodec:
    """Codec between raw Mini Militia LAN bytes and Bot frames.

    The codec is intentionally NOT_IMPLEMENTED for real packets: every
    decode/encode of an actual game packet raises ``NotImplementedError``.
    This forces the honest failure mode — the bot never pretends to
    understand bytes it has never seen.

    Set :attr:`discovery_payload` with the exact bytes Mini Militia sends in
    its discovery broadcast (from a PCAP) to enable LAN discovery.
    """

    def __init__(self) -> None:
        self.discovery_payload: bytes = b""  # UNKNOWN until capture evidence

    # -- Public entry points (adapter-facing) ----------------------------------

    def parse(self, data: bytes, addr: tuple[str, int]) -> LANPacket:
        """Decode one inbound datagram. Raises ``NotImplementedError`` until
        the real format is proven (see ``_decode_packet``)."""
        packet = self._decode_packet(data, addr)
        if packet is None:
            raise NotImplementedError(
                "LAN packet format is UNKNOWN — cannot decode "
                f"{len(data)} bytes from {addr}. Set codec fields only from "
                "capture evidence (protocol/lan-protocol-research.md)."
            )
        return packet

    def encode(self, message: dict[str, Any]) -> bytes:
        """Encode a Bot action into a LAN datagram. Raises
        ``NotImplementedError`` until the real format is proven."""
        payload = self._encode_packet(message)
        if payload is None:
            raise NotImplementedError(
                "LAN packet format is UNKNOWN — cannot encode action "
                f"{message.get('action')!r}. See protocol/lan-protocol-research.md."
            )
        return payload

    def to_frame(self, packet: LANPacket, addr: tuple[str, int]) -> dict[str, Any] | None:
        """Map a decoded packet to a Bot JSON frame.

        Scaffold mapping: state packets → ``state`` frames, player events →
        ``event`` frames. Replace entirely with the real mapping once the
        protocol is OBSERVED.
        """
        # SCAFFOLD ONLY: keep the Bot event loop exercisable before the real
        # format exists. Never ship this mapping as "protocol support".
        if packet.packet_type == -1:
            return None
        return {
            "type": "event",
            "event": "lan_packet_raw",
            "data": {
                "peer": {"ip": addr[0], "port": addr[1]},
                "packet_type": packet.packet_type,
                "hex": packet.payload.hex(),
            },
        }

    # -- To be filled from capture evidence -------------------------------------

    def _decode_packet(self, data: bytes, addr: tuple[str, int]) -> LANPacket | None:
        """Decode raw bytes into a typed LANPacket.

        REQUIRED (from PCAP evidence, fill in order):
          1. Packet header: length/structure (is there a fixed-size header?).
          2. Message tag byte(s): which byte selects move/join/fire/chat?
          3. Join handshake: magic bytes + lobby token location.
          4. Player identity: where the player name/avatar/id live.
          5. Position: encoding (fixed-point? float? pixel coords?) and axis order.
          6. Movement flags: crouch/jump/fly — bitfield or separate packets?
          7. Fire: trigger packet format + projectile parameters.
          8. Damage/death: who encodes it, host or client?
          9. Sequence numbers: is there a monotonic counter to skip/reorder?
          10. Checksum/encryption: are bytes XOR'd, CRC'd, or plaintext?

        Returns None for unrecognized datagrams (e.g. non-game UDP noise).
        Until all items above are OBSERVED, always returns None.
        """
        return None  # UNKNOWN — do not implement without capture evidence

    def _encode_packet(self, message: dict[str, Any]) -> bytes | None:
        """Encode a Bot action dict into a LAN datagram.

        REQUIRED (from PCAP evidence): the exact byte layout Mini Militia
        expects for each action, in the same order as ``_decode_packet``
        above. Never guess endianness or tag values.

        Until then, always returns None.
        """
        return None  # UNKNOWN — do not implement without capture evidence
