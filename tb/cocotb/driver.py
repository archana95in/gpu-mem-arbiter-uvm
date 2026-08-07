"""ArbDriver -- drives ONE client's req/addr lines per ArbReqItem and
waits for that client's grant bit before completing the item.

Phase 3 note: each ArbDriver instance is bound to a single client at
construction (one instance per agent/port). This is what lets multiple
clients hold `req` at the same time -- Phase 2 had a single driver
servicing items for any client one at a time through one sequencer,
which made real contention undrivable. `addr` is an unpacked array port,
indexed directly per client; `req`/`gnt` are packed bit vectors, handled
via ReqBus / plain bitmask reads respectively.
"""

from pyuvm import uvm_driver, ConfigDB
from cocotb.triggers import RisingEdge


class ArbDriver(uvm_driver):
    def __init__(self, name, parent, client):
        super().__init__(name, parent)
        self.client = client

    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.req_bus = ConfigDB().get(self, "", "REQ_BUS")

    async def run_phase(self):
        while True:
            item = await self.seq_item_port.get_next_item()
            await self._drive(item)
            self.seq_item_port.item_done()

    async def _drive(self, item):
        dut = self.dut
        client = self.client

        dut.addr[client].value = item.addr
        self.req_bus.assert_req(client)

        await RisingEdge(dut.clk)
        while not ((int(dut.gnt.value) >> client) & 1):
            await RisingEdge(dut.clk)

        self.req_bus.deassert_req(client)
