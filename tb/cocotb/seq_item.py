"""ArbReqItem -- the UVM sequence item for gpu_mem_arbiter.

One item represents a single arbitration request: a client asserting
`req` with a given `addr`, held until that client's `gnt` bit fires.
See SPEC.md section 3 for the interface this models.
"""

from pyuvm import uvm_sequence_item


class ArbReqItem(uvm_sequence_item):
    # Port map (see SPEC.md section 2): 0 = COMPUTE, 1 = TEXTURE, 2 = DISPLAY
    def __init__(self, name="ArbReqItem", client=0, addr=0):
        super().__init__(name)
        self.client = client
        self.addr = addr

    def __str__(self):
        return f"ArbReqItem(client={self.client}, addr={hex(self.addr)})"
