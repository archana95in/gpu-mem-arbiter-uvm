"""ArbEnv -- wires the agent (sequencer + driver + monitor) and the
scoreboard together. See the UVM primer in this project's history for
what each piece does; this mirrors that structure directly.
"""

from pyuvm import uvm_env, uvm_sequencer, ConfigDB
from driver import ArbDriver
from monitor import ArbMonitor
from scoreboard import ArbScoreboard


class ArbEnv(uvm_env):
    def build_phase(self):
        self.seqr = uvm_sequencer("seqr", self)
        ConfigDB().set(None, "*", "SEQR", self.seqr)
        self.driver = ArbDriver("driver", self)
        self.monitor = ArbMonitor("monitor", self)
        self.scoreboard = ArbScoreboard("scoreboard", self)

    def connect_phase(self):
        self.driver.seq_item_port.connect(self.seqr.seq_item_export)
        self.monitor.ap.connect(self.scoreboard.analysis_export)
