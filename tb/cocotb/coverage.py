"""ArbCoverage -- functional coverage model, built on cocotb-coverage.

Subscribes to the same monitor analysis port as the scoreboard (see
env.py) and samples one shared function call per grant with several
stacked CoverPoints/CoverCross, matching SPEC.md section 7's target
scenarios:
  - client_granted / contention_level / their cross: each class as sole
    requester, all three contending together.
  - aging_override_used: any class winning via the aging path.
  - simultaneous_aging_tiebreak: more than one client aged-out on the
    same decision (tie-break path).
  - repeated_aging_event (at_least=2 per class): confirms a class hits
    the aging path more than once, not just a single fluke crossing.

`coverage_db` (from cocotb_coverage) is a plain-Python singleton that
persists for the life of the process -- since pyuvm's report_phase/
final_phase run once *per test class*, not once per whole `make`
regression (multiple @pyuvm.test() classes share one simulation
process), the coverage report is exported via an `atexit` hook instead
so it happens exactly once, at the true end of the run, regardless of
which test happens to finish last.
"""

import atexit
import os

from pyuvm import uvm_component, uvm_tlm_analysis_fifo
from cocotb_coverage.coverage import CoverPoint, CoverCross, coverage_db

_RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "results")
_REPORT_TXT = os.path.join(_RESULTS_DIR, "coverage_before.txt")
_REPORT_YML = os.path.join(_RESULTS_DIR, "coverage_before.yml")


def _contention_bin(contenders):
    return {1: "solo", 2: "two-way", 3: "full"}.get(contenders)


@CoverPoint(
    "top.client_granted",
    xf=lambda client, contenders, aging_override, tiebreak: client,
    bins=[0, 1, 2],
)
@CoverPoint(
    "top.contention_level",
    xf=lambda client, contenders, aging_override, tiebreak: _contention_bin(contenders),
    bins=["solo", "two-way", "full"],
)
@CoverPoint(
    "top.aging_override_used",
    xf=lambda client, contenders, aging_override, tiebreak: aging_override,
    bins=[True, False],
)
@CoverPoint(
    "top.simultaneous_aging_tiebreak",
    xf=lambda client, contenders, aging_override, tiebreak: tiebreak,
    bins=[True, False],
)
@CoverCross(
    "top.client_x_contention",
    items=["top.client_granted", "top.contention_level"],
)
def sample_grant(client, contenders, aging_override, tiebreak):
    pass


@CoverPoint(
    "top.repeated_aging_event",
    xf=lambda client: client,
    bins=[0, 1, 2],
    at_least=2,
)
def sample_aging_event(client):
    pass


def _export_coverage_report():
    os.makedirs(_RESULTS_DIR, exist_ok=True)
    with open(_REPORT_TXT, "w") as f:
        coverage_db.report_coverage(lambda msg: f.write(msg + "\n"), bins=True)
    coverage_db.export_to_yaml(filename=_REPORT_YML)


atexit.register(_export_coverage_report)


class ArbCoverage(uvm_component):
    def build_phase(self):
        self.fifo = uvm_tlm_analysis_fifo("fifo", self)
        self.analysis_export = self.fifo.analysis_export
        self.get_port = self.fifo.get_export

    async def run_phase(self):
        while True:
            client, addr, contenders, aging_override, tiebreak = await self.get_port.get()
            sample_grant(client, contenders, aging_override, tiebreak)
            if aging_override:
                sample_aging_event(client)
