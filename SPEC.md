# SPEC — GPU Memory Arbiter (gpu_mem_arbiter)

## 1. Overview
A read-address arbiter for a shared GPU memory bus, servicing three fixed client ports — one per traffic class. Models the front-end arbitration decision a GPU memory controller makes when compute, texture, and display clients contend for the same memory bandwidth.

## 2. Clients
| Port | Class    | Latency sensitivity | Weight (share under full contention) |
|------|----------|---------------------|----------------------------------------|
| 0    | COMPUTE  | Low                 | 5 (50%) |
| 1    | TEXTURE  | Medium              | 3 (30%) |
| 2    | DISPLAY  | High (deadline-driven) | 2 (20%) |

Weights are a **target share under full contention**, not a fixed allocation — the policy is work-conserving: if a class has no pending request, its share is available to whichever classes are requesting (no idle bus cycles while any client has a pending request).

## 3. Interface (per client port)
- `req` — 1-bit request valid
- `addr[31:0]` — read address
- `gnt` — 1-bit grant (asserted for 1 cycle when this port wins arbitration)
- Burst length is fixed at **4 beats**, data width **128 bits** per beat (512 bits / 64 bytes per granted transaction) — no burst-length signal needed since it's constant.

## 4. Bus/arbitration model
- Single shared bus; one client owns it per transaction.
- Once granted, the winning client holds the bus for the full 4-beat burst (4 cycles) before the arbiter re-evaluates. This is a simplification (no mid-burst preemption) that keeps the DUT scope tractable without losing the interesting arbitration logic.
- Arbitration decision happens on any cycle where the bus is free and ≥1 client has `req` asserted.

## 5. Arbitration policy — weighted + aging
Each client port has an **age counter**, incremented by 1 every cycle its `req` is asserted and it is *not* granted; reset to 0 the cycle it *is* granted.

Each class has an **age threshold** (the hard starvation bound):
| Class    | Age threshold (cycles) |
|----------|--------------------------|
| DISPLAY  | 8  |
| TEXTURE  | 16 |
| COMPUTE  | 32 |

Decision each arbitration cycle:
1. **Aging override:** if any requesting client's age ≥ its class's threshold, the oldest such client wins (ties broken by class weight, highest first; further ties broken round-robin). This is what makes starvation-freedom a provable property — see §6.
2. **Otherwise, weighted round-robin:** among requesting clients, select using a credit-based weighted round-robin (each port accumulates credit each cycle proportional to its weight; highest-credit requester wins; winner's credit resets, others keep accumulating).

## 6. Correctness properties (source for SVA in Phase 4)
**Safety:**
- Exactly one `gnt` asserted at a time, never zero-during-contention and never more than one.
- `gnt` is only ever asserted for a port with `req` currently or previously asserted (no phantom grants).
- Once granted, no other client's `gnt` asserts until the 4-cycle burst completes (bus-hold correctness).

**Liveness / starvation-freedom:**
- Any client whose `req` stays asserted is granted within its class's age threshold (8/16/32 cycles) of first asserting `req`, measured under any contention pattern from the other two ports. This is directly checkable as an SVA liveness property per class.

**Bandwidth (checked via scoreboard/coverage statistics, not a hard assertion):**
- Under sustained full contention (all three `req` held high for a long window, e.g. 10,000 arbitration cycles), each class's fraction of total grants should track its weight (50/30/20%) within a defined tolerance (e.g., ±5%). This is a statistical property, not a per-cycle guarantee, so it belongs in the scoreboard/coverage report rather than SVA.

## 7. Functional coverage targets (source for Phase 3 covergroups)
- Each class as sole requester (no contention).
- All three classes requesting simultaneously.
- Any class reaching its age threshold and winning via aging override.
- Two classes aging out simultaneously (tie-break exercised).
- A class requesting continuously for >2x its age threshold (repeated aging cycles).
- Burst-boundary cases: new request arriving exactly on the cycle the bus frees up.
- DISPLAY starved down to 1 cycle from its threshold while COMPUTE + TEXTURE both continuously request (worst-case latency-sensitive scenario).

## 8. Explicitly out of scope (v1)
- Write channel (read-only arbiter for this project).
- Variable burst length / AXI-style burst negotiation.
- More than one client per class.
- Preemption mid-burst.

---
*This spec is the source of truth for the RTL (Phase 1), the scoreboard/assertions (Phase 2/4), and the coverage model (Phase 3). Changes here should propagate to those phases.*
