// r14: exact additive 3x3 cube-grid search from repeated cube differences.
#define main d1_old_main
#include "d1.cpp"
#undef main

#include <sstream>
#include <stdexcept>

struct Group14 {
    u64 D;
    int expected;
    std::vector<std::pair<u64,u64>> rp;
};

static std::vector<std::pair<int,u64>> read_bfile(const std::string& path,int expected){
    std::ifstream f(path); if(!f) throw std::runtime_error("open input");
    std::vector<std::pair<int,u64>> z; std::string line;
    while(std::getline(f,line)){
        if(line.empty()||line[0]=='#') continue;
        std::istringstream is(line); long long n; unsigned long long d;
        if(is>>n>>d) z.push_back({expected,(u64)d});
    }
    return z;
}

static u128 sum3(u64 a,u64 b,u64 c){return c3(a)+c3(b)+c3(c);}

static bool build_hit(const Group14& G,const Group14& H,const std::vector<u64>& common,std::ostream& out){
    if(common.size()<3) return false;
    auto upper=[](const Group14& g,u64 x)->u64{
        for(auto [a,b]:g.rp) if(a==x) return b;
        return 0;
    };
    for(size_t i=0;i<common.size();i++)for(size_t j=i+1;j<common.size();j++)for(size_t k=j+1;k<common.size();k++){
        u64 a=common[i],b=common[j],c=common[k];
        u64 A=upper(G,a),B=upper(G,b),C=upper(G,c);
        u64 X=upper(H,a),Q=upper(H,b),P=upper(H,c);
        if(!A||!B||!C||!X||!Q||!P) throw std::runtime_error("missing upper");
        std::array<u64,9> z={a,P,B,Q,A,c,C,b,X};
        std::set<u64> ss(z.begin(),z.end()); if(ss.size()!=9||*ss.begin()==0) continue;
        std::array<u128,6> s={
            sum3(z[0],z[1],z[2]),sum3(z[3],z[4],z[5]),sum3(z[6],z[7],z[8]),
            sum3(z[0],z[3],z[6]),sum3(z[1],z[4],z[7]),sum3(z[2],z[5],z[8])};
        for(int t=1;t<6;t++) if(s[t]!=s[0]) throw std::runtime_error("r14 replay failed");
        out<<"HIT D="<<G.D<<" T="<<H.D<<" common="<<a<<','<<b<<','<<c<<" bases=";
        for(int t=0;t<9;t++){if(t)out<<',';out<<z[t];}
        out<<" S="<<s128(s[0])<<"\n";
        return true;
    }
    return false;
}

int main(int argc,char**argv){
    if(argc!=4){std::cerr<<"usage: r14 B4 B5 OUT\n";return 2;}
    auto t0=std::chrono::steady_clock::now();
    auto g4=read_bfile(argv[1],4), g5=read_bfile(argv[2],5);
    if(g4.size()!=1000 || g5.size()!=150){std::cerr<<"INPUT_COUNT_FAIL "<<g4.size()<<' '<<g5.size()<<"\n";return 11;}
    auto a=g4; a.insert(a.end(),g5.begin(),g5.end());
    std::vector<Group14> gs; gs.reserve(a.size());
    size_t count_mismatch=0; bool anchor_ok=false;
    for(auto [expected,D]:a){
        auto rp=reps(D);
        if((int)rp.size()!=expected) count_mismatch++;
        if(D==4118877ULL){
            std::set<std::pair<u64,u64>> q(rp.begin(),rp.end());
            anchor_ok=q.count({51,162})&&q.count({72,165})&&q.count({115,178})&&q.count({675,678});
        }
        gs.push_back({D,expected,std::move(rp)});
    }
    if(!anchor_ok){std::cerr<<"ANCHOR_FAIL\n";return 12;}
    if(count_mismatch){std::cerr<<"COUNT_MISMATCH "<<count_mismatch<<"\n";return 13;}

    std::ofstream out(argv[3]); if(!out) return 3;
    u64 pairs=0,ge2=0,ge3=0,hits=0; size_t max_inter=0;
    for(size_t i=0;i<gs.size();i++)for(size_t j=i+1;j<gs.size();j++){
        pairs++;
        std::vector<u64> common;
        for(auto [x,y]:gs[i].rp) for(auto [u,v]:gs[j].rp) if(x==u) common.push_back(x);
        std::sort(common.begin(),common.end()); common.erase(std::unique(common.begin(),common.end()),common.end());
        max_inter=std::max(max_inter,common.size());
        if(common.size()>=2){ge2++;out<<"INTER n="<<common.size()<<" D="<<gs[i].D<<" T="<<gs[j].D<<" lower=";for(size_t t=0;t<common.size();t++){if(t)out<<',';out<<common[t];}out<<"\n";}
        if(common.size()>=3){ge3++; if(build_hit(gs[i],gs[j],common,out)) hits++;}
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT groups="<<gs.size()<<" groups4="<<g4.size()<<" groups5="<<g5.size()
       <<" pairs="<<pairs<<" max_intersection="<<max_inter<<" intersections_ge2="<<ge2<<" intersections_ge3="<<ge3<<" hits="<<hits<<" ms="<<ms<<"\n";
    std::cerr<<"STAT groups="<<gs.size()<<" pairs="<<pairs<<" max_intersection="<<max_inter<<" ge2="<<ge2<<" ge3="<<ge3<<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
