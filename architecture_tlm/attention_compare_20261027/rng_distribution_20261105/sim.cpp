#include <cstdint>
#include <vector>
#include <fstream>
#include <iostream>
#include <random>
#include <string>
#include <stdexcept>
#include <algorithm>
using namespace std;
// Functional transaction model, not cycle/PPA simulation. Native uint64 limbs
// preserve the original 93+84-bit Bivium and 160-bit word advancement.
struct Biv {
 uint64_t al=0,ah=0,bl=0,bh=0;
 unsigned next(){unsigned w=0;
  for(int j=0;j<160;j++){
   unsigned t1=((ah>>1)^(ah>>28))&1, t2=((bh>>4)^(bh>>19))&1;
   if(j<7)w|=(t1^t2)<<j;
   unsigned fa=t2^(((bh>>17)&(bh>>18))&1)^((ah>>4)&1);
   unsigned fb=t1^(((ah>>26)&(ah>>27))&1)^((bh>>13)&1);
   ah=((ah<<1)|(al>>63))&((1ULL<<29)-1);al=(al<<1)|fa;
   bh=((bh<<1)|(bl>>63))&((1ULL<<20)-1);bl=(bl<<1)|fb;
  }return w;
 }
};
uint64_t tab[4][256][9];
void gf(uint32_t &state,unsigned char *out){uint64_t v[9]={};
 for(int b=0;b<4;b++)for(int j=0;j<9;j++)v[j]^=tab[b][(state>>(b*8))&255][j];
 for(int j=0;j<64;j++)out[j]=(v[j/8]>>((j%8)*8))&255;
 state=uint32_t(v[8]);
}
uint64_t mix(uint64_t x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}
struct Source {
 mt19937_64 cand,fair;uint32_t a,b,lf;Biv bv;
 Source(uint64_t seed):cand(mix(seed)),fair(mix(seed^0xabcdef123456ULL)){
  a=uint32_t(mix(seed^1));b=uint32_t(mix(seed^2));lf=uint32_t(mix(seed^3));
  if(a==0)a=1;if(b==0)b=1;if(lf==0)lf=1;
  bv.al=mix(seed^4);bv.ah=mix(seed^5)&((1ULL<<29)-1);bv.bl=mix(seed^6);bv.bh=mix(seed^7)&((1ULL<<20)-1);
  for(int i=0;i<5;i++)bv.next();
 }
 void words(int mode,unsigned char *v){
  if(mode==1||mode==3){gf(a,v);gf(b,v+64);}
  else if(mode==4||mode==6){fill(v,v+128,lf&255);for(int j=0;j<(mode==6?8:1);j++)lf=(lf>>1)^(uint32_t(0-(lf&1))&0x80200003U);}
  else if(mode==5){unsigned x=cand()&255;fill(v,v+128,x);}
  else for(int k=0;k<16;k++){uint64_t w=cand();for(int j=0;j<8;j++)v[k*8+j]=(w>>(j*8))&255;}
 }
 unsigned rank(int n,int mode){unsigned mask=1;while(mask<unsigned(n-1))mask=(mask<<1)|1;
  for(int k=0;k<64;k++){unsigned x=((mode==2||mode==3)?bv.next():unsigned(fair()))&mask;if(x<unsigned(n))return x;}
  throw runtime_error("rank cap64 reached; no biased fallback");
 }
};
struct Row{string id;unsigned char p[128];};
int advance(Source &src,int mode,const Row&r,int winner,int &ct){
 unsigned char v[128];src.words(mode,v);int active[128];ct=0;
 for(int i=0;i<128;i++)if(v[i]<r.p[i])active[ct++]=i;
 if(v[winner]<r.p[winner]||ct==0)return winner;
 return ct==1?active[0]:active[src.rank(ct,mode)];
}
void dump(ofstream&o,const vector<int>&h){for(int x:h){uint32_t v=x;o.write(reinterpret_cast<char*>(&v),4);}}
int main(int argc,char**argv){
 if(argc<3)return 2;string dir=argv[1],action=argv[2];
 ifstream tf(dir+"/gf_tables.bin",ios::binary);tf.read(reinterpret_cast<char*>(tab),sizeof(tab));if(!tf)throw runtime_error("table");
 if(action=="verify"){
  ifstream in(dir+"/verify.txt");ofstream out(dir+"/verify_out.txt");string type;
  while(in>>type){if(type=="G"){uint32_t s;in>>s;unsigned char w[64];gf(s,w);out<<"G "<<s;for(int i=0;i<64;i++)out<<' '<<unsigned(w[i]);}
   else if(type=="B"){Biv b;in>>b.al>>b.ah>>b.bl>>b.bh;unsigned w=b.next();out<<"B "<<w<<' '<<b.al<<' '<<b.ah<<' '<<b.bl<<' '<<b.bh;}
   else if(type=="Q"){Source s(0);in>>s.a>>s.b>>s.bv.al>>s.bv.ah>>s.bv.bl>>s.bv.bh;int nq;in>>nq;
    out<<"Q";for(int q=0;q<nq;q++){Row r;for(int j=0;j<128;j++){int x;in>>x;r.p[j]=x;}int win=0,ct;for(int t=0;t<64;t++){win=advance(s,3,r,win,ct);out<<' '<<win;}}
   }else throw runtime_error("verify type");out<<'\n';
  }return 0;
 }
 ifstream in(dir+"/rows.txt");int nr;in>>nr;vector<Row> rows(nr);for(auto&r:rows){in>>r.id;for(int i=0;i<128;i++){int x;in>>x;r.p[i]=x;}}
 int reps=action=="short"?128:8;int steps=action=="short"?256:32768;int burn=action=="short"?0:4096;
 ofstream hist(dir+"/"+action+"_hist.bin",ios::binary),seq(dir+"/"+action+"_seq.bin",ios::binary),meta(dir+"/"+action+"_meta.tsv");
 meta<<"mode\trow\trep\tsteps\tunique\tswitches\tempty\tactive_sum\tmax_run\n";
 for(int mode=0;mode<7;mode++){
  for(int ri=0;ri<nr;ri++){
   // All synthetic and deterministic first two heads per captured layer.
   if(action!="short" && !(ri<6||ri==6||ri==7||ri==38||ri==39||ri==70||ri==71))continue;
   for(int rep=0;rep<reps;rep++){
    Source s(mix(uint64_t(rep)+0x198050000ULL+uint64_t(ri)*0x100000ULL));int winner=0,ct=0,sw=0,empty=0,ac=0,run=0,maxrun=0;vector<int> h(128,0);
    for(int t=0;t<burn;t++)winner=advance(s,mode,rows[ri],winner,ct);
    for(int t=1;t<=steps;t++){
     int next=advance(s,mode,rows[ri],winner,ct);if(next!=winner){sw++;run=1;}else run++;
     winner=next;maxrun=max(maxrun,run);empty+=ct==0;ac+=ct;h[winner]++;
     if(action!="short"){unsigned char w=winner;seq.write(reinterpret_cast<char*>(&w),1);}
     if(action=="short"&&(t==16||t==32||t==64||t==128||t==256)){
      dump(hist,h);meta<<mode<<'\t'<<ri<<'\t'<<rep<<'\t'<<t<<'\t'<<count_if(h.begin(),h.end(),[](int x){return x>0;})<<'\t'<<sw<<'\t'<<empty<<'\t'<<ac<<'\t'<<maxrun<<'\n';
     }
    }
    if(action!="short"){dump(hist,h);meta<<mode<<'\t'<<ri<<'\t'<<rep<<'\t'<<steps<<'\t'<<count_if(h.begin(),h.end(),[](int x){return x>0;})<<'\t'<<sw<<'\t'<<empty<<'\t'<<ac<<'\t'<<maxrun<<'\n';}
   }
  }cerr<<action<<" mode "<<mode<<" completed\n";
 }
 return 0;
}
