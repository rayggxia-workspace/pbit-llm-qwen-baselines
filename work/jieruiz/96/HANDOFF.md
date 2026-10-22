# Issue96 unified TLM v6

Owner jieruiz; branch task/96-unified-tlm; base83e15289434af50fc09c35e699d8b39965389d98. Independent sparse checkout tmp/unified-tlm-issue96-20261022. Source implementation and operator contracts are in architecture_tlm/unified_v6/.

20 mechanism tests pass (signed bitplanes vs direct products, shared gu input, T/K, resource conflicts, live-buffer bounds, GQA V union, full geometry2K/8K and all7 attention modes). Full Qwen24 initial unarchived smoke completed; not final frozen evidence. No PPL/GPU/PT/new DRAMSys run. Next: commit source, execute immutable complete-decode scenarios, verify manifests and publish report/PR. Random backend belongs to Issue95; this task only consumes a local interface with zero random-stream SRAM. Existing Issue37/78 work is untouched. Physical PPA remains unknown.
