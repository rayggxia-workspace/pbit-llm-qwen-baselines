#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>
#include <type_traits>
template<class T> uint64_t bits(const T&a,int off,int n){uint64_t r=0;for(int i=0;i<n;i++){bool b;if constexpr(std::is_integral_v<T>)b=(a>>(off+i))&1;else b=(a[(off+i)/32]>>((off+i)%32))&1u;if(b)r|=1ull<<i;}return r;}
template<class T> void put(T&a,int off,int n,uint64_t v){for(int i=0;i<n;i++){if constexpr(std::is_integral_v<T>){T m=T(1)<<(off+i);a=(a&~m)|(((v>>i)&1)?m:0);}else{auto&w=a[(off+i)/32];uint32_t m=1u<<((off+i)%32);w=(w&~m)|(((v>>i)&1)?m:0);}}}
template<class T>void zero(T&a){if constexpr(std::is_integral_v<T>)a=0;else for(unsigned i=0;i<a.size();i++)a[i]=0;}
inline void need(bool b,const std::string&s){if(!b)throw std::runtime_error(s);}
