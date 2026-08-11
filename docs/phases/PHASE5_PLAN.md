# Phase 5 — AI-Assisted Coverage Closure

Builds on the Phase 3 coverage report. Goal: close what's closeable, and for what isn't, prove *why* rather than shrugging at it.

## 0. Starting point

`results/coverage_before.txt` (19/22) has 3 missing bins: `repeated_aging_event` bins 0 (COMPUTE) and 1 (TEXTURE), and `simultaneous_aging_tiebreak`. `aging_override_used` had exactly 3 hits total, all attributable to DISPLAY — COMPUTE/TEXTURE have never aged out even once.

## 1. Working hypothesis to test first

Before writing more stimulus: **COMPUTE and TEXTURE's age thresholds (32, 16) may be structurally unreachable given the WRR weights (5/3/2)** — COMPUTE's credit grows fastest whenever it's not winning, so it should always win back its turn well before 32 decisions elapse.

Test this properly rather than guessing: a standalone script modeling the RTL's decision logic, run through an adversarial search over stimulus patterns, recording each class's worst-case observed wait.

## 2. Two outcomes, two next steps

**If the hypothesis holds:** stop chasing those bins with more stimulus, document the finding as a `SPEC.md` §5 addendum, and mark the bins as a justified coverage waiver — this also explains the simultaneous-tiebreak bin for free (if they can't age out, they can't age out *together*).

**If the hypothesis fails:** construct the exact adversarial pattern found as a new targeted sequence, add it to the regression, confirm the bin closes. For the tiebreak bin, this likely needs precise cycle-offset timing so two classes cross their thresholds on the same decision.

Either outcome is a legitimate result — the point is reaching one with evidence, not re-running random stimulus and hoping.

## 3. Optional: the bandwidth-tolerance gap

Phase 3 found COMPUTE (41.2% vs. 50%) and DISPLAY (26.6% vs. 20%) outside tolerance under sustained contention. Same underlying algorithm as §1 — note anything relevant found, but don't treat closing it as required.

## 4. Deliverables

`results/coverage_after.txt`, a `SPEC.md` update if warranted, and a plain-language running log of what was tried — raw material for `AI_METHODOLOGY.md`, written later, not polished prose now.
