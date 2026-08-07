"""ArbScoreboard -- Phase 2 scope.

For now this just tallies grants per client so we have a first visible
signal that the UVM chain works end to end. The real checks -- bandwidth
ratio within tolerance, starvation-freedom within each class's age
threshold (SPEC.md section 6) -- are added in Phase 3/4 once we have
enough stimulus for those checks to mean anything.
"""

from pyuvm import uvm_component, uvm_tlm_analysis_fifo


class ArbScoreboard(uvm_component):
    def build_phase(self):
        self.fifo = uvm_tlm_analysis_fifo("fifo", self)
        self.analysis_export = self.fifo.analysis_export
        self.get_port = self.fifo.get_export

    def start_of_simulation_phase(self):
        self.grant_count = [0, 0, 0]

    async def run_phase(self):
        while True:
            client, addr = await self.get_port.get()
            self.grant_count[client] += 1
            self.logger.info(f"GRANT client={client} addr={hex(addr)}")

    def report_phase(self):
        total = sum(self.grant_count)
        self.logger.info(
            f"Grant tally: COMPUTE={self.grant_count[0]} "
            f"TEXTURE={self.grant_count[1]} "
            f"DISPLAY={self.grant_count[2]} (total={total})"
        )
