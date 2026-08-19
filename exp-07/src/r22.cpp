// r22: exact transverse repeated-difference filter from the r20 normal form.
#define main d1_old_main
#include "d1.cpp"
#undef main

#include <array>
#include <sstream>
#include <stdexcept>

struct G22 {
    u64 D;
    std::vector<std::pair<u64,u64>> rp;
};

struct E22 {
    std::vector<std::pair<u64,u64>> rp;
};

static std::vector<u64> read22(const std::string& path){
    std::ifstream f(path);
    if(!f) throw std::runtime_error("open input");
    std::vector<u64> z;
    std::string line;
    while(std::getline(f,line)){
        if(line.empty() || line[0]=='#') continue;
        std::istringstream is(line);
        long long n;
        unsigned long long d;
        if(is>>n>>d) z.push_back((u64)d);
    }
    return z;
}

static bool has22(const std::vector<std::pair<u64,u64>>& v,
                  std::pair<u64,u64> q){
    return std::binary_search(v.begin(),v.end(),q);
}

static u128 sum22(u64 a,u64 b,u64 c){
    return c3(a)+c3(b)+c3(c);
}

static bool close22(const G22& g,
                    const std::pair<u64,u64>& ra,
                    const std::pair<u64,u64>& rb,
                    const std::pair<u64,u64>& rc,
                    const std::vector<std::pair<u64,u64>>& kab,
                    std::ostream& out,
                    u64& closure_tests){
    const u64 a=ra.first, au=ra.second;
    const u64 b=rb.first, bu=rb.second;
    const u64 c=rc.first, cu=rc.second;

    for(auto [p,q]:kab){
        if(p<=a) continue; // normalized positive second shift only
        const u128 E=c3(p)-c3(a);
        if(E==(u128)g.D) continue;
        ++closure_tests;
        if(q<=b || c3(q)-c3(b)!=E)
            throw std::runtime_error("K_ab replay failed");

        const u128 wcube=c3(c)+E;
        const u64 w=fcbrt(wcube);
        if(c3(w)!=wcube) continue;

        // r20 Latin placement for base cubes a^3,b^3,c^3 and offsets D,E:
        // a, w, bu / q, au, c / cu, b, p.
        std::array<u64,9> z={a,w,bu,q,au,c,cu,b,p};
        std::set<u64> distinct(z.begin(),z.end());
        if(distinct.size()!=9 || *distinct.begin()==0) continue;

        std::array<u128,6> s={
            sum22(z[0],z[1],z[2]),
            sum22(z[3],z[4],z[5]),
            sum22(z[6],z[7],z[8]),
            c3(z[0])+c3(z[3])+c3(z[6]),
            c3(z[1])+c3(z[4])+c3(z[7]),
            c3(z[2])+c3(z[5])+c3(z[8])
        };
        for(int i=1;i<6;i++)
            if(s[i]!=s[0]) throw std::runtime_error("six-sum replay failed");

        out<<"HIT D="<<g.D<<" E="<<s128(E)<<" lower="
           <<a<<','<<b<<','<<c<<" bases=";
        for(int i=0;i<9;i++){
            if(i) out<<',';
            out<<z[i];
        }
        out<<" S="<<s128(s[0])<<"\n";
        return true;
    }
    return false;
}

int main(int argc,char**argv){
    if(argc<3 || argc>4){
        std::cerr<<"usage: r22 BFILE OUT [limit_groups]\n";
        return 2;
    }
    const size_t limit = argc==4 ? (size_t)std::stoull(argv[3]) : 0;
    auto t0=std::chrono::steady_clock::now();
    auto ds=read22(argv[1]);
    if(ds.size()!=10000){
        std::cerr<<"INPUT_COUNT_FAIL "<<ds.size()<<"\n";
        return 11;
    }
    const size_t listed=ds.size();

    // Independently reconstructed high-multiplicity seeds used by r17 as well.
    for(u64 D:{424910390480793ULL,15490327057569000ULL,123922616460552000ULL})
        if(std::find(ds.begin(),ds.end(),D)==ds.end()) ds.push_back(D);
    if(limit && ds.size()>limit) ds.resize(limit);

    std::ofstream out(argv[2]);
    if(!out) return 3;

    u64 groups=0,total_reps=0,pair_checks=0,pair_ge3=0;
    u64 triples=0,fail_ab=0,fail_bc=0,fail_ac=0,all3=0;
    u64 closure_tests=0,hits=0;
    size_t max_rep=0,max_trans_rep=0,under3=0;
    bool anchor=false;

    for(u64 D:ds){
        auto rp=reps(D);
        ++groups;
        total_reps+=rp.size();
        max_rep=std::max(max_rep,rp.size());
        if(rp.size()<3){++under3;continue;}
        if(D==4118877ULL){
            std::set<std::pair<u64,u64>> q(rp.begin(),rp.end());
            anchor=q.count({51,162})&&q.count({72,165})&&
                   q.count({115,178})&&q.count({675,678});
        }

        const size_t m=rp.size();
        std::vector<std::vector<E22>> edge(m,std::vector<E22>(m));
        for(size_t i=0;i<m;i++) for(size_t j=i+1;j<m;j++){
            const u64 a=rp[i].first,b=rp[j].first;
            auto rr=reps_from_known(a,b);
            ++pair_checks;
            max_trans_rep=std::max(max_trans_rep,rr.size());
            // Equation (1) from r22 must already supply the base and D layers.
            if(!has22(rr,{rp[i].first,rp[j].first}) ||
               !has22(rr,{rp[i].second,rp[j].second})){
                std::cerr<<"TRANSVERSE_REPLAY_FAIL D="<<D<<" i="<<i<<" j="<<j<<"\n";
                return 14;
            }
            if(rr.size()>=3) ++pair_ge3;
            edge[i][j].rp=std::move(rr);
        }

        for(size_t i=0;i<m;i++) for(size_t j=i+1;j<m;j++) for(size_t k=j+1;k<m;k++){
            ++triples;
            if(edge[i][j].rp.size()<3){++fail_ab;continue;}
            if(edge[j][k].rp.size()<3){++fail_bc;continue;}
            if(edge[i][k].rp.size()<3){++fail_ac;continue;}
            ++all3;
            if(close22({D,rp},rp[i],rp[j],rp[k],edge[i][j].rp,out,closure_tests)){
                ++hits;
                out.flush();
            }
        }
    }

    if(under3){
        std::cerr<<"UNDER3 "<<under3<<"\n";
        return 12;
    }
    // The anchor is only guaranteed when the full beginning of A265625 is used.
    if((!limit || limit>=listed) && !anchor){
        std::cerr<<"ANCHOR_FAIL\n";
        return 13;
    }

    const auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now()-t0).count();
    out<<"STAT listed="<<listed<<" groups="<<groups
       <<" total_reps="<<total_reps<<" max_rep="<<max_rep
       <<" pair_checks="<<pair_checks<<" pair_ge3="<<pair_ge3
       <<" max_trans_rep="<<max_trans_rep
       <<" triples="<<triples<<" fail_ab="<<fail_ab
       <<" fail_bc="<<fail_bc<<" fail_ac="<<fail_ac
       <<" all3="<<all3<<" closure_tests="<<closure_tests
       <<" hits="<<hits<<" ms="<<ms<<"\n";
    std::cerr<<"STAT groups="<<groups<<" pair_checks="<<pair_checks
             <<" pair_ge3="<<pair_ge3<<" triples="<<triples
             <<" all3="<<all3<<" closure_tests="<<closure_tests
             <<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
