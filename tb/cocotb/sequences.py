"""Sequences for gpu_mem_arbiter.

Phase 2 scope: just enough to prove the UVM skeleton (sequencer -> driver
-> DUT -> monitor -> scoreboard) is wired up correctly. Real constrained-
random stimulus and the functional coverage model are added in Phase 3.
"""

from pyuvm import uvm_sequence
from seq_item import ArbReqItem


class FullContentionSeq(uvm_sequence):
    """All three clients issue one request each, back-to-back, so they
    contend for the bus. Equivalent in purpose to the Phase-1 RTL-only
    smoke test."""

    async def body(self):
        for client in range(3):
            item = ArbReqItem(client=client, addr=0x1000 * client)
            await self.start_item(item)
            await self.finish_item(item)
