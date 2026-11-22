// r54: independent bounded enumeration of repeated positive cube differences.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <numeric>
#include <vector>
using u64=std::uint64_t; using u128=__uint128_t;
struct R{u64 d; std::uint32_t x,y;};
static bool cmpR(const R&a,const R&b){
    return a.d<b.d || (a.d==b.d && (a.x<b.x || (a.x==b.x && a.y<b.y)));
}
static inline u64 c3(u64 x){return (u64)((u128)x*x*x);}
static u64 gcd6(const R&a,const R&b,const R&c){
    u64 g=0;
    for(u64 z:{(u64)a.x,(u64)a.y,(u64)b.x,(u64)b.y,(u64)c.x,(u64)c.y})
        g=std::gcd(g,z);
    return g;
}
int main(int argc,char**argv){
    const int N=argc>1?std::atoi(argv[1]):10000;
    if(N<2) return 2;
    const size_t total=(size_t)N*(N-1)/2;
    std::cerr<<"N="<<N<<" pairs="<<total<<"\n";
    std::vector<R> v; v.reserve(total);
    for(std::uint32_t y=2;y<=(std::uint32_t)N;y++){
        const u64 Y=c3(y);
        for(std::uint32_t x=1;x<y;x++) v.push_back({Y-c3(x),x,y});
    }
    std::sort(v.begin(),v.end(),cmpR);
    u64 groups3=0,triples=0; size_t maxm=0;
    for(size_t i=0;i<v.size();){
        size_t j=i+1; while(j<v.size() && v[j].d==v[i].d) ++j;
        const size_t m=j-i; maxm=std::max(maxm,m);
        if(m>=3){
            ++groups3;
            for(size_t a=i;a<j;a++) for(size_t b=a+1;b<j;b++) for(size_t c=b+1;c<j;c++){
                ++triples;
                std::cout<<"TRI D="<<v[i].d
                         <<" lower="<<v[a].x<<','<<v[b].x<<','<<v[c].x
                         <<" upper="<<v[a].y<<','<<v[b].y<<','<<v[c].y
                         <<" g="<<gcd6(v[a],v[b],v[c])<<"\n";
            }
        }
        i=j;
    }
    std::cout<<"STAT N="<<N<<" pairs="<<v.size()<<" groups3="<<groups3
             <<" triples="<<triples<<" maxm="<<maxm<<"\n";
}
