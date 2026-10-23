# Existing Ramulator integration boundary

Read-only inspection on 2026-10-23 (server UTC+8), while GQA validation was
prepared. No library was modified, installed, compiled or executed for this
assessment. Root: `/home/Weican_Chen/projects/tlm-cycle-issue116-20261023/ONNXim-archive`.

| Existing artifact | Size | SHA-256 |
|---|---:|---|
| `build/lib/libramulator1.a` | 787978 | `55d8f59f1c04ed7b35c33251220b1603e6ff6bb426869a5bc309393f4df8e0d5` |
| `build/lib/libramulator.so` | 4092536 | `bea1809754bf775e04f0805ec881088cfa62799e7f41a3de1d2a915eb87a7daf` |

The first is the custom Ramulator 1 static library, already linked into
`build/bin/Simulator_test`. Its public C++ header is
`extern/ramulator_custom/include/ramulator/Ramulator.hpp`:

```cpp
Ramulator(const std::string config, uint32_t num_core, bool is_pim=false);
bool isAvailable(uint64_t addr, bool is_write) const;
void push(uint64_t addr, bool is_write, uint32_t core_id, void* original_req);
void tick();
bool isEmpty(int channel) const;
const void* top(int channel) const;
void pop(int channel);
int getAtomicBytes() const;
int getNumChannels() const;
int getChannel(uint64_t addr) const;
```

There are also explicit-channel overloads. The wrapper reserves one return
slot on each accepted request, with capacity 256 per channel; its internal
read/write callbacks enqueue the original request pointer. It transports
request identity/timing, without numeric memory payloads. Construction
sets the statistics output to `./ramulator.stats`, so any future execution
must use a dedicated working directory. Its factory supports DDR4 and HBM.

`extern/ramulator_custom/src/Memory.h:34` exposes virtual `double clk_ns()`,
`void tick()` and `bool send(Request)`. `clk_ns()` at line 283 returns the
DRAM speed table's `tCK`; the public Ramulator wrapper does not expose it.
The supplied `configs/ramulator_configs/DDR4-config.cfg` selects DDR4_3200,
whose actual table entry in `src/DDR4.h:203` gives 0.625 ns (625 integer ps).

The write callback is **a posted write command-issued acknowledgment**.
`src/Controller.h:455` issues the command. After confirming it is the final
command, lines 476-478 invoke the WRITE callback immediately; there is no
future write-completion timer for nCWL/nBL/nWR. Reads instead set
`depart=clk+read_latency` at line 472, and the pending queue invokes a
callback when that time is reached (lines 353-361), at most one read return
per channel per tick. A future adapter must preserve this distinction and
must not label the write callback as full DRAM write completion.

The second library is Ramulator 2 and exposes the C++ `NDPSim::Ramulator2`
wrapper in `extern/ramulator2/resources/ndp_wrappers/ramulator2.hh`:
`full()`, `push(mem_fetch*)`, `cycle()`, `return_queue_top()` and
`return_queue_pop()`. `full()` uses a 256-entry request queue; the inspected
return queue has no explicit capacity bound. It is not a ready C ABI for
Python `ctypes`. Existing configurations include
`configs/ramulator2_configs/{DDR4,HBM2}.yaml`.

A small independent C ABI bridge or IPC process could reuse these existing
libraries without rebuilding ONNXim. Correct cycle integration still needs
an explicit accept/reject boundary, DRAM clock, burst size/address mapping,
finite output credits, response delivery ordering, numeric backing storage
and a posted-write contract. The current cycle kernel's built-in memory
runtime predicts completion and owns bank state, so it cannot acquire this
backend simply by replacing a latency constant. This inspection establishes
API feasibility; it is not evidence that an online adapter has been built,
tested, or integrated into the FFN/Attention chains.
