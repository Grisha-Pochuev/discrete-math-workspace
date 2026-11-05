#define main d1_old_main
#include "d1.cpp"
#undef main

#include <sstream>
#include <stdexcept>

static std::vector<u64> read23(const std::string& path){
    std::ifstream f(path); if(!f) throw std::runtime_error("open input");
    std::vector<u64> z; std::string line;
    while(std::getline(f,line)){
        if(line.empty()||line[0]=='#') continue;
        std::istringstream is(line); long long n; unsigned long long d;
        if(is>>n>>d) z.push_back((u64)d);
    }
    return z;
}

static bool close23(u64 D,
                    const std::pair<u64,u64>& ra,
                    const std::pair<u64,u64>& rb,
                    const std::pair<u64,u64>& rc,
                    std::ostream& out,u64& exact_tests){
    const u64 a=ra.first,au=ra.second,b=rb.first,bu=rb.second,c=rc.first,cu=rc.second;
    auto rr=reps_from_known(a,b);
    for(auto [p,q]:rr){
        if(p<=a) continue;
        u128 E=c3(p)-c3(a);
        if(E==(u128)D) continue;
        ++exact_tests;
        if(c3(q)-c3(b)!=E) throw std::runtime_error("replay K");
        u128 t=c3(c)+E; u64 w=fcbrt(t); if(c3(w)!=t) continue;
        std::array<u64,9> z={a,w,bu,q,au,c,cu,b,p};
        std::set<u64> ss(z.begin(),z.end()); if(ss.size()!=9||*ss.begin()==0) continue;
        std::array<u128,6> s={
            c3(z[0])+c3(z[1])+c3(z[2]),c3(z[3])+c3(z[4])+c3(z[5]),c3(z[6])+c3(z[7])+c3(z[8]),
            c3(z[0])+c3(z[3])+c3(z[6]),c3(z[1])+c3(z[4])+c3(z[7]),c3(z[2])+c3(z[5])+c3(z[8])};
        for(int i=1;i<6;i++) if(s[i]!=s[0]) throw std::runtime_error("six sums");
        out<<"HIT D="<<D<<" lower="<<a<<','<<b<<','<<c<<"\n";
        return true;
    }
    return false;
}

int main(int argc,char**argv){
    if(argc!=3){std::cerr<<"usage: r23 BFILE OUT\n";return 2;}
    auto t0=std::chrono::steady_clock::now(); auto ds=read23(argv[1]);
    if(ds.size()!=10000){std::cerr<<"INPUT_COUNT_FAIL "<<ds.size()<<"\n";return 11;}
    for(u64 D:{424910390480793ULL,15490327057569000ULL,123922616460552000ULL})
        if(std::find(ds.begin(),ds.end(),D)==ds.end()) ds.push_back(D);
    std::ofstream out(argv[2]); if(!out)return 3;
    u64 groups=0,triples=0,orient_pass=0,orient_equal=0,exact_tests=0,hits=0;
    u64 first_pass_D=0; size_t maxrep=0,under3=0;
    for(u64 D:ds){
        auto rp=reps(D); ++groups; maxrep=std::max(maxrep,rp.size());
        if(rp.size()<3){under3++;continue;}
        for(size_t i=0;i<rp.size();i++)for(size_t j=i+1;j<rp.size();j++)for(size_t k=j+1;k<rp.size();k++){
            ++triples;
            u128 K=c3(rp[j].first)-c3(rp[i].first);
            if(K<(u128)D) continue;
            ++orient_pass; if(K==(u128)D)++orient_equal;
            if(!first_pass_D)first_pass_D=D;
            out<<"PASS D="<<D<<" lower="<<rp[i].first<<','<<rp[j].first<<','<<rp[k].first<<" K="<<s128(K)<<"\n";
            if(close23(D,rp[i],rp[j],rp[k],out,exact_tests))hits++;
        }
    }
    if(under3){std::cerr<<"UNDER3 "<<under3<<"\n";return 12;}
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT groups="<<groups<<" max_rep="<<maxrep<<" triples="<<triples
       <<" orient_pass="<<orient_pass<<" orient_equal="<<orient_equal
       <<" exact_tests="<<exact_tests<<" hits="<<hits<<" first_pass_D="<<first_pass_D<<" ms="<<ms<<"\n";
    std::cerr<<"STAT groups="<<groups<<" triples="<<triples<<" orient_pass="<<orient_pass
             <<" exact_tests="<<exact_tests<<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
