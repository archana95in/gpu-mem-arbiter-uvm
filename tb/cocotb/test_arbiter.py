"""SmokeTest -- Phase 2 entry point.

Runs one FullContentionSeq through the full UVM skeleton (sequencer ->
driver -> DUT -> monitor -> scoreboard) and confirms grants come out the
other side. Purpose-equivalent to the Phase-1 RTL-only smoke test, but
now exercising the UVM chain instead of a bare testbench module.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
import pyuvm
from pyuvm import uvm_test, ConfigDB

from env import ArbEnv
from sequences import FullContentionSeq


@pyuvm.test()
class SmokeTest(uvm_test):
    def build_phase(self):
        ConfigDB().set(None, "*", "DUT", cocotb.top)
        self.env = ArbEnv("env", self)

    async def run_phase(self):
        self.raise_objection()

        dut = cocotb.top
        dut.rst_n.value = 0
        dut.req.value = 0
        for i in range(3):
            dut.addr[i].value = 0

        cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

        await RisingEdge(dut.clk)
        await RisingEdge(dut.clk)
        dut.rst_n.value = 1
        await RisingEdge(dut.clk)

        seq = FullContentionSeq("seq")
        seqr = ConfigDB().get(None, "", "SEQR")
        await seq.start(seqr)

        self.drop_objection()
