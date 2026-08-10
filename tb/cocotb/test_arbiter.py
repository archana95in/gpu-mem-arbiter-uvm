"""Phase 2/3 regression for gpu_mem_arbiter.

Runs every Phase 3 scenario (sequences.py) through the full UVM chain
(per-client agents -> DUT -> monitor -> scoreboard + coverage) and
confirms the expected behavior: real contention (multiple clients
holding req at once), aging-override grants, and a first functional
coverage report exported to results/ (see coverage.py's atexit hook).

This is ONE @pyuvm.test() class, not one per scenario. That's a
deliberate departure from the original plan: pyuvm forks each
component's run_phase via a bare `cocotb.start_soon()`
(pyuvm/s09_phasing.py:106) and never stores or cancels the returned
Task. Nothing kills a finished test's driver/monitor coroutines, so
with separate @pyuvm.test() classes they keep running into the *next*
test's simulation time and crash the simulator (confirmed empirically:
a scenario passes standalone but crashes with "Simulator shut down
prematurely" -- no Python traceback, since it isn't a catchable
exception -- as soon as it runs right after another test class in the
same regression). One long-lived env for the whole run, with
`reset_dut` between scenario phases, sidesteps the issue entirely --
the agents are the same live objects throughout, never orphaned.
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
import pyuvm
from pyuvm import uvm_test, ConfigDB

from env import ArbEnv
from sequences import (
    SoloRequestSeq,
    FullContentionSeq,
    AgingStressSeq,
    RepeatedAgingSeq,
    SimultaneousAgingSeq,
    RandomContentionSeq,
    TargetedAgingSeq,
)


async def reset_dut(dut):
    dut.rst_n.value = 0
    dut.req.value = 0
    for i in range(3):
        dut.addr[i].value = 0

    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


@pyuvm.test()
class ArbiterRegressionTest(uvm_test):
    """One env for the whole regression; each SPEC.md section 7 scenario
    runs as a sequential phase, resetting DUT state in between."""

    def build_phase(self):
        ConfigDB().set(None, "*", "DUT", cocotb.top)
        self.env = ArbEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        dut = cocotb.top
        cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

        self.logger.info("--- SmokeTest: one concurrent request per client ---")
        await reset_dut(dut)
        tasks = [
            cocotb.start_soon(SoloRequestSeq(client, 1, 0x1000 * client).start(
                ConfigDB().get(None, "", "SEQRS")[client]))
            for client in (0, 1, 2)
        ]
        for t in tasks:
            await t

        self.logger.info("--- SoloRequestSeq: each class as sole requester ---")
        await reset_dut(dut)
        for client in (0, 1, 2):
            seqr = ConfigDB().get(None, "", "SEQRS")[client]
            seq = SoloRequestSeq(client, num_requests=5, addr_base=0x1000 * client)
            await seq.start(seqr)

        self.logger.info("--- FullContentionSeq: all three classes contending ---")
        await reset_dut(dut)
        self.env.scoreboard.grant_count = [0, 0, 0]  # clean tally for the bandwidth window
        await FullContentionSeq(num_decisions=10_000).run()
        self.env.scoreboard.check_bandwidth()

        self.logger.info("--- AgingStressSeq: DISPLAY held against COMPUTE+TEXTURE flood ---")
        await reset_dut(dut)
        await AgingStressSeq(num_requests=200).run()

        self.logger.info("--- TargetedAgingSeq: COMPUTE pushed to its own age threshold (x2, for repeated_aging_event) ---")
        for _ in range(2):
            await reset_dut(dut)
            await TargetedAgingSeq(target=0, solo_decisions=50, contend_decisions=50, periodic_period=3).run()

        self.logger.info("--- TargetedAgingSeq: TEXTURE pushed to its own age threshold (x2, for repeated_aging_event) ---")
        for _ in range(2):
            await reset_dut(dut)
            await TargetedAgingSeq(target=1, solo_decisions=25, contend_decisions=25, periodic_period=3).run()

        self.logger.info("--- RepeatedAgingSeq: each class held >2x its own age threshold ---")
        for client in (0, 1, 2):
            await reset_dut(dut)
            await RepeatedAgingSeq(client).run()

        self.logger.info("--- SimultaneousAgingSeq: staggered TEXTURE/DISPLAY aging ---")
        await reset_dut(dut)
        await SimultaneousAgingSeq().run()

        self.logger.info("--- RandomContentionSeq: randomized per-client req toggling ---")
        await reset_dut(dut)
        await RandomContentionSeq(num_decisions=2000).run()

        self.drop_objection()
