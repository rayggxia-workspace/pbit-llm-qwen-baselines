#include "Vdut.h"
#include "verilated.h"
#include "util.h"
#include <array>
#include <deque>
#include <map>
#include <random>
#include <iostream>
#include <tuple>
#include <algorithm>
using namespace std;
constexpr int NC=6;
int weight(int m,int g,int k,int o,int i){int mag=(i*13+o*7+g*19+k*11+m*3)%128;return (i+o*3+k+g)%5<2?-mag:mag;}
int ew(int m,int g,int k,int o){return -5+(g+k+o/64+m)%3;}
struct Packet{int id,g,k,packet,due;};
struct Input{bool live=false;int row,g,k,due;};
struct Stat{long long cycles=0,tiles=0,samples=0,rows=0,bytes=0,commits=0,reads=0,writes=0,
 conflict=0,input_wait=0,result_full=0,overlap=0,dma_peak=0,result_peak=0,dual_commit=0,
 row_gap_min=1000000,row_gap_max=0,load_min=1000000,load_max=0;};
struct Sim{
 Vdut d;mt19937 rng;bool stalls;int mode,lg,m,ng,nk,cores,seed,cycle=0,tag=0;bool cancelled=false,long_latency=false,long_output_stall=false;
 array<deque<Packet>,4> packets;array<Input,NC> inputs;
 array<array<int64_t,128>,NC> local;
 array<array<int,3>,NC> local_id{};array<bool,NC> live{};
 array<int,NC> dispatch_cycle{},previous_row_cycle{};
 map<pair<int,int>,array<int64_t,128>> oracle;
 map<tuple<int,int,int>,bool> captured,committed;
 Stat st;
 Sim(int sd,bool stall):rng(sd),stalls(stall),seed(sd){
  d.rst_n=0;d.clk=0;d.cancel=0;d.cmd_valid=0;d.done_ready=0;d.seed_valid=0;
  d.row_valid=0;d.rsp_valid=0;d.rd_ready=15;d.commit_ready=3;d.sample_enable=63;
  for(int t=0;t<3;t++)edge();d.rst_n=1;
  for(int c=0;c<NC;c++)for(int j=0;j<4;j++)put(d.seeds,c*128+j*32,32,sd+c*103+j*7919);
  d.seed_valid=1;edge();d.seed_valid=0;
 }
 void edge(){d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}
 bool yes(int n=75){return !stalls||int(rng()%100)<n;}
 void step(){
  cycle++;st.cycles++;d.clk=0;d.row_valid=0;d.rsp_valid=0;d.rsp_error=0;d.rd_ready=0;
  d.sample_enable=0;d.commit_ready=0;zero(d.rsp_data);zero(d.row_x);zero(d.row_gu);
  zero(d.row_e0);zero(d.row_e1);zero(d.row_scale);
  for(int p=0;p<2;p++)if(yes())d.commit_ready|=1<<p;
  if(long_output_stall&&st.cycles<1000)d.commit_ready=0;
  array<int,4> chosen;chosen.fill(-1);
  for(int b=0;b<4;b++){
   if(yes(85))d.rd_ready|=1<<b;
   for(int j=int(packets[b].size())-1;j>=0;j--)if(packets[b][j].due<=cycle&&yes(90)){chosen[b]=j;break;}
   if(chosen[b]>=0){auto&p=packets[b][chosen[b]];d.rsp_valid|=1<<b;put(d.rsp_id,b*8,8,p.id);
    for(int by=0;by<64;by++){int off=p.packet*64+by,bank=off/16%16,row=off/256,l=off%16;
     int o=bank*8+l%8,i=row*2+l/8,w=weight(mode,p.g,p.k,o,i);
     put(d.rsp_data,b*512+by*8,8,(w<0?128:0)|abs(w));}
   }
  }
  d.eval();
  for(int c=0;c<NC;c++){
   if(yes(85))d.sample_enable|=1<<c;
   if(!inputs[c].live&&((d.row_req>>c)&1)){
    inputs[c]={true,int(bits(d.row_index,c*6,6)),int(bits(d.row_group,c*16,16)),int(bits(d.row_k,c*16,16)),cycle+(stalls?int(rng()%8):0)};
   }
   auto&in=inputs[c];
   if(in.live&&in.due<=cycle){
    d.row_valid|=1<<c;
    put(d.row_e0,c*8,8,-4+ew(mode,in.g,in.k,0)-lg);
    put(d.row_e1,c*8,8,-4+ew(mode,in.g,in.k,64)-lg);
    put(d.row_scale,c*7,7,0);
    for(int i=0;i<64;i++){
     int q=(i*29+in.k*43+in.row*11+17)%257;
     int v=(q==256?512:q)|((i+in.row)%3==0?256:0);put(d.row_x,c*640+i*10,10,v);
    }
    // Synthetic paired GU codes are fixed point inputs to the real existing
    // threshold/LUT/three-AND frontend. No floating-point nonlinear oracle.
    for(int j=0;j<32;j++){
     uint32_t code=uint32_t(0x28103080u+j*0x01010101u+in.row*0x00020301u+in.k*0x00100103u);
     put(d.row_gu,c*1024+j*32,32,code);
    }
   }
  }
  d.eval();
  if(d.dispatch_fire){st.tiles++;dispatch_cycle[d.assigned_core]=cycle;need(d.assigned_group<ng&&d.assigned_k<nk,"dispatch shape");}
  int simultaneous=0;
  for(int c=0;c<NC;c++){
   if((d.row_req>>c)&1&& !((d.row_valid>>c)&1))st.input_wait++;
   int used=bits(d.result_used,c*2,2);st.result_peak=max(st.result_peak,1ll*used);if(used==2)st.result_full++;
   if((d.row_valid&d.row_ready)>>c&1){auto in=inputs[c];need(!live[c],"overwrite active row");
    if(in.row==0){st.load_min=min(st.load_min,1ll*(cycle-dispatch_cycle[c]));st.load_max=max(st.load_max,1ll*(cycle-dispatch_cycle[c]));}
    else{st.row_gap_min=min(st.row_gap_min,1ll*(cycle-previous_row_cycle[c]));st.row_gap_max=max(st.row_gap_max,1ll*(cycle-previous_row_cycle[c]));}previous_row_cycle[c]=cycle;
    local[c].fill(0);local_id[c]={in.g,in.k,in.row};live[c]=true;inputs[c].live=false;st.rows++;
   }
   if((d.sample_fire>>c)&1){need(live[c],"sample identity");st.samples++;simultaneous++;
    auto id=local_id[c];uint64_t ev=bits(d.events,c*64,64),sg=bits(d.signs,c*64,64);
    for(int o=0;o<128;o++)for(int i=0;i<64;i++)if(ev>>i&1)local[c][o]+=(sg>>i&1?-1:1)*weight(mode,id[0],id[1],o,i);
   }
   if((d.capture>>c)&1){need(live[c],"capture active row");auto id=local_id[c];int g=id[0],k=id[1],r=id[2];
    need(int(bits(d.capture_row,c*6,6))==r&&int(bits(d.capture_group,c*16,16))==g&&int(bits(d.capture_k,c*16,16))==k,"capture tag");
    need(!captured[{g,k,r}],"duplicate capture");captured[{g,k,r}]=true;auto&a=oracle[{g,r}];
    for(int o=0;o<128;o++){int delta=-4+ew(mode,g,k,o)-lg+24;need(delta>=0&&delta<=31,"oracle exponent");a[o]+=local[c][o]*(1ll<<delta);}
    live[c]=false;
    need(bool(d.weight_release>>c&1)==(r+1==m),"resident weight released too early/late");
   }
  }
  if(simultaneous>1)st.overlap++;
  int cc=0;
  for(int p=0;p<2;p++){
   if(d.bank_conflict>>p&1)st.conflict++;if(d.state_read>>p&1)st.reads++;if(d.state_write>>p&1)st.writes++;
   if((d.commit_valid&d.commit_ready)>>p&1){int g=bits(d.commit_meta,p*96,16),k=bits(d.commit_meta,p*96+16,16),r=bits(d.commit_meta,p*96+49,16),b=bits(d.commit_beat,p*2,2);
    need(captured[{g,k,r}],"commit before row capture");need(r%2==p,"row/worker parity");
    need(int(bits(d.commit_meta,p*96+65,16))==tag,"task tag");
    for(int j=0;j<32;j++){int o=b*32+j;int64_t got=int64_t(bits(d.commit_data,p*2048+j*64,64)),want=oracle[{g,r}][o];
     need(got==want,"state mismatch g="+to_string(g)+" k="+to_string(k)+" row="+to_string(r)+" o="+to_string(o)+" got="+to_string(got)+" want="+to_string(want));}
    if(b==3){need(!committed[{g,k,r}],"duplicate row commit");committed[{g,k,r}]=true;}st.commits++;cc++;
   }
  }
  if(cc==2)st.dual_commit++;
  for(int b=0;b<4;b++){
   if((d.rd_valid&d.rd_ready)>>b&1){uint64_t a=bits(d.rd_addr,b*64,64);need(a>=0x100000,"DRAM base");uint64_t rel=a-0x100000;int tile=rel/8192;
    need(tile/nk<ng,"DRAM tile bounds");packets[b].push_back({int(bits(d.rd_id,b*8,8)),tile/nk,tile%nk,int(rel%8192/64),cycle+(long_latency?500:stalls?int(rng()%27)+2:1)});st.bytes+=64;}
   if((d.rsp_valid&d.rsp_ready)>>b&1){need(chosen[b]>=0,"return choice");packets[b].erase(packets[b].begin()+chosen[b]);}
  }
  st.dma_peak=max(st.dma_peak,1ll*d.dma_used);need(d.dma_used<=256,"DMA capacity");edge();
 }
 void queue_test(){
  mode=0;lg=4;m=32;ng=8;nk=2;cores=6;tag=1;
  d.cmd_mode=0;d.cmd_log2=4;d.cmd_rows=32;d.cmd_groups=8;d.cmd_kblocks=2;
  d.cmd_base=0x100000;d.cmd_base_exp=uint8_t(-24);d.cmd_tag=tag;d.cmd_core_mask=63;
  d.cmd_valid=1;d.rd_ready=0;d.rsp_valid=0;d.row_valid=0;int accepted=0;
  for(int i=0;i<30;i++){d.eval();if(d.cmd_ready)accepted++;edge();}
  need(accepted==17&&d.queue_used==16&&!d.cmd_ready,"FIFO capacity/normal wait");
  d.cmd_valid=0;d.cancel=1;edge();d.cancel=0;
  for(int i=0;i<2000;i++){if(d.done_valid)break;step();}
  need(d.done_valid&&d.done_error==1&&d.queue_used==0,"queued cancel drain");
  for(auto&q:packets)need(q.empty(),"queued cancel external drain");
  d.done_ready=1;step();d.done_ready=0;
  cout<<"{\"name\":\"queue_full_cancel\",\"seed\":"<<seed<<",\"accepted\":17,\"queued_peak\":16,\"status\":\"PASS\"}"<<endl;
 }
 Stat run(int md,int log2,int rows,int groups,int ks,int enabled,int cancel_at=0){
  mode=md;lg=log2;m=rows;ng=groups;nk=ks;cores=enabled;tag++;st=Stat{};oracle.clear();captured.clear();committed.clear();live.fill(false);for(auto&in:inputs)in.live=false;
  d.cmd_mode=mode;d.cmd_log2=lg;d.cmd_rows=m;d.cmd_groups=ng;d.cmd_kblocks=nk;
  d.cmd_base=0x100000;d.cmd_base_exp=uint8_t(-24);d.cmd_tag=tag;d.cmd_core_mask=(1<<cores)-1;
  d.cmd_valid=1;d.done_ready=0;d.cancel=0;d.eval();need(d.cmd_ready,"matrix command ready");step();d.cmd_valid=0;
  bool cancelled=false;
  for(int t=0;t<500000;t++){
   d.cancel=cancel_at&&t==cancel_at;if(d.cancel)cancelled=true;
   if(d.done_valid){need(d.done_error==(cancelled?1:0),"matrix done error "+to_string(d.done_error));
    if(!cancelled){need(st.tiles==ng*nk,"tile coverage");need(st.rows==ng*nk*m,"row coverage");need(st.samples==(1ll<<lg)*ng*nk*m,"sample coverage");
     need(st.bytes==8192ll*ng*nk,"weight reuse byte accounting");need(st.commits==4ll*ng*nk*m,"commit coverage");need(committed.size()==size_t(ng*nk*m),"state row coverage");}
    for(auto&q:packets)need(q.empty(),"external reads not drained");d.cancel=0;d.done_ready=1;step();d.done_ready=0;return st;
   }
   step();
  }
  throw runtime_error("matrix timeout groups="+to_string(ng)+" rows="+to_string(m)+" tiles="+to_string(st.tiles)+" commit="+to_string(st.commits)+" dma="+to_string(d.dma_used));
 }
};
void report(const Stat&s,int seed,bool stalls,int mode,int lg,int rows,int groups,int k,int cores,string name){
 cout<<"{\"name\":\""<<name<<"\",\"seed\":"<<seed<<",\"stalls\":"<<stalls<<",\"mode\":"<<mode<<",\"log2\":"<<lg<<",\"m\":"<<rows<<",\"groups\":"<<groups<<",\"kblocks\":"<<k<<",\"cores\":"<<cores;
 #define FIELD(n) cout<<",\"" #n "\":"<<s.n;
 FIELD(cycles) FIELD(tiles) FIELD(samples) FIELD(rows) FIELD(bytes) FIELD(commits) FIELD(reads) FIELD(writes) FIELD(conflict) FIELD(input_wait) FIELD(result_full) FIELD(overlap) FIELD(dma_peak) FIELD(result_peak) FIELD(dual_commit)
 FIELD(row_gap_min) FIELD(row_gap_max) FIELD(load_min) FIELD(load_max)
 #undef FIELD
 cout<<",\"status\":\"PASS\"}"<<endl;
}
int main(int argc,char**argv){try{
 int seed=argc>1?stoi(argv[1]):17;bool stalls=argc>2?stoi(argv[2]):0;int suite=argc>3?stoi(argv[3]):0;Sim s(seed,stalls);
 if(suite==0){s.queue_test();
  for(int mode=0;mode<2;mode++)for(int m:{1,8,32}){int lg=mode?5:4;auto r=s.run(mode,lg,m,8,2,6);report(r,seed,stalls,mode,lg,m,8,2,6,"reuse");}
  for(int mode=0;mode<2;mode++)for(int lg:{3,6,7}){auto r=s.run(mode,lg,3,2,3,6);report(r,seed,stalls,mode,lg,3,2,3,6,"budget_tail");}
  for(int cores:{1,4,5,6})for(int mode=0;mode<2;mode++){int lg=mode?5:4;auto r=s.run(mode,lg,32,8,2,cores);report(r,seed,stalls,mode,lg,32,8,2,cores,"cores");}
  auto a=s.run(0,4,8,6,2,6,800);report(a,seed,stalls,0,4,8,6,2,6,"cancel_drain");
  auto b=s.run(1,5,3,2,3,6);report(b,seed,stalls,1,5,3,2,3,6,"after_cancel");
  s.long_output_stall=true;auto bp=s.run(0,4,8,6,1,6);report(bp,seed,stalls,0,4,8,6,1,6,"result_backpressure");need(bp.result_peak==2&&bp.result_full>0,"double result slots/backpressure not exercised");s.long_output_stall=false;
  s.long_latency=true;auto c=s.run(0,4,3,6,1,6);report(c,seed,stalls,0,4,3,6,1,6,"DMA_credit_full");need(c.dma_peak==256,"DMA credit saturation not exercised");
 }else if(suite==1){
  for(int mode=0;mode<2;mode++){int k=mode?152:40,lg=mode?5:4;auto r=s.run(mode,lg,1,2,k,6);report(r,seed,stalls,mode,lg,1,2,k,6,"long_K");}
 }else{
  for(int cores:{4,5,6})for(int mode=0;mode<2;mode++){int lg=mode?5:4;auto r=s.run(mode,lg,32,24,2,cores);report(r,seed,stalls,mode,lg,32,24,2,cores,"steady_groups");}
 }
 return 0;
}catch(exception&e){cerr<<"FAIL "<<e.what()<<endl;return 1;}}
