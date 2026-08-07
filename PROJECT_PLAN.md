# GPU Memory Arbiter — AI-Assisted UVM Verification Project

**Goal:** A UVM/SystemVerilog verification project for a GPU memory arbiter — arbitration/QoS design reasoning, a full UVM environment, constrained-random + coverage-driven verification, SVA, and a documented AI-assisted coverage-closure methodology.

## Phase 0 — Spec & Design Decisions
- Define the DUT: number of clients, traffic classes (compute / texture / display), bus/memory interface shape (address, data width, burst support).
- Define the QoS policy: bandwidth guarantee per class, aging rule for starvation-freedom, any hard-latency requirement for display traffic.
- Write these down as a one-page spec — becomes the "requirements" section of the README and the source for both assertions and coverage bins.
- **Deliverable:** `SPEC.md`

## Phase 1 — DUT (RTL)
- Implement the arbiter in synthesizable SystemVerilog against the Phase 0 spec.
- Keep it small and correct over ambitious and buggy.
- **Deliverable:** `rtl/gpu_mem_arbiter.sv` (+ any submodules)

## Phase 2 — UVM Testbench Skeleton
- Interface definition (pin-level connection between testbench and DUT).
- Sequence item (one arbitration request: client ID, class, address, burst length).
- Agent per client port: sequencer, driver, monitor.
- Environment wiring all agents together.
- Scoreboard: checks grants against the QoS policy (no double-grants, bandwidth ratios respected, no starvation beyond the aging bound).
- **Deliverable:** `tb/` directory with one file per component, running on EDA Playground first, then exported.

## Phase 3 — Stimulus & Functional Coverage
- Baseline sequences: random single-client traffic, then multi-client contention, then adversarial patterns (one class flooding the bus to try to starve another).
- Functional coverage model translating the Phase 0 spec into concrete coverage bins (all-classes-contending, burst-crossing-boundary, client-at-max-aging, etc.).
- Run simulation, generate first coverage report.
- **Deliverable:** `tb/sequences/`, `tb/coverage.sv`, first coverage report saved to `results/`

## Phase 4 — SVA Assertions
- Safety properties (no illegal simultaneous grants, grant always maps to a valid pending request).
- Liveness/starvation-freedom property derived directly from the aging rule in the spec.
- Bind assertions into the DUT or a dedicated checker module.
- **Deliverable:** `tb/assertions.sv`

## Phase 5 — AI-Assisted Coverage Closure
- Review the Phase 3 coverage report for empty/weak bins.
- Use AI-assisted analysis to propose targeted sequences or constraint tweaks to close them; review and curate every suggestion before adding it.
- Re-run, compare before/after coverage numbers and note anything AI got wrong or needed correction.
- **Deliverable:** `results/coverage_before.txt`, `results/coverage_after.txt`, `AI_METHODOLOGY.md`

## Phase 6 — Documentation & Publish
- Top-level `README.md`: problem statement, design decisions, verification plan, coverage results, what the AI-assisted layer added, how to run it on EDA Playground.
- Clean, logical commit history.
- Push to personal GitHub.

## Repo structure
```
gpu-mem-arbiter-uvm/
├── README.md
├── SPEC.md
├── AI_METHODOLOGY.md
├── rtl/
│   └── gpu_mem_arbiter.sv
├── tb/
│   ├── interface.sv
│   ├── seq_item.sv
│   ├── sequences/
│   ├── agent/
│   ├── scoreboard.sv
│   ├── coverage.sv
│   ├── assertions.sv
│   ├── env.sv
│   └── test_top.sv
└── results/
    ├── coverage_before.txt
    ├── coverage_after.txt
    └── waveform.vcd (or screenshots)
```
