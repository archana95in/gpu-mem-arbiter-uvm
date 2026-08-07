TOPLEVEL_LANG = verilog
SIM ?= icarus

VERILOG_SOURCES = ../../rtl/gpu_mem_arbiter.sv ../sva/gpu_mem_arbiter_assertions.sv ../sva/gpu_mem_arbiter_tb_top.sv
TOPLEVEL = gpu_mem_arbiter_tb_top
MODULE = test_arbiter

COMPILE_ARGS += -g2012

include $(shell cocotb-config --makefiles)/Makefile.sim
