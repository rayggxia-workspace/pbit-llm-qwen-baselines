// Composite operation integration probe for ONNXim a1e86296e080fa1c82f8ad3f1b6de1079c192afc.
// Timing/transport only: ONNXim SRAM carries validity, not numerical payloads.
#include <algorithm>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <optional>
#include <set>
#include <stdexcept>
#include "SystolicWS.h"
#include "gtest/gtest.h"
#include "operations/Operation.h"

namespace {
class ThresholdTransportProbe final : public Operation {
 public:
  ThresholdTransportProbe(SimulationConfig config, MappingTable& table)
      : Operation(config, table, 0) {
    _name = "threshold_transport_probe";
    _optype = "PBitThresholdTransportProbe";
    _model = nullptr;
    initialize_tiles(table);
  }

  void initialize_tiles(MappingTable&) override {
    auto tile = std::make_unique<Tile>(Tile{});
    tile->status = Tile::Status::INITIALIZED;
    tile->layer_id = _id;
    tile->optype = _optype;
    tile->skip = false;
    tile->core_id = 0;
    auto load = std::make_unique<Instruction>(Instruction{});
    load->opcode = Opcode::MOVIN;
    load->dest_addr = SPAD_BASE;
    load->size = 2;
    load->src_addrs = {0x1000, 0x1020};
    load->operand_id = _INPUT_OPERAND;
    tile->instructions.push_back(std::move(load));
    auto compare = std::make_unique<Instruction>(Instruction{});
    compare->opcode = Opcode::COMP;
    compare->dest_addr = SPAD_BASE + 128;
    compare->size = 1;
    compare->compute_size = 64;  // bytes, as consumed by ONNXim vector iteration model
    compare->src_addrs = {SPAD_BASE};
    tile->instructions.push_back(std::move(compare));
    auto store = std::make_unique<Instruction>(Instruction{});
    store->opcode = Opcode::MOVOUT;
    store->dest_addr = SPAD_BASE + 128;
    store->size = 1;
    store->src_addrs = {0x2000};
    store->operand_id = _OUTPUT_OPERAND;
    tile->instructions.push_back(std::move(store));
    _tiles.push_back(std::move(tile));
  }
};

class InspectableCore final : public SystolicWS {
 public:
  using SystolicWS::SystolicWS;
  cycle_type vector_active_cycles() const { return _stat_vec_compute_cycle; }
};

struct Response { MemoryAccess* access; cycle_type due; };

json run_probe(const std::string& name, unsigned window, unsigned latency,
               bool out_of_order = false, unsigned vector_bits = 64) {
  CoreConfig core_config{};
  core_config.core_type = CoreType::SYSTOLIC_WS;
  core_config.core_height = 8;
  core_config.core_width = 8;
  core_config.vector_process_bit = vector_bits;
  core_config.sram_width = 32;
  core_config.spad_size = 64;
  core_config.accum_spad_size = 16;
  SimulationConfig config{};
  config.num_cores = 1;
  config.core_config = &core_config;
  config.core_freq = 100;
  config.core_print_interval = 1000000;
  config.precision = 1;
  config.dram_req_size = 32;
  config.layout = "NHWC";
  MappingTable table;
  ThresholdTransportProbe operation(config, table);
  InspectableCore core(0, config);
  auto& tiles = operation.get_tiles();
  if (tiles.size() != 1 || tiles.front()->skip || tiles.front()->instructions.size() != 3)
    throw std::runtime_error("custom operation did not produce real instructions");
  core.issue(std::move(tiles.front()));
  tiles.pop_front();

  json events = json::array();
  std::vector<Response> pending;
  std::set<unsigned> accepted, completed;
  std::vector<addr_type> read_returns;
  cycle_type cycle = 0, last_read = 0, write_accept = 0;
  unsigned reads = 0, writes = 0, peak = 0, refusals = 0;
  std::optional<std::pair<unsigned, addr_type>> refused_front;
  while (core.running() || !pending.empty()) {
    if (cycle > 10000) throw std::runtime_error("custom operation timeout");
    // Select from the previously accepted set. At most one response per edge.
    auto next = std::min_element(pending.begin(), pending.end(), [](const auto& a, const auto& b) {
      return std::make_pair(a.due, a.access->id) < std::make_pair(b.due, b.access->id);
    });
    if (next != pending.end() && next->due <= cycle) {
      auto* response = next->access;
      if (!completed.insert(response->id).second) throw std::runtime_error("duplicate response");
      events.push_back({{"event", "return"}, {"cycle", cycle}, {"id", response->id},
                        {"address", response->dram_address}, {"write", response->write}});
      if (!response->write) { last_read = cycle; read_returns.push_back(response->dram_address); }
      response->request = false;
      core.push_memory_response(response);  // takes ownership and deletes the response
      pending.erase(next);
    }
    core.cycle();
    if (refused_front && (!core.has_memory_request() ||
        *refused_front != std::make_pair(core.top_memory_request()->id,
                                        core.top_memory_request()->dram_address)))
      throw std::runtime_error("refused request was lost or replaced before acceptance");
    // External memory accepts one request per cycle with a finite descriptor window.
    if (core.has_memory_request() && pending.size() < window) {
      auto* access = core.top_memory_request();
      core.pop_memory_request();
      refused_front.reset();
      if (!accepted.insert(access->id).second) throw std::runtime_error("duplicate request");
      if (access->write) { ++writes; write_accept = cycle; } else { ++reads; }
      unsigned delay = latency;
      if (out_of_order && !access->write) delay = access->dram_address == 0x1000 ? 11 : 2;
      pending.push_back({access, cycle + delay});
      events.push_back({{"event", "accept"}, {"cycle", cycle}, {"id", access->id},
                        {"address", access->dram_address}, {"write", access->write}});
      peak = std::max<unsigned>(peak, pending.size());
    } else if (core.has_memory_request()) {
      ++refusals;
      auto* front = core.top_memory_request();
      refused_front = std::make_pair(front->id, front->dram_address);
      events.push_back({{"event", "refuse"}, {"cycle", cycle}, {"id", front->id},
                        {"address", front->dram_address}, {"write", front->write}});
    }
    ++cycle;
  }
  auto finished = core.pop_finished_tile();
  if (!finished || finished->status != Tile::Status::FINISH || finished->skip || accepted != completed ||
      reads != 2 || writes != 1 || peak > window || write_accept <= last_read)
    throw std::runtime_error("request conservation, dependency or tile-completion invariant failed");
  json result = {{"name", name}, {"finish_cycles", cycle}, {"window", window},
                 {"latency_cycles", latency}, {"vector_bits", vector_bits},
                 {"reads", reads}, {"writes", writes}, {"peak_inflight", peak},
                 {"refused_cycles", refusals}, {"last_read_return", last_read},
                 {"write_accept", write_accept}, {"read_return_addresses", read_returns},
                 {"vector_active_cycles", core.vector_active_cycles()}, {"events", events},
                 {"scope", "custom Operation to Tile to native COMP transport timing; no numerical payload"}};
  if (const char* out = std::getenv("ONNXIM_PROBE_OUTPUT")) {
    std::filesystem::create_directories(out);
    std::ofstream file(std::filesystem::path(out) / (name + ".json"));
    file << result.dump(2) << '\n';
    if (!file) throw std::runtime_error("failed to persist probe evidence");
  }
  return result;
}
}  // namespace

TEST(PBitThresholdTransportProbeTest, NativeOperationAndFiniteMemory) {
  auto baseline = run_probe("baseline", 8, 2);
  auto bounded = run_probe("bounded_long_memory", 1, 11);
  auto reordered = run_probe("out_of_order", 8, 2, true);
  auto narrow = run_probe("narrow_vector", 8, 2, false, 32);
  EXPECT_EQ(baseline["vector_active_cycles"], 8);
  EXPECT_EQ(narrow["vector_active_cycles"], 16);
  EXPECT_GT(bounded["finish_cycles"].get<unsigned>(), baseline["finish_cycles"].get<unsigned>());
  EXPECT_GT(bounded["refused_cycles"].get<unsigned>(), 0);
  EXPECT_EQ(bounded["peak_inflight"], 1);
  EXPECT_EQ(reordered["read_return_addresses"], json({0x1020, 0x1000}));
  EXPECT_EQ(narrow["finish_cycles"].get<unsigned>() - baseline["finish_cycles"].get<unsigned>(), 8);
}
