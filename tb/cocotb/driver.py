"""ArbDriver -- drives one client's req/addr lines per ArbReqItem and
waits for that client's grant bit before completing the item.

`req` and `gnt` are packed bit vectors on the DUT (logic [NUM_CLIENTS-1:0]),
so they're manipulated as plain integers/bitmasks here. `addr` is an
unpacked array port, indexed directly per client.
"""

from pyuvm import uvm_driver, ConfigDB
from cocotb.triggers import RisingEdge


class ArbDriver(uvm_driver):
    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")

    async def run_phase(self):
        while True:
            item = await self.seq_item_port.get_next_item()
            await self._drive(item)
            self.seq_item_port.item_done()

    async def _drive(self, item):
        dut = self.dut

        dut.addr[item.client].value = item.addr
        dut.req.value = int(dut.req.value) | (1 << item.client)

        await RisingEdge(dut.clk)
        while not ((int(dut.gnt.value) >> item.client) & 1):
            await RisingEdge(dut.clk)

        dut.req.value = int(dut.req.value) & ~(1 << item.client)
