# GPU Memory Arbiter — Project Plan

**Goal:** A UVM/SystemVerilog verification project for a GPU memory arbiter — arbitration/QoS design reasoning, a full UVM environment, constrained-random + coverage-driven verification, SVA, and a documented AI-assisted coverage-closure methodology.

- **Phase 0 — Spec.** Define the DUT, clients, and QoS policy. Deliverable: `SPEC.md`.
- **Phase 1 — RTL.** Implement the arbiter against the spec, small and correct over ambitious. Deliverable: `rtl/gpu_mem_arbiter.sv`.
- **Phase 2 — UVM testbench skeleton.** Interface, sequence item, one agent per client, environment, scoreboard. Deliverable: `tb/`.
- **Phase 3 — Stimulus & coverage.** Baseline through adversarial sequences, functional coverage model, first coverage report.
- **Phase 4 — SVA assertions.** Safety and liveness/starvation-freedom properties bound to the RTL.
- **Phase 5 — AI-assisted coverage closure.** Review weak coverage bins, test hypotheses about why, close what's closeable, document what isn't.
- **Phase 6 — Documentation & publish.** README, clean commit history, push to GitHub.

Note: the actual testbench ended up built in cocotb/pyuvm (Python) rather than pure SystemVerilog UVM as originally sketched here — see the real repo structure in the top-level `README.md`, which reflects what was actually built.
