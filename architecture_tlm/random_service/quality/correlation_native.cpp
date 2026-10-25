// Bit-exact bulk generator and packed-bit Pearson diagnostics. No RNG library fallback.
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
using U=uint64_t;
template<class T> std::vector<T> read(const std::string& p,size_t n){
 std::ifstream f(p,std::ios::binary);std::vector<T> v(n);
 if(!f.read(reinterpret_cast<char*>(v.data()),n*sizeof(T)))throw std::runtime_error("short input "+p);return v;
}
template<class T> void write(const std::string& p,const std::vector<T>& v){
 std::ofstream f(p,std::ios::binary);f.write(reinterpret_cast<const char*>(v.data()),v.size()*sizeof(T));
 if(!f)throw std::runtime_error("write failed "+p);
}
struct Core{
 uint32_t s;U al,bl;uint32_t ah,bh;
 Core(const uint32_t* w):s(w[0]),al(U(w[0])|(U(w[1])<<32)),bl(U(w[2]>>29)|(U(w[3])<<3)|(U(w[4])<<35)),ah(w[2]&0x1fffffff),bh(((w[4]>>29)|(w[5]<<3))&0xfffff){}
 void state(int kind,uint32_t* w){
  std::fill(w,w+6,0);if(kind!=2){w[0]=s;return;}
  w[0]=uint32_t(al);w[1]=uint32_t(al>>32);w[2]=ah|(uint32_t(bl&7)<<29);
  w[3]=uint32_t(bl>>3);w[4]=uint32_t(bl>>35)|(uint32_t(bh&7)<<29);w[5]=bh>>3;
 }
 void frame(int kind,const std::vector<uint32_t>& map,uint8_t* out){
  if(kind!=2){
   if(kind==0)out[0]=s&255;
   else for(int i=0;i<64;i++){unsigned v=0;for(int b=0;b<8;b++)v|=(__builtin_popcount(s&map[i*8+b])&1)<<b;out[i]=v;}
   for(int j=0;j<16;j++)s=(s>>1)^((s&1)?0x80200003:0);return;
  }
  std::fill(out,out+20,0);
  for(int i=0;i<160;i++){
   unsigned t1=((ah>>1)^(ah>>28))&1,t2=((bh>>4)^(bh>>19))&1;
   out[i/8]|=(t1^t2)<<(i%8);
   unsigned fa=t2^(((bh>>17)&(bh>>18))&1)^((ah>>4)&1);
   unsigned fb=t1^(((ah>>26)&(ah>>27))&1)^((bh>>13)&1);
   ah=((ah<<1)|(al>>63))&0x1fffffff;al=(al<<1)|fa;
   bh=((bh<<1)|(bl>>63))&0xfffff;bl=(bl<<1)|fb;
  }
 }
};
double rho(U n,U a,U b,U ab){
 double d=double(a)*double(n-a)*double(b)*double(n-b);
 return d>0?(double(n)*double(ab)-double(a)*double(b))/std::sqrt(d):NAN;
}
int main(int argc,char** argv){try{
 std::string mode=argv[1];
 if(mode=="gen"){
  int kind=std::stoi(argv[2]),n=std::stoi(argv[3]),lanes=kind==0?1:kind==1?64:20;
  auto seeds=read<uint32_t>(argv[4],12),map=read<uint32_t>(argv[5],512);
  std::vector<uint8_t> out(size_t(n)*2*lanes);std::vector<uint32_t> checkpoints;
  for(int p=0;p<2;p++){
   Core c(seeds.data()+6*p);uint8_t tmp[64];if(kind==2)for(int k=0;k<5;k++)c.frame(kind,map,tmp);
   for(int t=0;t<n;t++){
    if(t==n/2||t==n-256){uint32_t w[6];c.state(kind,w);checkpoints.insert(checkpoints.end(),w,w+6);}
    c.frame(kind,map,out.data()+size_t(t)*2*lanes+p*lanes);
   }
   uint32_t w[6];c.state(kind,w);checkpoints.insert(checkpoints.end(),w,w+6);
  }
  write(argv[6],out);write(std::string(argv[6])+".states",checkpoints);
 }else if(mode=="corr"){
  int n=std::stoi(argv[3]),l=std::stoi(argv[4]),feature=std::stoi(argv[5]);
  auto x=read<uint8_t>(argv[2],size_t(n)*l);
  auto lags=read<uint32_t>(argv[6],std::stoul(argv[7]));
  auto tlags=read<uint32_t>(argv[8],std::stoul(argv[9]));
  size_t nw=(n+63)/64;std::vector<std::vector<U>> b(l,std::vector<U>(nw+1,0));
  for(int t=0;t<n;t++)for(int i=0;i<l;i++){
   bool bit=feature>0?x[size_t(t)*l+i]<feature:(x[size_t(t)*l+i]>>(-feature-1))&1;
   if(bit)b[i][t/64]|=U(1)<<(t%64);
  }
  auto calculate=[&](unsigned lag,bool matrix){
   if(lag>=unsigned(n))throw std::runtime_error("lag too long");
   unsigned m=n-lag,words=(m+63)/64,off=lag/64,shift=lag%64;
   U mask=m%64?(U(1)<<(m%64))-1:~U(0);
   std::vector<std::vector<U>> y(l,std::vector<U>(words));std::vector<U> sa(l),sb(l);
   for(int i=0;i<l;i++)for(unsigned k=0;k<words;k++){
    U v=b[i][k+off]>>shift;if(shift)v|=b[i][k+off+1]<<(64-shift);
    U a=b[i][k];if(k+1==words){a&=mask;v&=mask;}
    y[i][k]=v;sa[i]+=__builtin_popcountll(a);sb[i]+=__builtin_popcountll(v);
   }
   std::vector<double> r(matrix?size_t(l)*l:l);
   for(int i=0;i<l;i++)for(int j=matrix?0:i;j<(matrix?l:i+1);j++){
    if(matrix&&lag==0&&j<i){r[size_t(i)*l+j]=r[size_t(j)*l+i];continue;}
    U ab=0;for(unsigned k=0;k<words;k++)ab+=__builtin_popcountll(b[i][k]&y[j][k]);
    r[matrix?size_t(i)*l+j:i]=rho(m,sa[i],sb[j],ab);
   }return r;
  };
  std::vector<double> spatial,temporal;
  for(auto lag:lags){auto r=calculate(lag,true);spatial.insert(spatial.end(),r.begin(),r.end());}
  for(auto lag:tlags){auto r=calculate(lag,false);temporal.insert(temporal.end(),r.begin(),r.end());}
  write(std::string(argv[10])+".spatial",spatial);write(std::string(argv[10])+".temporal",temporal);
 }else throw std::runtime_error("unknown mode");
 return 0;
}catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}}
