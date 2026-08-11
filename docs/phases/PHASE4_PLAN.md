# Phase 4 — SVA Assertions

Builds on SPEC.md §6 and the working Phase 3 regression. Goal: SystemVerilog Assertions bound to the RTL, checked continuously during the existing Phase 3 sequences.

## 0. Do this first: Icarus SVA capability check

Before writing the full assertion set, verify what Icarus Verilog 13.0 actually supports — SVA support in open-source simulators is historically partial. Write a throwaway `tb/sva/sva_smoke_test.sv` with a simple immediate assertion and one bounded-range concurrent property (`req |-> ##[0:8] gnt`). Compile with `iverilog -g2012` and see what breaks; that determines the approach below.

## 1. Structure: `bind`, not inline RTL edits

Keep assertions in a separate file bound to the DUT via a `bind` statement, so `gpu_mem_arbiter.sv` itself doesn't change. Add the file(s) to `VERILOG_SOURCES` so assertions run continuously during the existing regression.

## 2. Safety properties (SPEC.md §6)

- No double grant (`$onehot0(gnt)`).
- No grant while bus busy.
- Phantom-grant check (grant only to a port that was actually requesting).

## 3. Liveness / starvation-freedom

Each class has a hard wait bound (DISPLAY 8, TEXTURE 16, COMPUTE 32 cycles). Natural statement is a bounded-range implication (`req |-> ##[0:N] gnt`) per class. **If the capability check shows Icarus rejects ranged delays**, fall back to a Python-side check in the scoreboard instead — a normal, defensible call, not a failure. Document whichever path was taken in `AI_METHODOLOGY.md`.

## 4. Verification

Rerun the full regression with the new assertions wired in — confirm no spurious fires on passing scenarios, and construct at least one deliberately-bad case to confirm an assertion *can* fire (not silently inert).

## 5. Note

Phase 3 found COMPUTE/TEXTURE's aging override may be structurally unreachable under full contention. If their liveness assertions never fire in existing Phase 3 stimulus, that's expected, not a hole — worth a one-line note in the assertions file.
