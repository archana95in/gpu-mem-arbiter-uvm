"""ArbEnv -- wires 3 per-client agents (sequencer + driver each) plus the
shared monitor, scoreboard, and coverage collector together.

Phase 3 note: Phase 2 had one global sequencer/driver pair servicing
items for any client, one at a time -- that made it impossible to ever
have two clients hold `req` simultaneously, so no real contention could
be driven. One agent per client port (as PROJECT_PLAN.md's Phase 2
section originally called for) fixes that: each client's driver runs
independently and can hold `req` for as long as its sequence wants,
concurrently with the other two.
"""

from pyuvm import uvm_env, uvm_sequencer, ConfigDB
from driver import ArbDriver
from monitor import ArbMonitor
from scoreboard import ArbScoreboard
from coverage import ArbCoverage
from req_bus import ReqBus

CLIENTS = (0, 1, 2)  # COMPUTE, TEXTURE, DISPLAY -- see SPEC.md section 2


class ArbEnv(uvm_env):
    def build_phase(self):
        dut = ConfigDB().get(self, "", "DUT")
        ConfigDB().set(None, "*", "REQ_BUS", ReqBus(dut))

        self.seqr = {}
        self.driver = {}
        for client in CLIENTS:
            self.seqr[client] = uvm_sequencer(f"seqr{client}", self)
            self.driver[client] = ArbDriver(f"driver{client}", self, client=client)
        ConfigDB().set(None, "*", "SEQRS", self.seqr)

        self.monitor = ArbMonitor("monitor", self)
        self.scoreboard = ArbScoreboard("scoreboard", self)
        self.coverage = ArbCoverage("coverage", self)

    def connect_phase(self):
        for client in CLIENTS:
            self.driver[client].seq_item_port.connect(self.seqr[client].seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
        self.monitor.ap.connect(self.coverage.analysis_export)
