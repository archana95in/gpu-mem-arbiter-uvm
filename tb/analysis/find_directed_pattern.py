"""find_directed_pattern.py -- Phase 5 refinement step.

wrr_bound_search.py's random+hill-climb search found that COMPUTE and
TEXTURE *can* be pushed to their aging thresholds, refuting the
"structurally unreachable" hypothesis (PHASE5_PLAN.md section 1) -- but
the winning sequence it found is 500 decisions of noisy, hill-climbed
data, not something worth replaying verbatim as a testbench sequence.

Tracing the found COMPUTE sequence (see the Phase 5 log) showed the
actual mechanism: the target class first wins solo/lightly-contested
for a long stretch, building a deep negative credit debt (credit -=
TOTAL_WEIGHT on every win, with nothing to offset it while
uncontested) -- then the other two clients deny it by *sharing* the
win burden (the lower-weight one requesting continuously, the
higher-weight one only periodically) rather than one of them denying
it solo, since a solo denier's own credit drains just as fast as the
target's recovers and the two cross before reaching the threshold.

This script searches a small, clean, deterministic parameter family
(solo run-up length, periodic duty cycle for the higher-weight of the
two "other" clients) for the smallest/cleanest combination that
reliably reaches each target's threshold -- something a real
TargetedAgingSeq can reproduce exactly, not a frozen random blob.
"""

from wrr_model import WrrState, decision_step, run_trial, AGE_THRESHOLD, WEIGHT


def build_sequence(target, solo_decisions, contend_decisions, periodic_period):
    """Phase A: target requests solo for `solo_decisions` (builds deep
    credit deficit, since it wins every decision with no competition).
    Phase B: target + both other clients contend; the lower-weight of
    the two "other" clients requests every decision, the higher-weight
    one only every `periodic_period`-th decision, sharing the win
    burden the way the search's found pattern did."""
    seq = []
    for _ in range(solo_decisions):
        req = [0, 0, 0]
        req[target] = 1
        seq.append(tuple(req))

    others = [i for i in range(3) if i != target]
    others_by_weight = sorted(others, key=lambda i: WEIGHT[i])
    low_weight_other, high_weight_other = others_by_weight[0], others_by_weight[1]

    for k in range(contend_decisions):
        req = [0, 0, 0]
        req[target] = 1
        req[low_weight_other] = 1
        req[high_weight_other] = 1 if (k % periodic_period == 0) else 0
        seq.append(tuple(req))
    return seq


def main():
    for target, name in ((0, "COMPUTE"), (1, "TEXTURE")):
        threshold = AGE_THRESHOLD[target]
        print(f"--- {name} (threshold {threshold}) ---")
        found = []
        for solo in (10, 15, 20, 25, 30, 40):
            for period in (2, 3, 4, 5, 6):
                seq = build_sequence(target, solo, 80, period)
                max_age, wins, _ = run_trial(seq)
                if max_age[target] >= threshold:
                    found.append((solo, period, max_age[target]))
        if found:
            # smallest total decisions (solo + enough contend to hit it) first
            found.sort(key=lambda t: t[0])
            for solo, period, m in found[:8]:
                print(f"  solo={solo:3d} periodic_period={period}: max_age={m:3d}  REACHED")
        else:
            print("  no combination in this search grid reached the threshold")


if __name__ == "__main__":
    main()
