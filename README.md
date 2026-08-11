# GPU Memory Arbiter — UVM Verification Project

A QoS-aware GPU memory arbiter (SystemVerilog) with a full UVM-style verification environment: cocotb + pyuvm testbench, SystemVerilog Assertions, functional coverage, and an AI-assisted coverage-closure investigation.

## Architecture

Three clients share one memory bus. Each decision: any client past its age threshold wins outright (hard starvation bound); otherwise, highest-credit requester wins — credit accrues per cycle proportional to weight, and is debited (not reset) on a win.

| Client | Weight | Target share | Age threshold |
|---|---|---|---|
| COMPUTE | 5 | 50% | 32 cycles |
| TEXTURE | 3 | 30% | 16 cycles |
| DISPLAY | 2 | 20% | 8 cycles |

4-beat burst hold per grant, no mid-burst preemption. Full spec: [`SPEC.md`](SPEC.md).

## Verification

- **`tb/cocotb/`** — cocotb 2.0.1 + pyuvm 4.0.1: one agent per client, a whitebox monitor, a scoreboard, functional coverage (`cocotb-coverage`), directed and randomized sequences.
- **`tb/sva/`** — SystemVerilog Assertions for SPEC.md §6, run continuously alongside the regression. Icarus Verilog 13.0 implements neither `bind` nor concurrent assertions with `|->` — `gpu_mem_arbiter_tb_top.sv` and immediate assertions work around both, confirmed with a capability check before any real assertion was written.
- **`tb/analysis/`** — standalone Phase 5 tools: a Python model of the RTL's decision logic, an adversarial stimulus search, and cross-validation against the real RTL.

## Results

21/22 functional coverage bins closed in the committed run ([`results/coverage_after.txt`](results/coverage_after.txt)) — the regression has no fixed random seed, so the exact count varies (typically 20 or 21/22). The one bin never closed regardless of seed, `simultaneous_aging_tiebreak`, is a documented, investigated, deliberately-not-forced gap (`SPEC.md` §5). Bandwidth under sustained contention: TEXTURE 32.2% (within ±5% of target); COMPUTE 41.2% and DISPLAY 26.6% both outside tolerance, reported plainly rather than tuned away.

## Real bugs found

1. **Credit-reset vs. surplus/deficit weighting.** Resetting a winner's credit to zero instead of debiting it collapsed the weighted scheme to plain round-robin — caught as a suspicious ~33/33/33 grant split instead of 50/30/20.
2. **Single global driver couldn't model contention.** One driver serving all clients meant two clients could never hold `req` simultaneously. Fixed with one agent per client.
3. **Monitor sampling-order bug silently zeroed aging coverage.** A signal-sampling ordering landed one cycle later than intended, zeroing every aging-override detection. Fixed by sampling registers instead of a combinational signal.
4. **Equal-quota stimulus faked a clean bandwidth split.** Giving every client the same request count let whoever won more finish early and go idle, forcing an artificially even measured split. Fixed by time-boxing instead.
5. **A hypothesis tested and refuted (Phase 5).** Expected COMPUTE/TEXTURE's aging thresholds to be structurally unreachable; an adversarial search, cross-validated against the real RTL, found they're not — the mechanism is now exercised in the regression.

Full account of each: [`AI_METHODOLOGY.md`](AI_METHODOLOGY.md) and [`docs/phases/PHASE5_LOG.md`](docs/phases/PHASE5_LOG.md).

## How to run it

Requires Icarus Verilog and `cocotb==2.0.1`, `pyuvm==4.0.1`, `cocotb-coverage`.

```bash
cd tb/cocotb && make                      # full UVM regression
cd tb/sva && iverilog -g2012 sva_smoke_test.sv && vvp a.out   # SVA capability check
cd tb/sva && iverilog -g2012 -o sva_negative_test.out gpu_mem_arbiter_assertions.sv sva_negative_test.sv && vvp sva_negative_test.out  # confirms checks actually fire
cd tb/analysis && python3 wrr_bound_search.py   # Phase 5 adversarial search
cd tb/analysis && make                          # Phase 5 cross-validation
```

## Repo structure

```
├── SPEC.md              — design spec
├── AI_METHODOLOGY.md     — AI-assisted development account
├── LICENSE
├── rtl/                  — the arbiter RTL
├── tb/{cocotb,sva,analysis}/
├── results/              — coverage before/after
└── docs/phases/          — task briefs + Phase 5's raw log (see docs/phases/README.md)
```

## Tooling

SystemVerilog, UVM (via pyuvm), cocotb, Icarus Verilog, SVA, cocotb-coverage, Python.

## AI-assisted development

Used throughout — see [`AI_METHODOLOGY.md`](AI_METHODOLOGY.md) for an honest account of the division of labor.

## Scope

Read-only arbiter, fixed 4-beat burst, one client per class, no mid-burst preemption (`SPEC.md` §8).

## License

[MIT](LICENSE).
