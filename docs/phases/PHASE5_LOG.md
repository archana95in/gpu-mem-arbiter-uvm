# Phase 5 log — raw notes

Not polished prose. Raw material for `AI_METHODOLOGY.md`.

## Starting point

`results/coverage_before.txt`: `repeated_aging_event` bins 0 (COMPUTE) and 1 (TEXTURE) at 0 hits; `simultaneous_aging_tiebreak` at 0 hits. `aging_override_used`'s 3 hits were all DISPLAY — COMPUTE/TEXTURE had never aged out.

## Hypothesis: tested, refuted

Working hypothesis: COMPUTE (threshold 32) and TEXTURE (16) can't reach their aging threshold given weights 5/3/2 — COMPUTE's credit grows fastest whenever it's not winning, so it should always win back its turn well before 32 decisions. Reasonable-sounding, wrong.

Built a pure-Python transcription of the RTL's decision logic (`wrr_model.py`) and ran a 20,000-trial random + hill-climbing adversarial search (`wrr_bound_search.py`, ~26s). Result: sequences reaching **exactly** 32 for COMPUTE and 16 for TEXTURE (not more — the RTL's own aging override caps it there). Hypothesis refuted.

Traced the mechanism by hand rather than trusting the raw search output: the target class wins solo/uncontested for a long stretch, building deep negative credit (debited every win, no floor while uncontested). Once contention starts, that debt takes many decisions to recover — long enough to hit the threshold — but only if the two competitors *share* the win burden (low-weight one continuous, high-weight one only periodic). A **solo** denier's own credit drains at the same rate the target recovers (e.g. TEXTURE alone against a -200 deficit: gap shrinks 15/decision, closes in ~13 decisions, nowhere near 32) — confirmed by hand-deriving both cases, not just trusting the search.

Cleaned this into a small deterministic parameter search (`find_directed_pattern.py`): solo=50/period=3 for COMPUTE, solo=25/period=3 for TEXTURE.

## Cross-validation

Built a plain-cocotb harness (`test_wrr_cross_validate.py`) to confirm the Python model matches the real RTL exactly — winner, age, *and* credit at every decision, not just winner (age alone doesn't catch drift for a class that trivially resets to 0 as sole requester). This surfaced a real testbench timing quirk, not an RTL bug: writing a *changed* `req` value doesn't take effect for the very next decision — that decision still evaluates under the old value once more first. Took a few wrong turns (a write-race theory, a `ReadWrite()` sync, a `Timer` settle) before landing on the right model. All three target sequences (190 decisions total) then matched exactly.

Should have scoped this to just the two directed sequences that mattered from the start — burned time validating a maximally-adversarial random sequence that wasn't representative of anything being deployed.

## Outcome

`TargetedAgingSeq` reproduces the cross-validated pattern in the regression, run twice per target (`repeated_aging_event` needs `at_least=2` hits). Result: both bins go from 0 to 2 hits, reliably, every run. Overall coverage total isn't fully pinned down, though — the regression has no fixed random seed, and DISPLAY's own bin (driven by unrelated randomized stimulus) can land either side of its threshold; typical runs land at 20/22 or 21/22.

Wrote the finding up in `SPEC.md` §5: the threshold is reachable, here's the access pattern, and it's exercised in the regression.

## simultaneous_aging_tiebreak — still open, not forced

Considered whether TEXTURE's sequence could double as a DISPLAY-crossing too. Doesn't work: DISPLAY's role requires it to keep winning periodically, which resets its own age every time — the two goals are structurally in tension in this construction. Left open and documented rather than silently dropped.

## Bandwidth gap — one observation, not investigated further

COMPUTE (41.2%) and DISPLAY (26.6%) land outside ±5% tolerance; TEXTURE is spot-on (32.2%). Plausible (unverified) connection to the credit scheme's unbounded memory: COMPUTE wins the most under continuous contention, so it's also most likely accumulating long-run credit drift. Noted as a lead, not a conclusion.
