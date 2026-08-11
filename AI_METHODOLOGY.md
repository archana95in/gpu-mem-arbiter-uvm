# AI-Assisted Development Methodology

AI assistance (Claude / Claude Code) was used throughout this project's development, the same way it's used as a productivity tool in engineering today. This is a short, honest account of the division of labor — not a disclaimer, not a pitch.

## Division of labor

The AI wrote most of the RTL and testbench code, debugged tool errors, and ran a large-scale adversarial search in Phase 5. It did not decide what was worth testing, recognize when a result looked wrong, judge whether a mismatch was a real bug or a tooling quirk, or accept a finding without checking it against the real RTL. Those calls were mine.

Three concrete examples, pulled from this project's own history:

- **A suspicious pass.** An early bandwidth check reported a ~33/33/33 grant split — plausible-looking, but wrong: the spec calls for 50/30/20. An even split is exactly what you'd get if the weighting logic were broken (it was — a credit-reset bug). Recognizing that the *even* result was itself the tell was the judgment call.
- **A zero-hit coverage bin, doubted rather than trusted.** A functional coverage bin read zero hits across a 34,000-decision run, even during a scenario designed to stress it. The instinct to check whether the *instrument* was broken before believing the *design* was correct paid off — the monitor's sampling order had a bug that silently zeroed every measurement.
- **A hypothesis tested instead of trusted.** Phase 5 started from a reasonable-sounding claim (two client classes' starvation thresholds were probably unreachable). Rather than write that into the spec on the strength of the argument, it was tested with a model, an adversarial search, and cross-validation against the real RTL — and the hypothesis was wrong. Full account: `docs/phases/PHASE5_LOG.md`.

## Bottom line

AI assistance materially sped up writing and debugging code. It did not replace deciding what to build, what "correct" means for this design, or whether a result should be believed.
