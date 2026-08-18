// r17: proportional signatures using either lower or upper endpoints.
// Dormant until r16 is read; exact replay constructs a full 3x3 candidate.
#define main d1_old_main
#include "d1.cpp"
#undef main

#include <gmpxx.h>
#include <array>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

using Z17 = mpz_class;

struct G17 { u64 D; std::vector<std::pair<u64,u64>> rp; };
struct O17 {
    size_t gi;
    int sign; // alt^3-base^3 = sign*D before scaling
    std::array<u64,3> base;
    std::array<u64,3> alt;
    u64 g;
};
struct H17 {
    size_t operator()(const std::array<u64,3>& a) const noexcept {
        auto mix=[](u64 x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);};
        return (size_t)(mix(a[0])^(mix(a[1])<<1)^(mix(a[2])>>1));
    }
};

static Z17 z17(u64 x){ return Z17(std::to_string(x)); }
static Z17 c17(const Z17& x){ return x*x*x; }
static std::vector<u64> read17(const std::string& path){
    std::ifstream f(path); if(!f) throw std::runtime_error("open input");
    std::vector<u64> z; std::string line;
    while(std::getline(f,line)){
        if(line.empty()||line[0]=='#') continue;
        std::istringstream is(line); long long n; unsigned long long d;
        if(is>>n>>d) z.push_back((u64)d);
    }
    return z;
}

static bool replay17(const G17& A,const O17& oa,const G17& B,const O17& ob,std::ostream& out){
    const u64 gg=std::gcd(oa.g,ob.g), sa=ob.g/gg, sb=oa.g/gg;
    std::array<Z17,3> base, aa, bb;
    for(int i=0;i<3;i++){
        base[i]=z17(sa)*z17(oa.base[i]);
        if(base[i]!=z17(sb)*z17(ob.base[i])) throw std::runtime_error("base alignment failed");
        aa[i]=z17(sa)*z17(oa.alt[i]);
        bb[i]=z17(sb)*z17(ob.alt[i]);
    }
    Z17 dA=z17(sa)*z17(sa)*z17(sa)*z17(A.D);
    Z17 dB=z17(sb)*z17(sb)*z17(sb)*z17(B.D);
    if(oa.sign<0)dA=-dA;
    if(ob.sign<0)dB=-dB;
    if(dA==dB) return false;
    for(int i=0;i<3;i++){
        if(c17(aa[i])-c17(base[i])!=dA) throw std::runtime_error("A shift replay failed");
        if(c17(bb[i])-c17(base[i])!=dB) throw std::runtime_error("B shift replay failed");
    }
    std::array<Z17,9> q={base[0],bb[2],aa[1],bb[1],aa[0],base[2],aa[2],base[1],bb[0]};
    std::set<Z17> distinct(q.begin(),q.end());
    if(distinct.size()!=9||*distinct.begin()<=0)return false;
    std::array<Z17,9> q3;for(int i=0;i<9;i++)q3[i]=c17(q[i]);
    std::array<Z17,6> s={q3[0]+q3[1]+q3[2],q3[3]+q3[4]+q3[5],q3[6]+q3[7]+q3[8],q3[0]+q3[3]+q3[6],q3[1]+q3[4]+q3[7],q3[2]+q3[5]+q3[8]};
    for(int i=1;i<6;i++)if(s[i]!=s[0])throw std::runtime_error("six-sum replay failed");
    out<<"HIT D0="<<A.D<<" D1="<<B.D<<" sign0="<<oa.sign<<" sign1="<<ob.sign<<" scale0="<<sa<<" scale1="<<sb<<" bases=";
    for(int i=0;i<9;i++){if(i)out<<',';out<<q[i];}out<<" S="<<s[0]<<"\n";
    return true;
}

int main(int argc,char**argv){
    if(argc!=3){std::cerr<<"usage: r17 BFILE OUT\n";return 2;}
    auto t0=std::chrono::steady_clock::now(); auto ds=read17(argv[1]);
    if(ds.size()!=10000){std::cerr<<"INPUT_COUNT_FAIL "<<ds.size()<<"\n";return 11;}
    std::vector<G17> gs;gs.reserve(ds.size());bool anchor=false;size_t under3=0,maxrep=0;
    for(u64 D:ds){
        auto rp=reps(D);if(rp.size()<3)under3++;maxrep=std::max(maxrep,rp.size());
        if(D==4118877ULL){std::set<std::pair<u64,u64>>q(rp.begin(),rp.end());anchor=q.count({51,162})&&q.count({72,165})&&q.count({115,178})&&q.count({675,678});}
        gs.push_back({D,std::move(rp)});
    }
    if(under3)return 12;if(!anchor)return 13;
    std::ofstream out(argv[2]);if(!out)return 3;
    std::unordered_map<std::array<u64,3>,std::vector<O17>,H17> tab;tab.reserve(gs.size()*4);
    u64 signatures=0,collisions=0,equal_shift=0,degenerate=0,hits=0;
    for(size_t gi=0;gi<gs.size();gi++){
        auto const& rp=gs[gi].rp;
        for(size_t i=0;i<rp.size();i++)for(size_t j=i+1;j<rp.size();j++)for(size_t k=j+1;k<rp.size();k++){
            for(int sign:{1,-1}){
                std::array<u64,3> base,alt;
                std::array<size_t,3> ix={i,j,k};
                for(int t=0;t<3;t++){
                    auto [lo,hi]=rp[ix[t]];
                    if(sign>0){base[t]=lo;alt[t]=hi;}else{base[t]=hi;alt[t]=lo;}
                }
                // All endpoints are positive, so sorting base also fixes the unique proportional bijection.
                std::array<std::pair<u64,u64>,3> ba={{{base[0],alt[0]},{base[1],alt[1]},{base[2],alt[2]}}};
                std::sort(ba.begin(),ba.end());for(int t=0;t<3;t++){base[t]=ba[t].first;alt[t]=ba[t].second;}
                u64 g=std::gcd(base[0],std::gcd(base[1],base[2]));
                std::array<u64,3> key={base[0]/g,base[1]/g,base[2]/g};
                O17 cur{gi,sign,base,alt,g};signatures++;
                auto& vec=tab[key];
                for(auto const& prev:vec){
                    collisions++;
                    const u64 gg=std::gcd(prev.g,g),sa=g/gg,sb=prev.g/gg;
                    Z17 d0=z17(sa)*z17(sa)*z17(sa)*z17(gs[prev.gi].D),d1=z17(sb)*z17(sb)*z17(sb)*z17(gs[gi].D);
                    if(prev.sign<0)d0=-d0;if(sign<0)d1=-d1;
                    if(d0==d1){equal_shift++;continue;}
                    if(replay17(gs[prev.gi],prev,gs[gi],cur,out))hits++;else degenerate++;
                }
                vec.push_back(cur);
            }
        }
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT groups="<<gs.size()<<" max_rep="<<maxrep<<" signatures="<<signatures<<" collisions="<<collisions<<" equal_shift="<<equal_shift<<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    std::cerr<<"STAT groups="<<gs.size()<<" signatures="<<signatures<<" collisions="<<collisions<<" equal_shift="<<equal_shift<<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
