"""ArbScoreboard -- grant tally plus the bandwidth statistical check.

Tally is unconditional (Phase 2 scope, still useful as a sanity check).
The bandwidth check (SPEC.md section 6) is explicitly a *statistical*
property over a sustained contention window, not a per-cycle invariant,
so it's a logged report rather than a hard assertion: call
`check_bandwidth()` after a sustained full-contention run (see
sequences.FullContentionSeq) to compare each class's actual grant share
against its target weight within a tolerance.
"""

from pyuvm import uvm_component, uvm_tlm_analysis_fifo

# Port map (SPEC.md section 2): 0 = COMPUTE, 1 = TEXTURE, 2 = DISPLAY
TARGET_SHARE = [0.5, 0.3, 0.2]
CLASS_NAME = ["COMPUTE", "TEXTURE", "DISPLAY"]
BANDWIDTH_TOLERANCE = 0.05


class ArbScoreboard(uvm_component):
    def build_phase(self):
        self.fifo = uvm_tlm_analysis_fifo("fifo", self)
        self.analysis_export = self.fifo.analysis_export
        self.get_port = self.fifo.get_export

    def start_of_simulation_phase(self):
        self.grant_count = [0, 0, 0]

    async def run_phase(self):
        while True:
            client, addr, contenders, aging_override, simultaneous_tiebreak = (
                await self.get_port.get()
            )
            self.grant_count[client] += 1
            self.logger.info(
                f"GRANT client={client} addr={hex(addr)} contenders={contenders} "
                f"aging_override={aging_override} simultaneous_tiebreak={simultaneous_tiebreak}"
            )

    def check_bandwidth(self, tolerance=BANDWIDTH_TOLERANCE):
        """Compare actual grant share per class against its target weight.

        Logs actual vs. target regardless of outcome -- useful data for
        the README even when a run is outside tolerance (e.g. while
        investigating whether the credit-based WRR scheme converges
        precisely enough; see PHASE3_PLAN.md section 5).
        """
        total = sum(self.grant_count)
        if total == 0:
            self.logger.warning("check_bandwidth: no grants observed, skipping")
            return {}

        results = {}
        for i in range(3):
            actual = self.grant_count[i] / total
            target = TARGET_SHARE[i]
            within_tolerance = abs(actual - target) <= tolerance
            results[CLASS_NAME[i]] = {
                "actual": actual,
                "target": target,
                "within_tolerance": within_tolerance,
            }
            self.logger.info(
                f"BANDWIDTH {CLASS_NAME[i]}: actual={actual:.1%} target={target:.0%} "
                f"tolerance=+/-{tolerance:.0%} "
                f"{'OK' if within_tolerance else 'OUT OF TOLERANCE'}"
            )
        return results

    def report_phase(self):
        total = sum(self.grant_count)
        self.logger.info(
            f"Grant tally: COMPUTE={self.grant_count[0]} "
            f"TEXTURE={self.grant_count[1]} "
            f"DISPLAY={self.grant_count[2]} (total={total})"
        )
