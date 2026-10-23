# Encoding / restoration handshake boundary

`er_pot_encoder_rv` reuses `nr_pot_encoder` verbatim for complete B4/N64
BF16 or FP32 groups. Its 785-bit payload contains q, bin, original input sign,
true-one, top exponent and invalid flag; a 32-bit transaction tag is additional.
The functional arithmetic checks use finite inputs. The wrapper passes the
existing invalid flag through; it does not define useful numerical output for
NaN/Inf groups.

`er_bin_restore_rv` reuses the literal `nr_bin_restore(FUSED=0)` implementation.
One operation restores one full output containing all four bins. Its bus is
**input-sign / W8 two's-complement bit planes**, flattened as
`((bin*2+input_sign)*8+weight_bit)*COUNT_W`. The bit7 positional coefficient is
-128. Product-sign / magnitude counters must first be converted to this
representation or to signed per-bin integer sums by a separately verified
adapter; their raw bus is incompatible. The wrapper does not implement that
conversion or an alternative signed-sum datapath.

Every accepted input reserves one result slot. `reserved_count` includes
unfinished operations and completed outputs; `queued_count` includes only
completed outputs. The core can therefore finish after downstream ready drops
without losing a result. Full queues can accept on an actual same-edge output
handshake. Output data and tag remain stable until that handshake. Synchronous
active-low reset flushes both pipeline and reserved/queued results. Clocking and
reset are one domain; there is no CDC logic.

| Wrapper | Accept at edge k: first visible output | Earliest output handshake | Slots for continuous II=1 |
|---|---:|---:|---:|
| Encoder | after k+2 | k+3 | 3 |
| Literal restoration | after k+1 | k+2 | 2 |

These explicit RTL edge counts include the wrapper boundary, not STA-verified
delays. With a single slot, reservation lifetime makes II=3 and II=2 respectively.
The encoder's extra result-register edge is explicit; no free bypass was added.
Output slots store full results and tags: by default 817 bits per encoder slot,
64 bits per restoration slot, plus occupancy/pointers and existing core state.
They are hardware state, not SRAM response credits or free storage. Physical
area, frequency and energy are unknown.

`sim/validate_ready_valid.py` compiles and runs self-checking RTL. Its 27 default
cases cover three seeds, slot depths 1/3/5, BF16/FP32 encoding and T32 restoration;
continuous traffic, independent bubbles/stalls, queue saturation, simultaneous
pop/accept, ordering, stable stalled output, reset with full queues and drain are
checked. Exact gold reuses the previously validated integer FP oracle; arbitrary
bounded count patterns are synthetic, not proof of SC-event reachability.

Example (Linux, under an assigned CPU allocation when on a shared host):

```sh
python -B architecture_tlm/encoding_restore_contract/sim/validate_ready_valid.py \
  --iverilog /usr/bin/iverilog --vvp /usr/bin/vvp \
  --build-dir /absolute/personal/path/new-build \
  --out /absolute/personal/path/new-evidence
```

Both output directories must be new. Keep compiled `.vvp` binaries and generated
stimulus in the build directory, outside the published source/evidence tree.
`VALIDATION.json` and `COMMANDS.json` capture source/tool hashes and actual
results; their presence with `passed=false` records a failed run, not validation.
