# Phase 3 — Stimulus & Functional Coverage

Builds on the Phase 2 UVM skeleton and SPEC.md §6-7. Goal: constrained-random-style stimulus, a functional coverage model matching the spec's target scenarios, and a statistical bandwidth check.

## Sequences (`tb/cocotb/sequences.py`)

| Sequence | Covers |
|---|---|
| `SoloRequestSeq` | Each class as sole requester |
| `FullContentionSeq` | All three classes contending (~10,000 cycles; also the bandwidth-check data source) |
| `AgingStressSeq` | Aging override path (DISPLAY, tightest threshold) |
| `SimultaneousAgingSeq` | Two classes aging out on the same cycle (tie-break) |
| `RandomContentionSeq` | General noise, burst-boundary cases |
| `RepeatedAgingSeq` | A class held >2x its threshold — confirms repeated, not one-off, aging events |

## Coverage (`tb/cocotb/coverage.py`, new)

Use `cocotb-coverage`'s `CoverPoint`/`CoverCross`, hooked into the monitor's grant callback: `client_granted`, `contention_level`, their cross, plus standalone points for `aging_override_used`, `simultaneous_aging_tiebreak`, and `repeated_aging_event` (per class). Export a report to `results/coverage_before.txt` for Phase 5.

## Bandwidth check (`scoreboard.py`, extend)

After `FullContentionSeq`: each client's grant fraction should track its weight (50/30/20%) within ±5% — a statistical check in `report_phase`, not a per-cycle assertion. Log actual vs. target either way; if it's off even after the Phase 1 credit-scheme fix, that's a real signal worth investigating, not a bug in the check.
