TOPLEVEL_LANG = verilog
SIM ?= icarus

VERILOG_SOURCES = ../../rtl/gpu_mem_arbiter.sv
TOPLEVEL = gpu_mem_arbiter
MODULE = test_arbiter

COMPILE_ARGS += -g2012

include $(shell cocotb-config --makefiles)/Makefile.sim
