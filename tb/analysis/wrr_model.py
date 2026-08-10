"""wrr_model.py -- pure-Python transcription of gpu_mem_arbiter.sv's
arbitration decision logic, for a fast standalone search (Phase 5,
PHASE5_PLAN.md section 1). Not part of the cocotb regression.

Modeling choice: this operates at DECISION granularity, not raw clock
cycles. The real RTL freezes age/credit bookkeeping entirely while
busy_cnt != 0 (the 4-cycle burst hold) -- nothing about age or credit
changes during those cycles, they're a pure no-op for this state. So a
decision-level model that skips the mechanical busy_cnt countdown and
advances straight from one decision to the next produces the exact
same age/credit/win trajectory as the cycle-accurate RTL, just without
wasting 3 no-op steps per decision. This is exactly what's cross-
validated in cross_validate_rtl.py -- don't trust this claim without
reading that script's result.

Port map (SPEC.md section 2): 0 = COMPUTE, 1 = TEXTURE, 2 = DISPLAY
"""

NUM_CLIENTS = 3
WEIGHT = [5, 3, 2]          # weight_of() in the RTL
AGE_THRESHOLD = [32, 16, 8]  # age_th_of() in the RTL
TOTAL_WEIGHT = sum(WEIGHT)   # localparam TOTAL_WEIGHT in the RTL


class WrrState:
    __slots__ = ("age", "credit")

    def __init__(self):
        self.age = [0, 0, 0]
        self.credit = [0, 0, 0]

    def copy(self):
        s = WrrState()
        s.age = list(self.age)
        s.credit = list(self.credit)
        return s


def decision_step(req, state):
    """One arbitration decision. `req` is a 3-tuple/list of bool/int.
    Mutates `state` in place (age/credit after this decision) and
    returns the winning client index, or -1 if nobody won (no requesters).

    Direct transcription of gpu_mem_arbiter.sv's always_ff decision
    branch (the `else` of `if (busy_cnt != 0)`):
      - aged_out[i] = req[i] && age[i] >= age_th_of(i)
      - if any aged_out: winner = highest-weight aged-out client,
        ties broken by lowest index (select_aged_winner()).
      - elif any req: winner = highest-credit requester, ties broken
        by lowest index (`credit[i] > credit[win]`, strict, so the
        first/lowest-index requester found keeps a tie).
      - winner's age -> 0, credit -= TOTAL_WEIGHT (surplus/deficit).
      - other active requesters: age += 1, credit += weight_of(i).
      - non-requesters: age -> 0, credit -> 0.
    """
    aged_out = [bool(req[i]) and state.age[i] >= AGE_THRESHOLD[i] for i in range(NUM_CLIENTS)]

    win = -1
    if any(aged_out):
        best = -1
        for i in range(NUM_CLIENTS):
            if aged_out[i] and (best == -1 or WEIGHT[i] > WEIGHT[best]):
                best = i
        win = best
    elif any(req):
        for i in range(NUM_CLIENTS):
            if req[i] and (win == -1 or state.credit[i] > state.credit[win]):
                win = i

    new_age = [0, 0, 0]
    new_credit = [0, 0, 0]
    for i in range(NUM_CLIENTS):
        if i == win:
            new_age[i] = 0
            new_credit[i] = state.credit[i] - TOTAL_WEIGHT
        elif req[i]:
            new_age[i] = state.age[i] + 1
            new_credit[i] = state.credit[i] + WEIGHT[i]
        else:
            new_age[i] = 0
            new_credit[i] = 0

    state.age = new_age
    state.credit = new_credit
    return win


def run_trial(req_sequence, initial_state=None):
    """req_sequence: iterable of 3-tuples. Returns (max_age_per_client,
    win_sequence, final_state) -- max_age_per_client is the maximum
    value each client's age register ever reached across the whole
    trial (checked *before* each decision resets/increments it, i.e.
    the age that was actually used in that decision's aged_out check --
    matches what the RTL's own aging-override logic would have seen)."""
    state = initial_state.copy() if initial_state else WrrState()
    max_age = [0, 0, 0]
    wins = []
    for req in req_sequence:
        for i in range(NUM_CLIENTS):
            if state.age[i] > max_age[i]:
                max_age[i] = state.age[i]
        win = decision_step(req, state)
        wins.append(win)
    return max_age, wins, state
