// ---------------------------------------------------------------------------
// gpu_mem_arbiter_tb_top.sv
//
// Simulation top for Phase 4: instantiates the real DUT plus the
// assertion checker side by side, forwarding every DUT port straight
// through at this module's own boundary under the same names -- so
// cocotb's existing Phase 2/3 testbench code (which reads/drives
// cocotb.top.clk, .req, .gnt, etc., assuming top IS the DUT) keeps
// working unmodified with COCOTB_TOPLEVEL pointed at this wrapper
// instead of at gpu_mem_arbiter directly.
//
// This exists only because Icarus Verilog 13.0 doesn't implement
// `bind` (see gpu_mem_arbiter_assertions.sv's header) -- otherwise the
// checker would bind directly onto gpu_mem_arbiter with no wrapper
// needed. u_assertions.age/busy_cnt connect to u_dut's internal
// signals via plain hierarchical reference, which Icarus does support.
//
// BUSY_W=3 matches gpu_mem_arbiter's own localparam computation
// ($clog2(BURST_LEN+1) with the default BURST_LEN=4) -- it's a
// localparam in the RTL, not an exposed module parameter, so it's
// restated here rather than derived.
// ---------------------------------------------------------------------------

module gpu_mem_arbiter_tb_top #(
  parameter int NUM_CLIENTS  = 3,
  parameter int ADDR_WIDTH   = 32,
  parameter int BURST_LEN    = 4,
  parameter int AGE_WIDTH    = 8,
  parameter int CREDIT_WIDTH = 16
) (
  input  logic                    clk,
  input  logic                    rst_n,
  input  logic [NUM_CLIENTS-1:0]  req,
  input  logic [ADDR_WIDTH-1:0]   addr [NUM_CLIENTS],
  output logic [NUM_CLIENTS-1:0]  gnt,
  output logic [ADDR_WIDTH-1:0]   gnt_addr,
  output logic                    bus_busy
);

  gpu_mem_arbiter #(
    .NUM_CLIENTS(NUM_CLIENTS),
    .ADDR_WIDTH(ADDR_WIDTH),
    .BURST_LEN(BURST_LEN),
    .AGE_WIDTH(AGE_WIDTH),
    .CREDIT_WIDTH(CREDIT_WIDTH)
  ) u_dut (
    .clk(clk),
    .rst_n(rst_n),
    .req(req),
    .addr(addr),
    .gnt(gnt),
    .gnt_addr(gnt_addr),
    .bus_busy(bus_busy)
  );

  gpu_mem_arbiter_assertions #(
    .NUM_CLIENTS(NUM_CLIENTS),
    .AGE_WIDTH(AGE_WIDTH),
    .BUSY_W(3)
  ) u_assertions (
    .clk(clk),
    .rst_n(rst_n),
    .req(req),
    .gnt(gnt),
    .bus_busy(bus_busy),
    .age(u_dut.age),
    .busy_cnt(u_dut.busy_cnt)
  );

endmodule
