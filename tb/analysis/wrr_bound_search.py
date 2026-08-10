"""wrr_bound_search.py -- Phase 5, PHASE5_PLAN.md section 1.

Tests the hypothesis that COMPUTE (age threshold 32) and TEXTURE
(threshold 16) can never reach their aging-override threshold under
any request pattern from the other two clients, given the current WRR
weights (5/3/2) -- a structural property of the credit scheme, not a
stimulus gap in the Phase 3 sequences.

Search strategy (documented here since this is the actual evidence
behind whatever SPEC.md/coverage.py end up saying):
  1. Baseline: continuous 3-way flood (every client requests every
     decision) for a long window. This is what Phase 3's
     FullContentionSeq already exercises.
  2. Randomized adversarial search: many trials, each with the two
     "other" clients following an independently randomized per-decision
     request pattern (Bernoulli per decision, with the Bernoulli
     probability itself also randomized per trial so both sparse and
     dense adversarial patterns get tried), while the target client
     requests every decision (its age can only grow while it does).
  3. Hill-climbing refinement: starting from the baseline/best-found
     pattern, flip individual decisions' request bits and keep any
     change that increases the target's max observed age, repeating
     until no single flip helps. Cheap local search around the best
     pattern found so far, without brute-forcing the full state space.

This is deliberately NOT exhaustive (the state space -- every
combination of two clients' request bits over hundreds of decisions --
is astronomically large). Per PHASE5_PLAN.md section 1, the goal is
strong empirical evidence, not formal proof.
"""

import json
import os
import random

from wrr_model import WrrState, decision_step, run_trial, AGE_THRESHOLD, NUM_CLIENTS

RESULTS_PATH = os.path.join(os.path.dirname(__file__), "worst_case_sequences.json")


def continuous_flood(target, num_decisions):
    """All three clients request every decision."""
    return [(1, 1, 1)] * num_decisions


def random_trial_sequence(target, num_decisions, rng):
    """Target requests every decision; the other two independently
    follow a Bernoulli(p) pattern per decision, p itself randomized."""
    others = [i for i in range(NUM_CLIENTS) if i != target]
    probs = {i: rng.random() for i in others}
    seq = []
    for _ in range(num_decisions):
        req = [0, 0, 0]
        req[target] = 1
        for i in others:
            req[i] = 1 if rng.random() < probs[i] else 0
        seq.append(tuple(req))
    return seq


def max_age_for_target(target, req_sequence):
    max_age, wins, _ = run_trial(req_sequence)
    return max_age[target]


def hill_climb(target, req_sequence, rng, max_iters=2000):
    """Local search: flip one decision's non-target bits at a time,
    keep the change if it increases the target's max observed age."""
    seq = [list(r) for r in req_sequence]
    others = [i for i in range(NUM_CLIENTS) if i != target]
    best = max_age_for_target(target, [tuple(r) for r in seq])

    for _ in range(max_iters):
        k = rng.randrange(len(seq))
        i = rng.choice(others)
        old = seq[k][i]
        seq[k][i] = 1 - old
        candidate = max_age_for_target(target, [tuple(r) for r in seq])
        if candidate > best:
            best = candidate
        else:
            seq[k][i] = old  # revert, no improvement

    return best, [tuple(r) for r in seq]


def search_for_target(target, class_name, num_decisions=500, num_random_trials=20_000, seed=0):
    rng = random.Random(seed)
    threshold = AGE_THRESHOLD[target]

    flood_seq = continuous_flood(target, num_decisions)
    flood_max = max_age_for_target(target, flood_seq)

    best_max = flood_max
    best_seq = flood_seq

    for _ in range(num_random_trials):
        seq = random_trial_sequence(target, num_decisions, rng)
        m = max_age_for_target(target, seq)
        if m > best_max:
            best_max = m
            best_seq = seq

    climbed_max, climbed_seq = hill_climb(target, best_seq, rng)
    if climbed_max > best_max:
        best_max = climbed_max
        best_seq = climbed_seq

    return {
        "class": class_name,
        "target_index": target,
        "threshold": threshold,
        "continuous_flood_max_age": flood_max,
        "best_found_max_age": best_max,
        "num_random_trials": num_random_trials,
        "num_decisions_per_trial": num_decisions,
        "threshold_reached": best_max >= threshold,
        "best_sequence": best_seq,
    }


def main():
    results = {}
    for target, name in ((0, "COMPUTE"), (1, "TEXTURE")):
        r = search_for_target(target, name)
        results[name] = r
        print(f"=== {name} (threshold {r['threshold']}) ===")
        print(f"  continuous 3-way flood max age observed: {r['continuous_flood_max_age']}")
        print(f"  best found across {r['num_random_trials']} random trials + hill-climb: {r['best_found_max_age']}")
        print(f"  threshold reached: {r['threshold_reached']}")

    # Save the best-found sequences so the cocotb cross-validation test
    # can replay these exact patterns against the real RTL, not just
    # generic sanity sequences.
    to_save = {
        name: {"target_index": r["target_index"], "class": r["class"],
               "best_found_max_age": r["best_found_max_age"],
               "sequence": r["best_sequence"]}
        for name, r in results.items()
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(to_save, f)
    print(f"\nSaved best-found sequences to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
