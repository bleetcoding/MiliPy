"""Round 5 honesty gate.

The Mini Militia LAN packet codec is UNKNOWN (no captures validated).
Connecting a Bot to a raw host address must therefore raise
CapabilityError rather than silently fabricating protocol support.
Tests never require Mini Militia, an Android device, or a network.
"""


import pytest

from milipy import Bot, SimAdapter, SimWorld
from milipy.protocol import CapabilityError


class TestLANProtocolGate:
    """Until LAN captures promote the codec to OBSERVED, the only honest
    behavior for Bot(<host-string>) is refusal with a clear reason."""

    @pytest.mark.asyncio
    async def test_connecting_to_raw_host_raises_capability_error(self):
        bot = Bot("192.168.43.1")
        with pytest.raises(CapabilityError, match="not yet implemented"):
            await bot.connect_async()

    @pytest.mark.asyncio
    async def test_error_message_points_at_research_document(self):
        bot = Bot("10.0.0.1", 9999)
        with pytest.raises(CapabilityError, match="lan-protocol-research.md"):
            await bot.connect_async()

    @pytest.mark.asyncio
    async def test_explicit_adapter_still_works(self):
        """The gate must not break the adapter-driven path (simulator)."""
        bot = Bot(SimAdapter(SimWorld()))
        await bot.connect_async()
        assert bot.is_connected
        await bot.disconnect_async()
