"""ArbMonitor -- passively watches gnt/gnt_addr and publishes a
(client, addr) transaction for every grant observed. Downstream
consumer: the scoreboard.
"""

from pyuvm import uvm_component, uvm_analysis_port, ConfigDB
from cocotb.triggers import RisingEdge


class ArbMonitor(uvm_component):
    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.ap = uvm_analysis_port("ap", self)

    async def run_phase(self):
        dut = self.dut
        while True:
            await RisingEdge(dut.clk)
            if not dut.gnt.value.is_resolvable:
                continue  # reset transient -- no valid grant to report
            gnt_val = int(dut.gnt.value)
            if gnt_val:
                # index of the single set bit (gnt is one-hot by design --
                # this will surface a bug loudly if that's ever violated)
                client = (gnt_val & -gnt_val).bit_length() - 1
                self.ap.write((client, int(dut.gnt_addr.value)))
