// r18: broaden the signed proportional-signature probe over a union of tables.
#define main d1_old_main_r18
#include "d1.cpp"
#undef main

#include <gmpxx.h>
#include <array>
#include <map>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

using Z18=mpz_class;
struct G18{u64 D;std::vector<std::pair<u64,u64>>rp;};
struct O18{size_t gi;int sign;std::array<u64,3>base,alt;u64 g;};
struct H18{
    size_t operator()(const std::array<u64,3>&a)const noexcept{
        auto mix=[](u64 x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);};
        return(size_t)(mix(a[0])^(mix(a[1])<<1)^(mix(a[2])>>1));
    }
};
static Z18 z18(u64 x){return Z18(std::to_string(x));}
static Z18 cube18(const Z18&x){return x*x*x;}
static std::vector<u64> read18(const std::string&path){
    std::ifstream f(path);if(!f)throw std::runtime_error("open input");
    std::vector<u64>z;std::string line;
    while(std::getline(f,line)){
        if(line.empty()||line[0]=='#')continue;
        std::istringstream is(line);long long n;unsigned long long d;
        if(is>>n>>d)z.push_back((u64)d);
    }
    return z;
}
static mpq_class normalized_shift18(const G18&g,const O18&o){
    Z18 den=z18(o.g);den=den*den*den;
    mpq_class q(z18(g.D),den);if(o.sign<0)q=-q;q.canonicalize();return q;
}
static bool replay18(const G18&A,const O18&oa,const G18&B,const O18&ob,std::ostream&out){
    const u64 gg=std::gcd(oa.g,ob.g),sa=ob.g/gg,sb=oa.g/gg;
    std::array<Z18,3>base,aa,bb;
    for(int i=0;i<3;i++){
        base[i]=z18(sa)*z18(oa.base[i]);
        if(base[i]!=z18(sb)*z18(ob.base[i]))throw std::runtime_error("base alignment failed");
        aa[i]=z18(sa)*z18(oa.alt[i]);bb[i]=z18(sb)*z18(ob.alt[i]);
    }
    Z18 dA=z18(sa)*z18(sa)*z18(sa)*z18(A.D),dB=z18(sb)*z18(sb)*z18(sb)*z18(B.D);
    if(oa.sign<0)dA=-dA;if(ob.sign<0)dB=-dB;if(dA==dB)return false;
    for(int i=0;i<3;i++){
        if(cube18(aa[i])-cube18(base[i])!=dA)throw std::runtime_error("A replay failed");
        if(cube18(bb[i])-cube18(base[i])!=dB)throw std::runtime_error("B replay failed");
    }
    std::array<Z18,9>q={base[0],bb[2],aa[1],bb[1],aa[0],base[2],aa[2],base[1],bb[0]};
    std::set<Z18>distinct(q.begin(),q.end());if(distinct.size()!=9||*distinct.begin()<=0)return false;
    std::array<Z18,9>q3;for(int i=0;i<9;i++)q3[i]=cube18(q[i]);
    std::array<Z18,6>s={q3[0]+q3[1]+q3[2],q3[3]+q3[4]+q3[5],q3[6]+q3[7]+q3[8],q3[0]+q3[3]+q3[6],q3[1]+q3[4]+q3[7],q3[2]+q3[5]+q3[8]};
    for(int i=1;i<6;i++)if(s[i]!=s[0])throw std::runtime_error("six-sum replay failed");
    out<<"HIT D0="<<A.D<<" D1="<<B.D<<" sign0="<<oa.sign<<" sign1="<<ob.sign<<" scale0="<<sa<<" scale1="<<sb<<" bases=";
    for(int i=0;i<9;i++){if(i)out<<',';out<<q[i];}out<<" S="<<s[0]<<"\n";return true;
}
static void merge18(const std::string&path,int exact,std::map<u64,int>&want,
                    std::unordered_set<u64>&plus,bool is_plus,size_t expected_count){
    auto v=read18(path);
    if(v.size()!=expected_count){
        std::cerr<<"INPUT_COUNT_FAIL "<<path<<" "<<v.size()<<" expected="<<expected_count<<"\n";
        throw std::runtime_error("input count");
    }
    for(u64 D:v){
        if(is_plus)plus.insert(D);
        auto it=want.find(D);
        if(it==want.end())want.emplace(D,exact);
        else if(exact){
            if(it->second&&it->second!=exact)throw std::runtime_error("inconsistent exact multiplicity");
            it->second=exact;
        }
    }
}

int main(int argc,char**argv){
    if(argc!=6){std::cerr<<"usage: r18 BPLUS B3 B4 B5 OUT\n";return 2;}
    auto t0=std::chrono::steady_clock::now();std::map<u64,int>want;std::unordered_set<u64>plus;
    try{
        merge18(argv[1],0,want,plus,true,10000);
        merge18(argv[2],3,want,plus,false,10000);
        merge18(argv[3],4,want,plus,false,1000);
        merge18(argv[4],5,want,plus,false,150);
    }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 11;}
    for(u64 D:{424910390480793ULL,15490327057569000ULL,123922616460552000ULL})if(!want.count(D))want.emplace(D,0);
    const size_t union_groups=want.size();size_t new_vs_plus=0;for(auto const&kv:want)if(!plus.count(kv.first))new_vs_plus++;

    std::vector<G18>gs;gs.reserve(want.size());bool anchor=false;size_t under3=0,count_mismatch=0,maxrep=0;u64 total_reps=0;
    for(auto[D,exact]:want){
        auto rp=reps(D);if(rp.size()<3)under3++;if(exact&&(int)rp.size()!=exact)count_mismatch++;
        maxrep=std::max(maxrep,rp.size());total_reps+=rp.size();
        if(D==4118877ULL){std::set<std::pair<u64,u64>>q(rp.begin(),rp.end());anchor=q.count({51,162})&&q.count({72,165})&&q.count({115,178})&&q.count({675,678});}
        gs.push_back({D,std::move(rp)});
    }
    if(under3){std::cerr<<"UNDER3 "<<under3<<"\n";return 12;}
    if(count_mismatch){std::cerr<<"COUNT_MISMATCH "<<count_mismatch<<"\n";return 13;}
    if(!anchor){std::cerr<<"ANCHOR_FAIL\n";return 14;}

    std::ofstream out(argv[5]);if(!out)return 3;
    std::unordered_map<std::array<u64,3>,std::vector<O18>,H18>tab;tab.reserve(gs.size()*4);
    u64 signatures=0,kept=0,collisions=0,duplicate_shift=0,degenerate=0,hits=0;
    for(size_t gi=0;gi<gs.size();gi++){
        auto const&rp=gs[gi].rp;
        for(size_t i=0;i<rp.size();i++)for(size_t j=i+1;j<rp.size();j++)for(size_t k=j+1;k<rp.size();k++)for(int sign:{1,-1}){
            std::array<u64,3>base,alt;std::array<size_t,3>ix={i,j,k};
            for(int t=0;t<3;t++){auto[lo,hi]=rp[ix[t]];if(sign>0){base[t]=lo;alt[t]=hi;}else{base[t]=hi;alt[t]=lo;}}
            std::array<std::pair<u64,u64>,3>ba={{{base[0],alt[0]},{base[1],alt[1]},{base[2],alt[2]}}};
            std::sort(ba.begin(),ba.end());for(int t=0;t<3;t++){base[t]=ba[t].first;alt[t]=ba[t].second;}
            u64 g=std::gcd(base[0],std::gcd(base[1],base[2]));std::array<u64,3>key={base[0]/g,base[1]/g,base[2]/g};
            O18 cur{gi,sign,base,alt,g};signatures++;auto&vec=tab[key];const mpq_class qcur=normalized_shift18(gs[gi],cur);
            bool duplicate=false;for(auto const&prev:vec)if(normalized_shift18(gs[prev.gi],prev)==qcur){duplicate=true;break;}
            if(duplicate){duplicate_shift++;continue;}
            for(auto const&prev:vec){collisions++;if(replay18(gs[prev.gi],prev,gs[gi],cur,out))hits++;else degenerate++;}
            vec.push_back(cur);kept++;
        }
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT union_groups="<<union_groups<<" new_vs_plus="<<new_vs_plus<<" max_rep="<<maxrep<<" total_reps="<<total_reps
       <<" signatures="<<signatures<<" kept="<<kept<<" collisions="<<collisions<<" duplicate_shift="<<duplicate_shift
       <<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    std::cerr<<"STAT union_groups="<<union_groups<<" new_vs_plus="<<new_vs_plus<<" max_rep="<<maxrep
             <<" signatures="<<signatures<<" kept="<<kept<<" collisions="<<collisions<<" duplicate_shift="<<duplicate_shift
             <<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
