module sva_smoke_test;
  logic clk = 0;
  logic req, gnt;
  always #5 clk = ~clk;

  // Safety: immediate + simple concurrent assertion.
  always @(posedge clk) begin
    a_simple: assert (!(req && gnt) || 1); // trivial, just confirms parsing
  end

  // The construct that actually matters: bounded-range delay implication,
  // needed for the starvation-freedom property below.
  property p_bounded_eventually;
    @(posedge clk) req |-> ##[0:8] gnt;
  endproperty
  a_bounded: assert property (p_bounded_eventually);

  initial begin
    req = 0; gnt = 0;
    #100 $display("SVA smoke test ran to completion");
    $finish;
  end
endmodule
