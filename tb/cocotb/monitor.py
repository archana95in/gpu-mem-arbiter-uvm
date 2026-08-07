"""ArbMonitor -- passively watches gnt/gnt_addr and publishes a grant
transaction for every grant observed. Downstream consumers: the
scoreboard (tally/bandwidth check) and the coverage collector.

Phase 3 note: besides the blackbox (client, addr) pair, the published
tuple also carries a few whitebox facts needed for coverage bins that
SPEC.md defines in terms of internal arbiter state (aging override,
simultaneous tie-break) rather than anything visible on the pin-level
interface:
  - `contenders`: how many clients had `req` asserted going into the
    decision that produced this grant.
  - `aging_override`: whether the granted client won via the aging path
    rather than weighted round robin.
  - `simultaneous_tiebreak`: whether more than one client was aged-out
    on that same decision.

These are peeked via internal hierarchical signals (`dut.u_dut.age`,
`dut.u_dut.busy_cnt`), not new DUT ports -- the pin-level interface in
SPEC.md section 3 is unchanged. `age`/`busy_cnt` are peeked rather than
the combinational `aged_out` signal deliberately: they're real
registers, so their value is stable for an entire clock cycle and can
be read with a plain post-RisingEdge snapshot -- the same safe pattern
already used for `gnt` below. An earlier version of this monitor tried
to sample `aged_out` (purely combinational) via `ReadOnly()` timed to
land just before the decision edge; that ordering turned out to
actually land just *after* it instead (confirmed by dumping raw values:
grants showed up paired with `busy_cnt==3`, which is only possible
immediately after a grant, not before one), silently zeroing every
aging_override detection. Registers don't have that ordering hazard.

Phase 4 note: COCOTB_TOPLEVEL points at gpu_mem_arbiter_tb_top (a thin
wrapper needed because Icarus doesn't implement `bind` -- see
tb/sva/gpu_mem_arbiter_assertions.sv), not at gpu_mem_arbiter directly
anymore. clk/req/gnt/etc. are forwarded through at the wrapper's own
boundary under the same names, so those references are unchanged; only
age/busy_cnt (internal-only, no port) need the extra `.u_dut.` hop to
reach the real DUT instance inside the wrapper.
"""

from pyuvm import uvm_component, uvm_analysis_port, ConfigDB
from cocotb.triggers import RisingEdge

# Port map (SPEC.md section 2): 0 = COMPUTE, 1 = TEXTURE, 2 = DISPLAY
AGE_THRESHOLD = [32, 16, 8]


class ArbMonitor(uvm_component):
    def build_phase(self):
        self.dut = ConfigDB().get(self, "", "DUT")
        self.ap = uvm_analysis_port("ap", self)

    async def run_phase(self):
        dut = self.dut
        num_clients = len(AGE_THRESHOLD)
        prev_age = [0] * num_clients
        prev_busy = 0
        prev_req = 0

        while True:
            await RisingEdge(dut.clk)

            if dut.gnt.value.is_resolvable:
                gnt_val = int(dut.gnt.value)
                if gnt_val:
                    # index of the single set bit (gnt is one-hot by
                    # design -- this will surface a bug loudly if
                    # that's ever violated)
                    client = (gnt_val & -gnt_val).bit_length() - 1
                    addr = int(dut.gnt_addr.value)
                    contenders = bin(prev_req).count("1")
                    aged_out_clients = [
                        i for i in range(num_clients) if prev_age[i] >= AGE_THRESHOLD[i]
                    ]
                    aging_override = (prev_busy == 0) and (client in aged_out_clients)
                    simultaneous_tiebreak = aging_override and len(aged_out_clients) >= 2

                    self.ap.write((client, addr, contenders, aging_override, simultaneous_tiebreak))

            # Snapshot registers right after this edge -- they're
            # stable for the entire next cycle, so this becomes the
            # correct "going into the decision" state for whatever
            # grant (if any) appears at the *next* RisingEdge.
            for i in range(num_clients):
                if dut.u_dut.age[i].value.is_resolvable:
                    prev_age[i] = int(dut.u_dut.age[i].value)
            if dut.u_dut.busy_cnt.value.is_resolvable:
                prev_busy = int(dut.u_dut.busy_cnt.value)
            if dut.req.value.is_resolvable:
                prev_req = int(dut.req.value)
