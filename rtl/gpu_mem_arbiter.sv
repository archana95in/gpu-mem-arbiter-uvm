// ---------------------------------------------------------------------------
// gpu_mem_arbiter.sv
//
// Read-address arbiter for a shared GPU memory bus with 3 fixed client
// ports (COMPUTE, TEXTURE, DISPLAY). Implements a credit-based weighted
// round-robin policy with a per-class aging override to guarantee a hard
// upper bound on wait time (starvation-freedom). See SPEC.md for the full
// design rationale, weights, and age thresholds.
//
// Port map: 0 = COMPUTE, 1 = TEXTURE, 2 = DISPLAY
// ---------------------------------------------------------------------------

module gpu_mem_arbiter #(
  parameter int NUM_CLIENTS = 3,
  parameter int ADDR_WIDTH  = 32,
  parameter int BURST_LEN   = 4,
  parameter int AGE_WIDTH   = 8,
  parameter int CREDIT_WIDTH = 16
) (
  input  logic                    clk,
  input  logic                    rst_n,

  // Per-client request/address
  input  logic [NUM_CLIENTS-1:0]  req,
  input  logic [ADDR_WIDTH-1:0]   addr [NUM_CLIENTS],

  // Grant (1-cycle pulse) and the address of the granted transaction
  output logic [NUM_CLIENTS-1:0]  gnt,
  output logic [ADDR_WIDTH-1:0]   gnt_addr,
  output logic                    bus_busy
);

  // -------------------------------------------------------------------
  // Static policy tables (see SPEC.md sections 2 and 5).
  // Implemented as functions rather than unpacked-array localparams --
  // functionally identical, but avoids an array-localparam portability
  // gap in some simulators' SystemVerilog front ends.
  // -------------------------------------------------------------------
  function automatic int weight_of(input int idx);
    case (idx)
      0: return 5; // COMPUTE
      1: return 3; // TEXTURE
      2: return 2; // DISPLAY
      default: return 0;
    endcase
  endfunction

  function automatic int age_th_of(input int idx);
    case (idx)
      0: return 32; // COMPUTE
      1: return 16; // TEXTURE
      2: return 8;  // DISPLAY
      default: return 0;
    endcase
  endfunction

  localparam int BUSY_W = (BURST_LEN <= 1) ? 1 : $clog2(BURST_LEN + 1);

  // Sum of all client weights (5 + 3 + 2). Used for the surplus/deficit
  // credit update below -- update this if the weights in weight_of()
  // change. Hardcoded rather than computed to keep this portable across
  // simulators with varying support for constant function evaluation.
  localparam int TOTAL_WEIGHT = 10;

  // -------------------------------------------------------------------
  // State
  //
  // `credit` is SIGNED. Winner-selection subtracts TOTAL_WEIGHT from the
  // winner's credit (a "surplus/deficit" update) rather than resetting
  // it to zero. Resetting to zero was tried first and found -- via the
  // Phase-1 smoke test -- to discard a winner's earned surplus, which
  // collapses the scheme to plain round-robin regardless of weight
  // (verified: produced an even ~33/33/33 split instead of the spec's
  // 50/30/20). Carrying the debt forward via subtraction is the standard
  // fix used in weighted fair queueing schedulers.
  // -------------------------------------------------------------------
  logic [AGE_WIDTH-1:0]           age    [NUM_CLIENTS];
  logic signed [CREDIT_WIDTH-1:0] credit [NUM_CLIENTS];
  logic [BUSY_W-1:0]              busy_cnt;

  logic [NUM_CLIENTS-1:0]  aged_out;

  assign bus_busy = (busy_cnt != '0);

  // -------------------------------------------------------------------
  // Combinational: who has aged past their threshold this cycle?
  // -------------------------------------------------------------------
  always_comb begin
    for (int i = 0; i < NUM_CLIENTS; i++) begin
      aged_out[i] = req[i] && (age[i] >= age_th_of(i));
    end
  end

  // -------------------------------------------------------------------
  // Winner-selection helpers.
  // Aging override: among aged-out requesters, highest weight wins;
  // ties broken by lowest port index (deterministic, checked in TB).
  // Weighted round robin: among all requesters, highest credit wins;
  // ties broken by lowest port index.
  // -------------------------------------------------------------------
  function automatic int select_aged_winner(
    input logic [NUM_CLIENTS-1:0] aged_out_v
  );
    int best;
    begin
      best = -1;
      for (int i = 0; i < NUM_CLIENTS; i++) begin
        if (aged_out_v[i]) begin
          if (best == -1 || weight_of(i) > weight_of(best)) best = i;
        end
      end
      return best;
    end
  endfunction

  // Weighted round-robin winner selection is inlined directly in the
  // always_ff below (rather than a function taking the `credit` array)
  // because unpacked-array subroutine ports aren't supported by every
  // simulator front end.

  // -------------------------------------------------------------------
  // Sequential: arbitration decision, age/credit bookkeeping, busy timer
  // -------------------------------------------------------------------
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      gnt      <= '0;
      gnt_addr <= '0;
      busy_cnt <= '0;
      for (int i = 0; i < NUM_CLIENTS; i++) begin
        age[i]    <= '0;
        credit[i] <= '0;
      end
    end else begin
      gnt <= '0; // grant is a 1-cycle pulse; default deassert every cycle

      if (busy_cnt != 0) begin
        // Bus owned by an in-flight burst — just count down, no new
        // arbitration decision, and freeze age/credit bookkeeping so a
        // waiting client isn't penalized for a burst it can't preempt.
        busy_cnt <= busy_cnt - 1'b1;
      end else begin
        int win;
        win = -1;

        if (|aged_out) begin
          win = select_aged_winner(aged_out);
        end else if (|req) begin
          for (int i = 0; i < NUM_CLIENTS; i++) begin
            if (req[i]) begin
              if (win == -1 || credit[i] > credit[win]) win = i;
            end
          end
        end

        if (win != -1) begin
          gnt[win]  <= 1'b1;
          gnt_addr  <= addr[win];
          busy_cnt  <= BUSY_W'(BURST_LEN - 1);
        end

        for (int i = 0; i < NUM_CLIENTS; i++) begin
          if (i == win) begin
            age[i]    <= '0;
            credit[i] <= credit[i] - TOTAL_WEIGHT; // surplus/deficit update, not reset
          end else if (req[i]) begin
            age[i]    <= age[i] + 1'b1;
            credit[i] <= credit[i] + weight_of(i);
          end else begin
            // Not requesting this cycle: reset bookkeeping. A client that
            // drops and re-raises req starts its wait/credit clock over.
            age[i]    <= '0;
            credit[i] <= '0;
          end
        end
      end
    end
  end

endmodule
