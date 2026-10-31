// r16: proportional triple signatures across repeated cube differences.
#define main d1_old_main
#include "d1.cpp"
#undef main

#include <gmpxx.h>
#include <array>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

using big16 = mpz_class;

struct G16 { u64 D; std::vector<std::pair<u64,u64>> rp; };
struct Occ16 { size_t gi; std::array<u64,3> x; u64 g; };
struct KeyHash16 {
    size_t operator()(const std::array<u64,3>& a) const noexcept {
        auto mix=[](u64 x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);};
        return (size_t)(mix(a[0])^(mix(a[1])<<1)^(mix(a[2])>>1));
    }
};

static std::vector<u64> read16(const std::string& path){
    std::ifstream f(path);if(!f)throw std::runtime_error("open input");
    std::vector<u64> z;std::string line;
    while(std::getline(f,line)){
        if(line.empty()||line[0]=='#')continue;
        std::istringstream is(line);long long n;unsigned long long d;
        if(is>>n>>d)z.push_back((u64)d);
    }
    return z;
}
static u64 up16(const G16&g,u64 x){for(auto [a,b]:g.rp)if(a==x)return b;return 0;}
static big16 cube16(const big16&x){return x*x*x;}
static big16 z16(u64 x){return big16(std::to_string(x));}

static bool replay16(const G16&A,const Occ16&oa,const G16&B,const Occ16&ob,std::ostream&out){
    const u64 gg=std::gcd(oa.g,ob.g);
    const u64 sa=ob.g/gg, sb=oa.g/gg;
    std::array<big16,3> low;
    for(int i=0;i<3;i++){
        low[i]=z16(sa)*z16(oa.x[i]);
        big16 chk=z16(sb)*z16(ob.x[i]);
        if(low[i]!=chk)throw std::runtime_error("scale alignment failed");
    }
    std::array<big16,3> ua,ub;
    for(int i=0;i<3;i++){
        u64 xa=up16(A,oa.x[i]),xb=up16(B,ob.x[i]);
        if(!xa||!xb)throw std::runtime_error("missing upper");
        ua[i]=z16(sa)*z16(xa);ub[i]=z16(sb)*z16(xb);
    }
    std::array<big16,9> z={low[0],ub[2],ua[1],ub[1],ua[0],low[2],ua[2],low[1],ub[0]};
    std::set<big16> distinct(z.begin(),z.end());if(distinct.size()!=9||*distinct.begin()<=0)return false;
    std::array<big16,9> c;for(int i=0;i<9;i++)c[i]=cube16(z[i]);
    std::array<big16,6> s={c[0]+c[1]+c[2],c[3]+c[4]+c[5],c[6]+c[7]+c[8],c[0]+c[3]+c[6],c[1]+c[4]+c[7],c[2]+c[5]+c[8]};
    for(int i=1;i<6;i++)if(s[i]!=s[0])throw std::runtime_error("six-sum replay failed");
    big16 DA=z16(sa)*z16(sa)*z16(sa)*z16(A.D), DB=z16(sb)*z16(sb)*z16(sb)*z16(B.D);
    out<<"HIT D0="<<A.D<<" D1="<<B.D<<" scale0="<<sa<<" scale1="<<sb<<" scaledD0="<<DA<<" scaledD1="<<DB<<" key=";
    for(int i=0;i<3;i++){if(i)out<<',';out<<oa.x[i]/oa.g;}out<<" bases=";
    for(int i=0;i<9;i++){if(i)out<<',';out<<z[i];}out<<" S="<<s[0]<<"\n";
    return true;
}

int main(int argc,char**argv){
    if(argc!=3){std::cerr<<"usage: r16 BFILE OUT\n";return 2;}
    auto t0=std::chrono::steady_clock::now();auto ds=read16(argv[1]);
    if(ds.size()!=10000){std::cerr<<"INPUT_COUNT_FAIL "<<ds.size()<<"\n";return 11;}
    for(size_t i=1;i<ds.size();i++)if(ds[i]<=ds[i-1]){std::cerr<<"INPUT_ORDER_FAIL\n";return 12;}
    std::vector<G16> gs;gs.reserve(ds.size());size_t under3=0;bool anchor=false;size_t maxrep=0;
    for(u64 D:ds){auto rp=reps(D);if(rp.size()<3)under3++;maxrep=std::max(maxrep,rp.size());if(D==4118877ULL){std::set<std::pair<u64,u64>>q(rp.begin(),rp.end());anchor=q.count({51,162})&&q.count({72,165})&&q.count({115,178})&&q.count({675,678});}gs.push_back({D,std::move(rp)});}
    if(under3)return 13;if(!anchor)return 14;

    std::ofstream out(argv[2]);if(!out)return 3;
    std::unordered_map<std::array<u64,3>,std::vector<Occ16>,KeyHash16> tab;tab.reserve(gs.size()*2);
    u64 signatures=0,normalized_collisions=0,same_group=0,equal_scaled_diff=0,degenerate=0,hits=0;
    for(size_t gi=0;gi<gs.size();gi++){
        std::vector<u64>x;for(auto [a,b]:gs[gi].rp)x.push_back(a);
        for(size_t i=0;i<x.size();i++)for(size_t j=i+1;j<x.size();j++)for(size_t k=j+1;k<x.size();k++){
            std::array<u64,3> raw={x[i],x[j],x[k]};u64 g=std::gcd(raw[0],std::gcd(raw[1],raw[2]));
            std::array<u64,3> key={raw[0]/g,raw[1]/g,raw[2]/g};signatures++;
            auto& vec=tab[key];
            for(const auto& prev:vec){
                normalized_collisions++;
                if(prev.gi==gi){same_group++;continue;}
                u64 gg=std::gcd(prev.g,g),sa=g/gg,sb=prev.g/gg;
                big16 d0=z16(sa)*z16(sa)*z16(sa)*z16(gs[prev.gi].D),d1=z16(sb)*z16(sb)*z16(sb)*z16(gs[gi].D);
                if(d0==d1){equal_scaled_diff++;continue;}
                Occ16 cur{gi,raw,g};
                out<<"COLLISION D0="<<gs[prev.gi].D<<" D1="<<gs[gi].D<<" key="<<key[0]<<','<<key[1]<<','<<key[2]<<"\n";
                if(replay16(gs[prev.gi],prev,gs[gi],cur,out))hits++;else degenerate++;
            }
            vec.push_back({gi,raw,g});
        }
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT groups="<<gs.size()<<" max_rep="<<maxrep<<" signatures="<<signatures<<" normalized_collisions="<<normalized_collisions<<" same_group="<<same_group<<" equal_scaled_diff="<<equal_scaled_diff<<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    std::cerr<<"STAT groups="<<gs.size()<<" signatures="<<signatures<<" normalized_collisions="<<normalized_collisions<<" same_group="<<same_group<<" equal_scaled_diff="<<equal_scaled_diff<<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
