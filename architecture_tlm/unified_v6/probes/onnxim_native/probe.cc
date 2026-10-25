// Issue186 original integration harness; upstream ONNXim is MIT licensed.
// Actual Core/WS/SRAM implementation stays unchanged. SC is a busy-time hook,
// not numerical FFN execution. External memory below is synthetic, not DRAMSys.
#include <algorithm>
#include <fstream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>
#include "Common.h"
#include "Core.h"
#include "SystolicWS.h"
uint32_t generate_mem_access_id() { static uint32_t n=0; return n++; }
uint32_t generate_id() { static uint32_t n=0; return n++; }
class ProbeCore:public SystolicWS {
 public:
  ProbeCore(SimulationConfig c,uint64_t sc):SystolicWS(0,c),sc_(sc){}
  uint64_t now()const{return _core_cycle;}
  json compute=json::array();
 protected:
  cycle_type get_inst_compute_cycles(std::unique_ptr<Instruction>&i)override{
    auto n=SystolicWS::get_inst_compute_cycles(i);
    compute.push_back({{"id",i->id},{"start",i->start_cycle},{"duration",n},{"service","native_ws_gemm"}});return n;
  }
  cycle_type get_vector_compute_cycles(std::unique_ptr<Instruction>&i)override{
    if(i->id.rfind("SC_MACRO_",0)==0){
      if(i->opcode!=Opcode::COMP||!sc_)throw std::runtime_error("bad macro");
      compute.push_back({{"id",i->id},{"start",i->start_cycle},{"duration",sc_},{"service","explicit_sc_macro"}});return sc_;
    }
    return SystolicWS::get_vector_compute_cycles(i);
  }
 private:uint64_t sc_;
};
constexpr uint64_t B=0x100000,TS=0x10000;
std::unique_ptr<Instruction> ins(Opcode op,std::string id,addr_type dest,unsigned size,std::vector<addr_type>src){
 auto i=std::make_unique<Instruction>();*i=Instruction{};
 i->opcode=op;i->id=id;i->dest_addr=dest;i->size=size;i->src_addrs=src;i->base_addr=0;
 i->tile_m=i->tile_k=i->tile_n=i->compute_size=8;return i;
}
std::unique_ptr<Tile> tile(unsigned t,bool sc,unsigned stride){
 auto p=std::make_unique<Tile>(Tile{});p->status=Tile::Status::INITIALIZED;p->layer_id=t;p->fused_op_id=t;p->accum=false;p->skip=false;
 p->optype=sc?"sc_macro":"native_ws_gemm";
 std::vector<addr_type>x,w,y;auto b=B+t*TS;
 for(unsigned j=0;j<4;++j){x.push_back(b+j*stride);w.push_back(b+0x1000+j*stride);y.push_back(b+0x8000+j*stride);}
 p->instructions.push_back(ins(Opcode::MOVIN,"X",SPAD_BASE,4,x));
 p->instructions.push_back(ins(Opcode::MOVIN,"W",SPAD_BASE+0x1000,4,w));
 p->instructions.push_back(ins(sc?Opcode::COMP:Opcode::GEMM_PRELOAD,(sc?"SC_MACRO_":"GEMM_")+std::to_string(t),ACCUM_SPAD_BASE,4,{SPAD_BASE,SPAD_BASE+0x1000}));
 p->instructions.push_back(ins(Opcode::MOVOUT,"Y",ACCUM_SPAD_BASE,4,y));return p;
}
struct Flight{MemoryAccess*a;uint64_t due;};
void require(bool p,const char*m){if(!p)throw std::runtime_error(m);}
json run(std::string name,uint64_t sc,unsigned window,unsigned latency,unsigned stride,unsigned tile_limit,bool banks){
 CoreConfig c{};c.core_type=CoreType::SYSTOLIC_WS;c.core_height=c.core_width=8;c.spad_size=c.accum_spad_size=2;c.sram_width=32;c.vector_process_bit=512;
 SimulationConfig cfg{};cfg.num_cores=1;cfg.core_config=&c;cfg.core_print_interval=1000000;cfg.precision=2;cfg.full_precision=4;cfg.dram_req_size=32;cfg.core_freq=cfg.dram_freq=cfg.icnt_freq=1000;cfg.layout="NHWC";
 ProbeCore core(cfg,sc);unsigned issued=0,done=0,active=0,reads=0,writes=0,rejects=0,peak=0;
 std::vector<Flight>f;std::set<unsigned>accepted,returned;std::map<unsigned,unsigned>r_count;std::map<unsigned,uint64_t>r_last,w_first;uint64_t bank_free[4]={};json events=json::array();
 auto issue=[&](){if(issued<4&&active<tile_limit&&core.can_issue()){core.issue(tile(issued,sc!=0,stride));events.push_back({{"kind","tile_issue"},{"tile",issued},{"cycle",core.now()}});++issued;++active;}};
 issue();
 while(issued<4||core.running()||!f.empty()||core.has_memory_request()){
  require(core.now()<100000,"watchdog");
  auto ready=f.end();for(auto it=f.begin();it!=f.end();++it)if(it->due<=core.now()&&(ready==f.end()||it->due<ready->due))ready=it;
  if(ready!=f.end()){
   auto*a=ready->a;unsigned t=unsigned((a->dram_address-B)/TS);require(returned.insert(a->id).second,"duplicate return");
   if(!a->write){++r_count[t];r_last[t]=core.now();}
   events.push_back({{"kind","return"},{"id",a->id},{"address",a->dram_address},{"write",a->write},{"tile",t},{"cycle",core.now()}});
   a->request=false;core.push_memory_response(a);f.erase(ready);
  }
  core.cycle();
  if(core.has_memory_request()){
   if(f.size()>=window)++rejects;
   else{
    auto*a=core.top_memory_request();unsigned t=unsigned((a->dram_address-B)/TS);require(accepted.insert(a->id).second,"duplicate accept");
    if(a->write){++writes;require(r_count[t]==8,"write before reads");if(!w_first.count(t))w_first[t]=core.now();}else ++reads;
    unsigned bank=unsigned((a->dram_address/32)%4);uint64_t due=core.now()+latency;
    if(banks){due=std::max(core.now(),bank_free[bank])+latency;bank_free[bank]=due;}
    events.push_back({{"kind","accept"},{"id",a->id},{"address",a->dram_address},{"write",a->write},{"tile",t},{"cycle",core.now()},{"due",due}});
    core.pop_memory_request();f.push_back({a,due});peak=std::max(peak,unsigned(f.size()));
   }
  }
  for(;;){auto p=core.pop_finished_tile();if(p->status==Tile::Status::EMPTY)break;++done;--active;events.push_back({{"kind","tile_finish"},{"tile",p->layer_id},{"cycle",core.now()}});}
  issue();
 }
 require(done==4&&reads==32&&writes==16&&accepted==returned,"traffic mismatch");require(core.compute.size()==4,"compute count");
 for(const auto&e:core.compute){std::string id=e.at("id");unsigned t=std::stoul(id.substr(id.find_last_of('_')+1));uint64_t start=e.at("start"),duration=e.at("duration");require(start>=r_last[t]&&w_first[t]>=start+duration,"dependency violation");if(sc)require(duration==sc,"latency hook ignored");}
 return {{"name",name},{"cycles",core.now()},{"tiles",4},{"precision_bytes",2},{"read_bytes",reads*32},{"write_bytes",writes*32},{"sc_macro_cycles",sc},{"external_window",window},{"external_latency",latency},{"stride",stride},{"tile_issue_limit",tile_limit},{"address_bank_service",banks},{"rejected_cycles",rejects},{"peak_outstanding",peak},{"compute",core.compute},{"events",events},{"validated",true}};
}
void ws_reference(unsigned n,uint64_t expected){
 CoreConfig c{};c.core_type=CoreType::SYSTOLIC_WS;c.core_height=c.core_width=8;c.spad_size=c.accum_spad_size=192;c.vector_process_bit=512;c.sram_width=32;
 SimulationConfig cfg{};cfg.num_cores=1;cfg.core_config=&c;cfg.precision=4;cfg.full_precision=4;cfg.dram_req_size=32;cfg.core_print_interval=1000000;
 SystolicWS core(0,cfg);auto p=std::make_unique<Tile>(Tile{});p->status=Tile::Status::INITIALIZED;p->layer_id=0;
 for(unsigned j=0;j<n;++j){auto i=std::make_unique<Instruction>();*i=Instruction{};i->opcode=Opcode::GEMM_PRELOAD;i->dest_addr=ACCUM_SPAD_BASE;i->compute_size=8;p->instructions.push_back(std::move(i));}
 core.issue(std::move(p));uint64_t cycle=0;while(core.running()){core.cycle();if(core.has_memory_request()){auto*a=core.top_memory_request();a->request=false;core.pop_memory_request();core.push_memory_response(a);}if(++cycle>1000)throw std::runtime_error("WS watchdog");}require(cycle==expected,"official WS reference mismatch");
}
int main(int argc,char**argv){
 if(argc!=2)return 2;spdlog::set_level(spdlog::level::warn);ws_reference(1,39);ws_reference(2,47);json a=json::array();
 for(auto sc:{uint64_t(0),uint64_t(8),uint64_t(32),uint64_t(64),uint64_t(128)}){
  std::string p=sc?"sc"+std::to_string(sc):"native_ws";
  a.push_back(run(p+"_base",sc,8,3,32,2,false));
  a.push_back(run(p+"_window1",sc,1,11,32,2,false));
  a.push_back(run(p+"_single_tile",sc,8,3,32,1,false));
  a.push_back(run(p+"_bank_interleaved",sc,8,3,32,2,true));
  a.push_back(run(p+"_bank_conflict",sc,8,3,128,2,true));
 }
 for(unsigned i=0;i<a.size();i+=5){require(a[i+1]["cycles"].get<uint64_t>()>=a[i]["cycles"].get<uint64_t>(),"window monotonic");require(a[i+2]["cycles"].get<uint64_t>()>=a[i]["cycles"].get<uint64_t>(),"tile monotonic");require(a[i+4]["cycles"].get<uint64_t>()>=a[i+3]["cycles"].get<uint64_t>(),"bank monotonic");require(a[i+1]["rejected_cycles"].get<unsigned>()>0,"no backpressure");}
 require(a[20]["cycles"].get<uint64_t>()>=a[15]["cycles"].get<uint64_t>()&&a[15]["cycles"].get<uint64_t>()>=a[10]["cycles"].get<uint64_t>(),"SC monotonic");
 std::ofstream out(argv[1]);require(bool(out),"output open");out<<json({{"upstream","8599bee46b311fb267ac34b0677ad7db3d8a8ccd"},{"official_WS_reference_cycles",{39,47}},{"status","completed"},{"cases",a},{"scope","Native WS scheduling; explicit SC busy macro; no numerical payload/whole Qwen/mixed BF16-W8/actual DRAM; external memory is synthetic bounded service"}}).dump(2)<<'\n';
}
