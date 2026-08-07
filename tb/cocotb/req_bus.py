"""ReqBus -- shared, race-free access to the DUT's packed `req` vector.

Phase 3 gives each client its own driver so multiple clients can hold
`req` concurrently (required for any contention scenario). Those drivers
all write the same packed `dut.req` signal, so a naive
"read current value, OR in my bit, write it back" from each driver would
race: two drivers could both read the same stale value and clobber each
other's bit. Routing every set/clear through this single object keeps a
Python-side shadow of the bus and does the read-modify-write in one
synchronous (non-async) call, so cocotb never interleaves two clients'
updates mid-operation.
"""


class ReqBus:
    def __init__(self, dut):
        self.dut = dut
        self.bits = 0

    def assert_req(self, client):
        self.bits |= (1 << client)
        self.dut.req.value = self.bits

    def deassert_req(self, client):
        self.bits &= ~(1 << client)
        self.dut.req.value = self.bits
