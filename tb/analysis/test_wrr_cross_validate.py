"""test_wrr_cross_validate.py -- Phase 5 cross-validation.

Plain cocotb test (no pyuvm -- this is a standalone analysis tool, not
part of the Phase 2/3/4 regression). Drives gpu_mem_arbiter directly,
decision by decision, with the exact same request sequences used by
wrr_model.py, and asserts the RTL's actual winner and age/credit
trajectory match the Python model exactly at every decision -- the
fidelity check that makes the Phase 5 section 1 search's conclusions
trustworthy (rather than an artifact of a mistranscribed model).

Sequences checked:
  - continuous 3-way flood (baseline sanity)
  - the exact clean directed sequences (find_directed_pattern.py's
    build_sequence(), same solo/period parameters used for the real
    TargetedAgingSeq_* testbench sequences) for both COMPUTE and
    TEXTURE -- confirms the specific pattern the regression relies on
    to close the coverage bins behaves identically on real hardware,
    not just in the model.

Timing behavior found while building this (confirmed by direct
experiment, not guessed): writing a *changed* req value doesn't take
effect for the very next arbitration decision. The RTL's decision on
that immediate next edge still evaluates under the OLD req value one
more time -- confirmed directly by holding req constant post-reset and
watching busy_cnt only move on the second edge (matching the proven-
working Phase 3 regression's own first-grant timestamp, 40ns with a
10ns period, from a cached log), and later by a mid-sequence
transition (50 solo COMPUTE decisions, then contention) whose "decision
50" showed exactly the winner solo COMPUTE would have produced, not
the new contended winner. Writes that repeat the *same* value never
show this -- continuous_flood's internal 39 decision-to-decision steps
(same req throughout) and each directed sequence's first 50/25 solo
steps (same req throughout that phase) all needed only the ordinary
single edge.

drive_one_decision() below handles this by treating every req change
as two real RTL decisions: first a "settle" decision (the RTL's own
stale-value one, modeled against the OLD req so it's not miscounted as
a mismatch), then the real one under the new value. The very first
decision of a sequence is just this same mechanism with the implicit
initial req of (0, 0, 0) (reset state, matching the RTL's own
post-reset behavior of no winner on that settle decision).

Run with (from tb/analysis/): source ../../.venv/bin/activate && make
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge

from wrr_model import WrrState, decision_step, NUM_CLIENTS
from find_directed_pattern import build_sequence


def req_to_int(req):
    val = 0
    for i, bit in enumerate(req):
        if bit:
            val |= (1 << i)
    return val


def read_win(dut):
    gnt_val = int(dut.gnt.value)
    if not gnt_val:
        return -1
    return (gnt_val & -gnt_val).bit_length() - 1


async def reset_dut(dut):
    dut.rst_n.value = 0
    dut.req.value = 0
    for i in range(NUM_CLIENTS):
        dut.addr[i].value = 0
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst_n.value = 1
    await RisingEdge(dut.clk)


async def drive_write_and_settle(dut, req):
    """Writes `req` and advances through exactly one RTL decision --
    the one that fires on the very next edge, which per the module
    docstring may still be evaluating under whatever req was in effect
    *before* this write. Returns the observed winner for that decision
    (not necessarily for `req` -- see drive_one_decision)."""
    dut.req.value = req_to_int(req)
    await RisingEdge(dut.clk)
    win = read_win(dut)
    while dut.bus_busy.value.is_resolvable and int(dut.bus_busy.value):
        await RisingEdge(dut.clk)
    return win


async def check_sequence(dut, name, req_sequence):
    model_state = WrrState()
    prev_req = (0, 0, 0)  # matches reset state -- no requesters, no winner

    for k, req in enumerate(req_sequence):
        req = tuple(req)

        if req != prev_req:
            # This write's *first* resulting decision still reflects
            # prev_req, per the module docstring. Step the model the
            # same way to stay in sync, and check it against prev_req,
            # not req_sequence[k].
            stale_win = await drive_write_and_settle(dut, req)
            expected_stale = decision_step(prev_req, model_state)
            assert stale_win == expected_stale, (
                f"{name} decision {k} (settle step, still using prior req={prev_req}): "
                f"RTL winner={stale_win} model winner={expected_stale}"
            )

        # By now req has genuinely taken effect (this call's write
        # repeats the same value if we just did a settle step above,
        # which is exactly the "no change" case that's never shown the
        # timing issue).
        rtl_win = await drive_write_and_settle(dut, req)
        model_win = decision_step(req, model_state)
        assert rtl_win == model_win, (
            f"{name} decision {k}: RTL winner={rtl_win} model winner={model_win} req={req}"
        )
        for i in range(NUM_CLIENTS):
            rtl_age = int(dut.age[i].value)
            assert rtl_age == model_state.age[i], (
                f"{name} decision {k} client {i}: RTL age={rtl_age} model age={model_state.age[i]}"
            )
            rtl_credit = dut.credit[i].value.to_signed()
            assert rtl_credit == model_state.credit[i], (
                f"{name} decision {k} client {i}: RTL credit={rtl_credit} model credit={model_state.credit[i]}"
            )

        prev_req = req

    dut._log.info(f"{name}: {len(req_sequence)} decisions, RTL matched Python model exactly")


@cocotb.test()
async def test_cross_validate(dut):
    compute_seq = build_sequence(target=0, solo_decisions=50, contend_decisions=50, periodic_period=3)
    texture_seq = build_sequence(target=1, solo_decisions=25, contend_decisions=25, periodic_period=3)

    sequences = [
        ("continuous_flood", [(1, 1, 1)] * 40),
        ("directed_COMPUTE", compute_seq),
        ("directed_TEXTURE", texture_seq),
    ]

    for name, seq in sequences:
        await reset_dut(dut)
        await check_sequence(dut, name, seq)

    dut._log.info("All Phase 5 cross-validation sequences matched the Python model exactly.")
