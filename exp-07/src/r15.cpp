// r15: hash triples of lower endpoints across repeated cube differences.
#define main d1_old_main
#include "d1.cpp"
#undef main

#include <array>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

struct G15 {
    u64 D;
    std::vector<std::pair<u64,u64>> rp;
};

struct A3Hash {
    size_t operator()(const std::array<u64,3>& a) const noexcept {
        auto mix=[](u64 x){
            x += 0x9e3779b97f4a7c15ULL;
            x = (x^(x>>30))*0xbf58476d1ce4e5b9ULL;
            x = (x^(x>>27))*0x94d049bb133111ebULL;
            return x^(x>>31);
        };
        return (size_t)(mix(a[0]) ^ (mix(a[1])<<1) ^ (mix(a[2])>>1));
    }
};

static std::vector<u64> read15(const std::string& path){
    std::ifstream f(path); if(!f) throw std::runtime_error("open input");
    std::vector<u64> z; std::string line;
    while(std::getline(f,line)){
        if(line.empty()||line[0]=='#') continue;
        std::istringstream is(line); long long n; unsigned long long d;
        if(is>>n>>d) z.push_back((u64)d);
    }
    return z;
}

static u64 upper15(const G15& g,u64 x){
    for(auto [a,b]:g.rp) if(a==x) return b;
    return 0;
}
static u128 sum15(u64 a,u64 b,u64 c){return c3(a)+c3(b)+c3(c);}

static bool replay15(const G15& G,const G15& H,const std::array<u64,3>& t,std::ostream& out){
    const u64 a=t[0],b=t[1],c=t[2];
    const u64 A=upper15(G,a),B=upper15(G,b),C=upper15(G,c);
    const u64 X=upper15(H,a),Q=upper15(H,b),P=upper15(H,c);
    if(!A||!B||!C||!X||!Q||!P) throw std::runtime_error("missing upper");
    std::array<u64,9> z={a,P,B,Q,A,c,C,b,X};
    std::set<u64> ss(z.begin(),z.end());
    if(ss.size()!=9 || *ss.begin()==0) return false;
    std::array<u128,6> s={
        sum15(z[0],z[1],z[2]),sum15(z[3],z[4],z[5]),sum15(z[6],z[7],z[8]),
        sum15(z[0],z[3],z[6]),sum15(z[1],z[4],z[7]),sum15(z[2],z[5],z[8])};
    for(int i=1;i<6;i++) if(s[i]!=s[0]) throw std::runtime_error("six-sum replay failed");
    out<<"HIT D="<<G.D<<" T="<<H.D<<" lower="<<a<<','<<b<<','<<c<<" bases=";
    for(int i=0;i<9;i++){if(i)out<<',';out<<z[i];}
    out<<" S="<<s128(s[0])<<"\n";
    return true;
}

int main(int argc,char**argv){
    if(argc!=3){std::cerr<<"usage: r15 BFILE OUT\n";return 2;}
    auto t0=std::chrono::steady_clock::now();
    auto ds=read15(argv[1]);
    if(ds.size()!=10000){std::cerr<<"INPUT_COUNT_FAIL "<<ds.size()<<"\n";return 11;}
    for(size_t i=1;i<ds.size();i++) if(ds[i]<=ds[i-1]){std::cerr<<"INPUT_ORDER_FAIL\n";return 12;}

    std::vector<G15> gs; gs.reserve(ds.size());
    size_t minrep=999,maxrep=0,under3=0,total_reps=0;
    bool anchor=false;
    for(u64 D:ds){
        auto rp=reps(D);
        minrep=std::min(minrep,rp.size()); maxrep=std::max(maxrep,rp.size());
        total_reps+=rp.size(); if(rp.size()<3) under3++;
        if(D==4118877ULL){
            std::set<std::pair<u64,u64>> q(rp.begin(),rp.end());
            anchor=q.count({51,162})&&q.count({72,165})&&q.count({115,178})&&q.count({675,678});
        }
        gs.push_back({D,std::move(rp)});
    }
    if(under3){std::cerr<<"UNDER3 "<<under3<<"\n";return 13;}
    if(!anchor){std::cerr<<"ANCHOR_FAIL\n";return 14;}

    std::ofstream out(argv[2]); if(!out)return 3;
    std::unordered_map<std::array<u64,3>,size_t,A3Hash> first;
    first.reserve(gs.size()*2);
    u64 signatures=0,duplicate_signatures=0,hits=0,degenerate=0;
    for(size_t gi=0;gi<gs.size();gi++){
        std::vector<u64> x; x.reserve(gs[gi].rp.size());
        for(auto [a,b]:gs[gi].rp)x.push_back(a);
        for(size_t i=0;i<x.size();i++)for(size_t j=i+1;j<x.size();j++)for(size_t k=j+1;k<x.size();k++){
            std::array<u64,3> key={x[i],x[j],x[k]};
            signatures++;
            auto [it,inserted]=first.emplace(key,gi);
            if(inserted)continue;
            const size_t gj=it->second;
            if(gj==gi)continue;
            duplicate_signatures++;
            out<<"DUP D="<<gs[gj].D<<" T="<<gs[gi].D<<" lower="<<key[0]<<','<<key[1]<<','<<key[2]<<"\n";
            if(replay15(gs[gj],gs[gi],key,out))hits++; else degenerate++;
        }
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT groups="<<gs.size()<<" min_rep="<<minrep<<" max_rep="<<maxrep<<" total_reps="<<total_reps
       <<" signatures="<<signatures<<" duplicate_signatures="<<duplicate_signatures
       <<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    std::cerr<<"STAT groups="<<gs.size()<<" min_rep="<<minrep<<" max_rep="<<maxrep
             <<" signatures="<<signatures<<" duplicate_signatures="<<duplicate_signatures
             <<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
