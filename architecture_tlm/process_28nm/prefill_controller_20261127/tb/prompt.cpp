#include "Vdut.h"
#include "verilated.h"
#include "util.h"
#include <array>
#include <vector>
#include <random>
#include <iostream>
using namespace std;
using Service=array<int,5>;
int main(int argc,char**argv){try{
 int seed=argc>1?stoi(argv[1]):17;mt19937 rng(seed);Vdut d;
 d.rst_n=0;d.clk=0;d.cancel=0;d.cmd_valid=0;d.svc_ready=0;d.svc_done_valid=0;d.done_ready=0;
 auto edge=[&](){d.clk=1;d.eval();d.clk=0;d.eval();};for(int i=0;i<3;i++)edge();d.rst_n=1;
 int cases=0,total=0;
 for(int length:{1,8,31,32,33,128})for(int layers:{2,36}){
  vector<Service> exp;for(int op=0;op<2;op++)for(int l=0;l<(op?layers:1);l++)for(int r=0;r<length;r+=32)exp.push_back({op,l,r,7+r,min(32,length-r)});
  exp.push_back({2,layers-1,length-1,7+length-1,1});
  d.cmd_length=length;d.cmd_past=7;d.cmd_layers=layers;d.cmd_block_rows=32;d.cmd_valid=1;d.eval();need(d.cmd_ready,"prompt ready");edge();d.cmd_valid=0;
  int idx=0,delay=0;bool waiting=false,held=false;Service old{};int t;
  for(t=0;t<20000;t++){
   d.svc_ready=rng()%4!=0;d.svc_done_valid=waiting&&--delay<=0;d.eval();
   if(held){Service cur={d.svc_opcode,d.svc_layer,d.svc_row_base,d.svc_position,d.svc_rows};need(d.svc_valid&&cur==old,"service changed under backpressure");}
   held=d.svc_valid&&!d.svc_ready;if(held)old={d.svc_opcode,d.svc_layer,d.svc_row_base,d.svc_position,d.svc_rows};
   if(d.svc_valid&&d.svc_ready){need(!waiting,"more than one accepted service");Service cur={d.svc_opcode,d.svc_layer,d.svc_row_base,d.svc_position,d.svc_rows};need(idx<int(exp.size())&&cur==exp[idx],"sequence mismatch");idx++;waiting=true;delay=1+rng()%7;}
   if(d.svc_done_valid&&d.svc_done_ready)waiting=false;
   if(d.done_valid){need(idx==int(exp.size())&&!waiting,"incomplete prompt");need(d.decode_position==length+7,"decode transition position");d.done_ready=1;edge();d.done_ready=0;break;}edge();
  }
  need(t<20000,"prompt timeout");cases++;total+=idx;
 }
 // Cancel while a service is in flight; completion must be drained, not lost.
 d.cmd_length=33;d.cmd_layers=2;d.cmd_valid=1;d.svc_ready=1;d.svc_done_valid=0;d.eval();need(d.cmd_ready,"cancel launch");edge();d.cmd_valid=0;edge();
 d.cancel=1;edge();d.cancel=0;d.eval();need(!d.cmd_ready&&d.svc_done_ready,"cancel drain");
 d.svc_done_valid=1;edge();d.svc_done_valid=0;d.eval();need(d.cmd_ready&&!d.done_valid,"cancel recovery");
 cout<<"PASS prompt seed="<<seed<<" cases="<<cases+1<<" accepted_services="<<total<<endl;return 0;
}catch(exception&e){cerr<<"FAIL "<<e.what()<<endl;return 1;}}
