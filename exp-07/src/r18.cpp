// r18: broaden r17 by taking the union of the available repeated-difference tables.
#define main r17_old_main
#include "r17.cpp"
#undef main

#include <map>
#include <unordered_set>

static void merge18(const std::string& path,int exact,
                    std::map<u64,int>& want,std::unordered_set<u64>& plus,
                    bool is_plus,size_t expected_count){
    auto v=read17(path);
    if(v.size()!=expected_count){
        std::cerr<<"INPUT_COUNT_FAIL "<<path<<" "<<v.size()<<" expected="<<expected_count<<"\n";
        throw std::runtime_error("input count");
    }
    for(u64 D:v){
        if(is_plus) plus.insert(D);
        auto it=want.find(D);
        if(it==want.end()) want.emplace(D,exact);
        else if(exact){
            if(it->second && it->second!=exact) throw std::runtime_error("inconsistent exact multiplicity");
            it->second=exact;
        }
    }
}

int main(int argc,char**argv){
    if(argc!=6){std::cerr<<"usage: r18 BPLUS B3 B4 B5 OUT\n";return 2;}
    auto t0=std::chrono::steady_clock::now();
    std::map<u64,int> want;
    std::unordered_set<u64> plus;
    try{
        merge18(argv[1],0,want,plus,true,10000);
        merge18(argv[2],3,want,plus,false,10000);
        merge18(argv[3],4,want,plus,false,1000);
        merge18(argv[4],5,want,plus,false,150);
    }catch(const std::exception&e){std::cerr<<e.what()<<"\n";return 11;}

    // Known high-multiplicity seeds.  Acceptance never trusts the external
    // multiplicity: reps() reconstructs all positive representations exactly.
    for(u64 D:{424910390480793ULL,15490327057569000ULL,123922616460552000ULL})
        if(!want.count(D)) want.emplace(D,0);

    const size_t union_groups=want.size();
    size_t new_vs_plus=0;
    for(auto const& kv:want) if(!plus.count(kv.first)) new_vs_plus++;

    std::vector<G17> gs;gs.reserve(want.size());
    bool anchor=false;size_t under3=0,count_mismatch=0,maxrep=0;u64 total_reps=0;
    for(auto [D,exact]:want){
        auto rp=reps(D);
        if(rp.size()<3) under3++;
        if(exact && (int)rp.size()!=exact) count_mismatch++;
        maxrep=std::max(maxrep,rp.size());total_reps+=rp.size();
        if(D==4118877ULL){
            std::set<std::pair<u64,u64>>q(rp.begin(),rp.end());
            anchor=q.count({51,162})&&q.count({72,165})&&q.count({115,178})&&q.count({675,678});
        }
        gs.push_back({D,std::move(rp)});
    }
    if(under3){std::cerr<<"UNDER3 "<<under3<<"\n";return 12;}
    if(count_mismatch){std::cerr<<"COUNT_MISMATCH "<<count_mismatch<<"\n";return 13;}
    if(!anchor){std::cerr<<"ANCHOR_FAIL\n";return 14;}

    std::ofstream out(argv[5]);if(!out)return 3;
    std::unordered_map<std::array<u64,3>,std::vector<O17>,H17> tab;
    tab.reserve(gs.size()*4);
    u64 signatures=0,kept=0,collisions=0,duplicate_shift=0,degenerate=0,hits=0;
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
                std::array<std::pair<u64,u64>,3> ba={{{base[0],alt[0]},{base[1],alt[1]},{base[2],alt[2]}}};
                std::sort(ba.begin(),ba.end());
                for(int t=0;t<3;t++){base[t]=ba[t].first;alt[t]=ba[t].second;}
                u64 g=std::gcd(base[0],std::gcd(base[1],base[2]));
                std::array<u64,3> key={base[0]/g,base[1]/g,base[2]/g};
                O17 cur{gi,sign,base,alt,g};signatures++;
                auto& vec=tab[key];
                const mpq_class qcur=normalized_shift17(gs[gi],cur);
                bool duplicate=false;
                for(auto const& prev:vec){
                    if(normalized_shift17(gs[prev.gi],prev)==qcur){duplicate=true;break;}
                }
                if(duplicate){duplicate_shift++;continue;}
                for(auto const& prev:vec){
                    collisions++;
                    if(replay17(gs[prev.gi],prev,gs[gi],cur,out))hits++;else degenerate++;
                }
                vec.push_back(cur);kept++;
            }
        }
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT union_groups="<<union_groups<<" new_vs_plus="<<new_vs_plus
       <<" max_rep="<<maxrep<<" total_reps="<<total_reps
       <<" signatures="<<signatures<<" kept="<<kept
       <<" collisions="<<collisions<<" duplicate_shift="<<duplicate_shift
       <<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    std::cerr<<"STAT union_groups="<<union_groups<<" new_vs_plus="<<new_vs_plus
             <<" max_rep="<<maxrep<<" signatures="<<signatures<<" kept="<<kept
             <<" collisions="<<collisions<<" duplicate_shift="<<duplicate_shift
             <<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
