"""Sequences for gpu_mem_arbiter -- Phase 3 stimulus.

SPEC.md section 7 lists the functional coverage targets these
scenarios are built to exercise. `SoloRequestSeq` is the one real
low-level uvm_sequence (issues back-to-back requests for a single
client on its own per-client sequencer); everything else is a thin
orchestration class that starts multiple per-client sequences
concurrently on the right sequencers (pulled from ConfigDB's "SEQRS"
entry -- see env.py) to produce actual multi-client contention. This
only works because each client now has its own agent (Phase 2 had one
shared driver that could only run one client's request at a time).
"""

import random

import cocotb
from cocotb.triggers import ClockCycles
from pyuvm import uvm_sequence, ConfigDB
from seq_item import ArbReqItem

# Port map (SPEC.md section 2): 0 = COMPUTE, 1 = TEXTURE, 2 = DISPLAY
AGE_THRESHOLD = {0: 32, 1: 16, 2: 8}
DECISION_CYCLES = 4  # burst length (SPEC.md section 3) -- cycles per arbitration decision


def _seqr(client):
    return ConfigDB().get(None, "", "SEQRS")[client]


class _StopFlag:
    """Plain mutable flag shared between a time-boxing coroutine and the
    sequences it should tell to stop -- see SoloRequestSeq's stop_flag
    param and FullContentionSeq.run()."""

    stopped = False


class SoloRequestSeq(uvm_sequence):
    """Issues `num_requests` back-to-back requests for one client.

    Run alone (no other client's sequencer active), this is SPEC.md
    section 7's "each class as sole requester." Run concurrently with
    other per-client sequences on their own sequencers, this is the
    building block for every contention scenario below.
    """

    def __init__(self, client, num_requests, addr_base=0, name="SoloRequestSeq", stop_flag=None):
        super().__init__(name)
        self.client = client
        self.num_requests = num_requests
        self.addr_base = addr_base
        # Optional cooperative stop: checked only between items (never
        # mid-item), so a driver is never abandoned mid-wait holding
        # `req` asserted. FullContentionSeq uses this to time-box a
        # window without leaving the driver underneath stuck forever --
        # an earlier version used task.kill() instead, which cut the
        # sequence off but left its driver blocked forever waiting for
        # a grant that would never come once req was force-cleared,
        # deadlocking the next scenario that needed that same driver.
        self.stop_flag = stop_flag

    async def body(self):
        for i in range(self.num_requests):
            if self.stop_flag is not None and self.stop_flag.stopped:
                break
            item = ArbReqItem(client=self.client, addr=self.addr_base + i)
            await self.start_item(item)
            await self.finish_item(item)


class RandomPerClientSeq(uvm_sequence):
    """Randomly toggles one client's request on/off per decision slot:
    with probability `assert_prob` it issues a request that decision,
    otherwise it idles for one decision's worth of cycles. Building
    block for RandomContentionSeq."""

    def __init__(self, client, num_decisions, assert_prob, name="RandomPerClientSeq"):
        super().__init__(name)
        self.client = client
        self.num_decisions = num_decisions
        self.assert_prob = assert_prob

    async def body(self):
        dut = ConfigDB().get(None, "", "DUT")
        for i in range(self.num_decisions):
            if random.random() < self.assert_prob:
                item = ArbReqItem(client=self.client, addr=0x1000 * self.client + i)
                await self.start_item(item)
                await self.finish_item(item)
            else:
                await ClockCycles(dut.clk, DECISION_CYCLES)


async def _run_concurrent(seqs_and_seqrs):
    """seqs_and_seqrs: list of (uvm_sequence, sequencer) pairs. Starts
    each concurrently and waits for all of them to finish."""
    tasks = [cocotb.start_soon(seq.start(seqr)) for seq, seqr in seqs_and_seqrs]
    for t in tasks:
        await t


class FullContentionSeq:
    """All three clients request continuously for a long window --
    SPEC.md section 7's "all three classes requesting simultaneously,"
    and the data source for the scoreboard's bandwidth check.

    Time-boxed by `num_decisions`, not by an equal per-client request
    count: giving every client the *same* request quota would trivially
    force equal final grant totals regardless of the RTL's weighting
    (whichever client wins more often simply finishes its quota and
    stops early, so the tally can never diverge from equal shares) --
    that was a real bug caught by looking at the first bandwidth
    numbers (a suspicious exact 33/33/33 split). Instead, give each
    client an effectively-unbounded quota and cut them all off together
    after a fixed number of decisions.
    """

    def __init__(self, num_decisions=10_000):
        self.num_decisions = num_decisions

    async def run(self):
        dut = ConfigDB().get(None, "", "DUT")
        flag = _StopFlag()
        unbounded = self.num_decisions + 1  # more than any client could win alone
        pairs = [
            (SoloRequestSeq(0, unbounded, 0x0000, "full_compute", stop_flag=flag), _seqr(0)),
            (SoloRequestSeq(1, unbounded, 0x1000, "full_texture", stop_flag=flag), _seqr(1)),
            (SoloRequestSeq(2, unbounded, 0x2000, "full_display", stop_flag=flag), _seqr(2)),
        ]
        tasks = [cocotb.start_soon(seq.start(seqr)) for seq, seqr in pairs]

        await ClockCycles(dut.clk, self.num_decisions * DECISION_CYCLES)
        flag.stopped = True

        # Each sequence notices the flag between items (never mid-item)
        # and returns on its own -- no killed tasks, no driver left
        # stuck mid-wait for a grant that will never arrive.
        for t in tasks:
            await t


class AgingStressSeq:
    """COMPUTE + TEXTURE flood continuously; DISPLAY holds continuously
    alongside. DISPLAY's threshold (8 decisions) is the tightest, so
    this should repeatedly force the aging-override path for DISPLAY --
    SPEC.md section 7's "any class reaching its age threshold" and
    "DISPLAY starved to within 1 cycle of its threshold.\""""

    def __init__(self, num_requests=200):
        self.num_requests = num_requests

    async def run(self):
        await _run_concurrent([
            (SoloRequestSeq(0, self.num_requests, 0x0000, "aging_compute"), _seqr(0)),
            (SoloRequestSeq(1, self.num_requests, 0x1000, "aging_texture"), _seqr(1)),
            (SoloRequestSeq(2, self.num_requests, 0x2000, "aging_display"), _seqr(2)),
        ])


class RepeatedAgingSeq:
    """One client held continuously for >2x its class's age threshold,
    against continuous competition from the other two, to confirm it
    doesn't win once via aging and then immediately starve again."""

    def __init__(self, client, num_requests=None):
        self.client = client
        threshold = AGE_THRESHOLD[client]
        self.num_requests = num_requests or (3 * threshold)  # comfortably >2x

    async def run(self):
        others = [c for c in (0, 1, 2) if c != self.client]
        pairs = [(SoloRequestSeq(self.client, self.num_requests, 0x1000 * self.client,
                                  f"repeat_c{self.client}"), _seqr(self.client))]
        for c in others:
            pairs.append((SoloRequestSeq(c, self.num_requests * 2, 0x1000 * c,
                                          f"repeat_c{c}"), _seqr(c)))
        await _run_concurrent(pairs)


class SimultaneousAgingSeq:
    """Stagger TEXTURE and DISPLAY's start times, with COMPUTE flooding
    throughout, aiming for both to cross their age thresholds (16 and 8
    decisions) on the same arbitration decision -- SPEC.md section 7's
    "two classes aging out simultaneously (tie-break exercised)."

    This is a best-effort directed attempt, not a guaranteed one: the
    credit-based weighted-round-robin scheme means TEXTURE can still win
    a normal (non-aged) arbitration before reaching its threshold,
    depending on runtime credit dynamics -- see PHASE3_PLAN.md section 5
    and AI_METHODOLOGY.md for what was actually observed.
    """

    def __init__(self, texture_requests=64, display_requests=64, compute_requests=200):
        self.texture_requests = texture_requests
        self.display_requests = display_requests
        self.compute_requests = compute_requests

    async def run(self):
        dut = ConfigDB().get(None, "", "DUT")

        compute_seq = SoloRequestSeq(0, self.compute_requests, 0x0000, "sim_compute")
        texture_seq = SoloRequestSeq(1, self.texture_requests, 0x1000, "sim_texture")
        display_seq = SoloRequestSeq(2, self.display_requests, 0x2000, "sim_display")

        compute_task = cocotb.start_soon(compute_seq.start(_seqr(0)))
        texture_task = cocotb.start_soon(texture_seq.start(_seqr(1)))

        # TEXTURE's threshold is 16 decisions, DISPLAY's is 8 -- start
        # DISPLAY 8 decisions after TEXTURE so both are aiming at the
        # same absolute decision.
        await ClockCycles(dut.clk, AGE_THRESHOLD[2] * DECISION_CYCLES)

        display_task = cocotb.start_soon(display_seq.start(_seqr(2)))

        await compute_task
        await texture_task
        await display_task


class RandomContentionSeq:
    """Each client's req independently toggles on/off per decision via
    weighted random.random() calls -- general noise + burst-boundary
    coverage, and the statistical backstop for any directed scenario
    (e.g. simultaneous aging) that doesn't land deterministically."""

    def __init__(self, num_decisions=2000, assert_prob=(0.6, 0.4, 0.3)):
        self.num_decisions = num_decisions
        self.assert_prob = assert_prob

    async def run(self):
        await _run_concurrent([
            (RandomPerClientSeq(client, self.num_decisions, self.assert_prob[client],
                                 f"rand_c{client}"), _seqr(client))
            for client in (0, 1, 2)
        ])
