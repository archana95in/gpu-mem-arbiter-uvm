// ---------------------------------------------------------------------------
// gpu_mem_arbiter_assertions.sv
//
// Phase 4 correctness checks for gpu_mem_arbiter, per SPEC.md section 6.
// Instantiated alongside the DUT (not edited into it -- gpu_mem_arbiter.sv
// itself doesn't change) by gpu_mem_arbiter_tb_top.sv, which wires this
// module's age/busy_cnt ports to the DUT instance's internal signals via
// a plain hierarchical reference. PHASE4_PLAN.md's original structure
// called for a `bind` statement instead; the section 0 capability check
// found Icarus Verilog 13.0 doesn't implement `bind` at all
// (`-gbind` reports "Unknown/Unsupported Language generation bind", and
// there's no flag to enable it) -- a plain wrapper module achieves the
// same "verification code doesn't touch the RTL file" separation bind
// would have given, just via an explicit instance-and-wire-through
// module instead of `bind`'s automatic scope injection.
//
// Written entirely as IMMEDIATE assertions (procedural `assert (...)
// else ...;` inside `always @(posedge clk)`), not concurrent
// `assert property`. The same section 0 capability check (tb/sva/
// sva_smoke_test.sv) found Icarus doesn't parse concurrent assertions
// with an implication operator (`|->`) at all -- a hard syntax error
// ("Error in property_spec"), not just unsupported for the ranged-delay
// `##[0:N]` operator this project anticipated needing a fallback for.
// `$past()` is also undefined here. Immediate assertions work fully and
// do fire on violations (verified directly: a deliberately-bad
// $onehot0 case printed the violation message).
//
// age/busy_cnt aren't part of the pin-level interface in SPEC.md
// section 3 -- accessing them via hierarchical reference from the
// wrapper is the same whitebox-internal-signal-peeking approach the
// Phase 3 cocotb monitor already uses from the Python side.
// ---------------------------------------------------------------------------

module gpu_mem_arbiter_assertions #(
  parameter int NUM_CLIENTS = 3,
  parameter int AGE_WIDTH   = 8,
  parameter int BUSY_W      = 3
) (
  input logic                    clk,
  input logic                    rst_n,
  input logic [NUM_CLIENTS-1:0]  req,
  input logic [NUM_CLIENTS-1:0]  gnt,
  input logic                    bus_busy,
  input logic [AGE_WIDTH-1:0]    age [NUM_CLIENTS],
  input logic [BUSY_W-1:0]       busy_cnt
);

  // SPEC.md section 5's age thresholds, independently restated here
  // rather than reused from the RTL's own age_th_of() -- this should
  // check the implementation against the spec's stated intent, not
  // against itself (reusing the DUT's own function would make the
  // liveness check tautological against a bug in that function).
  // Port map (SPEC.md section 2): 0 = COMPUTE, 1 = TEXTURE, 2 = DISPLAY
  function automatic int age_threshold(input int idx);
    case (idx)
      0: return 32; // COMPUTE
      1: return 16; // TEXTURE
      2: return 8;  // DISPLAY
      default: return 0;
    endcase
  endfunction

  // -------------------------------------------------------------------
  // Shadow registers -- $past() isn't available under Icarus 13.0
  // (confirmed by the section 0 capability check), so mirror the two
  // signals the phantom-grant and no-grant-mid-burst checks need "as
  // of the previous edge" by hand.
  // -------------------------------------------------------------------
  logic [NUM_CLIENTS-1:0] req_prev;
  logic [BUSY_W-1:0]      busy_prev;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      req_prev  <= '0;
      busy_prev <= '0;
    end else begin
      req_prev  <= req;
      busy_prev <= busy_cnt;
    end
  end

  // -------------------------------------------------------------------
  // Safety (SPEC.md section 6)
  // -------------------------------------------------------------------
  always @(posedge clk) begin
    if (rst_n) begin
      // Exactly one gnt bit set, never more than one.
      a_no_double_grant: assert ($onehot0(gnt))
        else $error("SVA a_no_double_grant: more than one gnt bit set: gnt=%b", gnt);

      // bus_busy is a combinational function of busy_cnt in the RTL;
      // a cheap consistency check that the port is actually wired the
      // way the DUT's own assign statement says it should be.
      a_bus_busy_consistent: assert (bus_busy == (busy_cnt != '0))
        else $error("SVA a_bus_busy_consistent: bus_busy=%b busy_cnt=%0d", bus_busy, busy_cnt);

      // No grant mid-burst. NOTE: busy_cnt itself is NOT the right
      // signal to gate this on -- the grant pulse and the first cycle
      // of the busy hold are the SAME cycle (gnt[win]<=1 and
      // busy_cnt<=BURST_LEN-1 are set by the same clocked block, same
      // edge, in the RTL), so "bus_busy |-> gnt=='0" as literally
      // suggested in PHASE4_PLAN.md section 2 would false-fire on
      // every single legitimate grant. busy_prev (busy_cnt as of the
      // *previous* edge, i.e. going into this decision) correctly
      // excludes the grant cycle itself while still catching a real
      // grant during an already-in-progress hold.
      a_no_grant_mid_burst: assert (busy_prev == 0 || gnt == '0)
        else $error("SVA a_no_grant_mid_burst: gnt=%b asserted with busy_prev=%0d", gnt, busy_prev);

      // Phantom grant: a client can only be granted if it was actually
      // requesting at decision time -- one cycle before the grant
      // becomes visible, since gnt is a registered output set from a
      // combinational read of req at the previous edge.
      for (int i = 0; i < NUM_CLIENTS; i++) begin
        a_no_phantom_grant: assert (!gnt[i] || req_prev[i])
          else $error("SVA a_no_phantom_grant: client %0d granted without a prior request (req_prev=%b)", i, req_prev);
      end

      // ---------------------------------------------------------------
      // Liveness / starvation-freedom (SPEC.md section 6)
      //
      // The natural SVA statement would be a bounded-range implication
      // (req[i] |-> ##[0:N] gnt[i]) -- impossible here per the section 0
      // capability check. SPEC.md section 5 defines the bound directly
      // in terms of the age counter ("age counter... reset to 0 the
      // cycle it is granted... age threshold (the hard starvation
      // bound)"), so asserting the invariant age[i] <= threshold[i]
      // every cycle is a faithful, direct translation of the spec's
      // own definition, not an approximation of the ##[0:N] idiom.
      //
      // Note: Phase 3 found COMPUTE/TEXTURE's natural weighted-round-
      // robin gap under full contention is well under their thresholds
      // (max observed ~3-4 decisions against thresholds of 32/16), so
      // this invariant may sit far from firing for those two classes
      // in the existing Phase 3 stimulus -- expected, not a hole in
      // this check. DISPLAY's aging path is the one actually exercised.
      // ---------------------------------------------------------------
      for (int i = 0; i < NUM_CLIENTS; i++) begin
        a_liveness_bound: assert (age[i] <= age_threshold(i))
          else $error("SVA a_liveness_bound: client %0d age %0d exceeded threshold %0d",
                       i, age[i], age_threshold(i));
      end
    end
  end

endmodule
