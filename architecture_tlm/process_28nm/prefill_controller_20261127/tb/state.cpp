#include "Vdut.h"
#include "verilated.h"
#include "util.h"
#include <array>
#include <deque>
#include <map>
#include <random>
#include <iostream>
using namespace std;
struct Exp{int slot,beat,k;array<int64_t,32> data;};
int main(int argc,char**argv){try{
 int seed=argc>1?stoi(argv[1]):17;bool stalls=argc>2?stoi(argv[2]):0;int pattern=argc>3?stoi(argv[3]):0;bool same_bank=pattern!=0;
 mt19937 rng(seed);Vdut d;d.rst_n=0;d.clk=0;d.flush=0;d.in_valid=0;d.out_ready=3;d.base_exp=uint8_t(-24);
 for(int t=0;t<3;t++){d.eval();d.clk=1;d.eval();d.clk=0;d.eval();}d.rst_n=1;
 array<int,2> sent{},got{};array<deque<Exp>,2> expect;
 array<map<pair<int,int>,array<int64_t,32>>,2> oracle;
 int cycles=0,conflicts=0,reads=0,writes=0,dual=0;constexpr int N=1024;
 while(got[0]<N||got[1]<N){
  d.in_valid=0;d.out_ready=0;zero(d.in_count);zero(d.in_meta);d.in_slot=0;d.in_beat=0;
  for(int p=0;p<2;p++){
   if(!stalls||rng()%4)d.out_ready|=1<<p;
   if(sent[p]<N){d.in_valid|=1<<p;int q=sent[p],beat=q%4,slot=((q/4)%32)*2+p,k=q/128;
    if(same_bank){beat=0;slot=(q%32)*2+p;k=q/32;}
    if(pattern==2){slot=p;k=q;}
    put(d.in_slot,p*8,8,slot);put(d.in_beat,p*2,2,beat);
    put(d.in_meta,p*96,16,slot);put(d.in_meta,p*96+16,16,k);
    put(d.in_meta,p*96+32,8,-20);put(d.in_meta,p*96+40,8,-19);
    for(int j=0;j<32;j++){int v=(q*17+j*31)%3001-1500;put(d.in_count,p*32*21+j*21,21,v);}
   }
  }
  d.clk=0;d.eval();int takes=0;
  for(int p=0;p<2;p++){
   if((d.bank_conflict>>p)&1)conflicts++;
   if((d.read_fire>>p)&1)reads++;if((d.write_fire>>p)&1)writes++;
   if((d.out_valid&d.out_ready)>>p&1){need(!expect[p].empty(),"orphan state output");auto e=expect[p].front();expect[p].pop_front();
    need(int(bits(d.out_meta,p*96,16))==e.slot&&int(bits(d.out_beat,p*2,2))==e.beat,"state metadata");
    need(!((d.out_error>>p)&1),"state overflow");
    for(int j=0;j<32;j++)need(int64_t(bits(d.out_data,p*2048+j*64,64))==e.data[j],"state sum mismatch q="+to_string(got[p])+" lane="+to_string(j));got[p]++;
   }
   if((d.in_valid&d.in_ready)>>p&1){int q=sent[p],beat=q%4,slot=((q/4)%32)*2+p,k=q/128;
    if(same_bank){beat=0;slot=(q%32)*2+p;k=q/32;}if(pattern==2){slot=p;k=q;}auto&a=oracle[p][{slot,beat}];
    for(int j=0;j<32;j++){if(k==0)a[j]=0;int64_t v=(q*17+j*31)%3001-1500;a[j]+=v*(1ll<<(beat<2?4:5));}
    expect[p].push_back({slot,beat,k,a});sent[p]++;takes++;
   }
  }
  if(takes==2)dual++;d.clk=1;d.eval();d.clk=0;d.eval();cycles++;need(cycles<20000,"state timeout");
 }
 need(reads==(pattern==2?2046:same_bank?1984:1792)&&writes==2048,"state action counts");if(!stalls&&!same_bank)need(cycles==N+3,"II1 pipeline claim failed");
 if(same_bank)need(conflicts>0,"conflict test not exercised");
 cout<<"PASS state seed="<<seed<<" stalls="<<stalls<<" pattern="<<pattern<<" cycles="<<cycles<<" beats=2048 values=65536 reads="<<reads<<" writes="<<writes<<" dual="<<dual<<" conflicts="<<conflicts<<endl;
 return 0;
}catch(exception&e){cerr<<"FAIL "<<e.what()<<endl;return 1;}}
