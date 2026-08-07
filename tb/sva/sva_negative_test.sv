// ---------------------------------------------------------------------------
// sva_negative_test.sv
//
// Confirms gpu_mem_arbiter_assertions.sv's checks actually fire, rather
// than being silently inert -- drives the checker directly (not
// through the real DUT) with one deliberately-bad value per property,
// in isolation, so each check is exercised on purpose rather than
// hoping to coerce the real arbiter into each illegal state. Not part
// of the cocotb regression; run standalone with:
//   iverilog -g2012 -o sva_negative_test.out \
//     gpu_mem_arbiter_assertions.sv sva_negative_test.sv && \
//     vvp sva_negative_test.out
// Expect at least one $error per case below covering all five checks --
// state isn't fully reset between cases, so a few cases trip more than
// one check at once (e.g. case 1's gnt=011 also has no matching prior
// req, so a_no_phantom_grant fires alongside a_no_double_grant). That
// cross-triggering is fine: the goal is confirming each of the five
// checks fires at least once with the right diagnostic, not isolating
// them perfectly from each other.
// ---------------------------------------------------------------------------

module sva_negative_test;
  localparam int NUM_CLIENTS = 3;
  localparam int AGE_WIDTH   = 8;
  localparam int BUSY_W      = 3;

  logic clk = 0;
  logic rst_n = 0;
  logic [NUM_CLIENTS-1:0] req = '0;
  logic [NUM_CLIENTS-1:0] gnt = '0;
  logic bus_busy = 1'b0;
  logic [AGE_WIDTH-1:0] age [NUM_CLIENTS];
  logic [BUSY_W-1:0] busy_cnt = '0;

  always #5 clk = ~clk;

  gpu_mem_arbiter_assertions #(
    .NUM_CLIENTS(NUM_CLIENTS),
    .AGE_WIDTH(AGE_WIDTH),
    .BUSY_W(BUSY_W)
  ) u_assertions (
    .clk(clk), .rst_n(rst_n), .req(req), .gnt(gnt), .bus_busy(bus_busy),
    .age(age), .busy_cnt(busy_cnt)
  );

  initial begin
    for (int i = 0; i < NUM_CLIENTS; i++) age[i] = '0;

    // Come out of reset with everything legal for one cycle so the
    // checker's shadow registers (req_prev/busy_prev) settle cleanly.
    @(posedge clk); @(posedge clk);
    rst_n = 1;
    @(posedge clk);

    $display("--- case 1: a_no_double_grant (gnt=011, two bits set) ---");
    gnt = 3'b011;
    @(posedge clk);
    gnt = '0;

    $display("--- case 2: a_bus_busy_consistent (bus_busy=0 while busy_cnt=2) ---");
    busy_cnt = 3'd2;
    bus_busy = 1'b0;
    @(posedge clk);
    busy_cnt = '0;
    bus_busy = 1'b0;

    $display("--- case 3: a_no_grant_mid_burst (gnt asserted while busy_prev!=0) ---");
    // Force an in-progress hold: busy_cnt nonzero for one full cycle
    // first so busy_prev picks it up, then assert gnt while it's still
    // mid-hold.
    busy_cnt = 3'd2;
    @(posedge clk); // busy_prev now latches 2
    gnt = 3'b001;
    @(posedge clk);
    gnt = '0;
    busy_cnt = '0;

    $display("--- case 4: a_no_phantom_grant (gnt to client with no prior req) ---");
    req = '0;
    @(posedge clk); // req_prev now latches 0 for all clients
    gnt = 3'b100; // client 2 granted despite req_prev[2] == 0
    @(posedge clk);
    gnt = '0;

    $display("--- case 5: a_liveness_bound (client 2's age exceeds its threshold of 8) ---");
    age[2] = 8'd9;
    @(posedge clk);
    age[2] = '0;

    @(posedge clk);
    $display("--- negative test complete ---");
    $finish;
  end
endmodule
