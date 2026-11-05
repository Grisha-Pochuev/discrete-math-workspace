// r19: close each signed base triple by enumerating the second shift directly.
#define main d1_old_main_r19
#include "d1.cpp"
#undef main

#include <gmpxx.h>
#include <array>
#include <map>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <unordered_set>

struct G19{u64 D;std::vector<std::pair<u64,u64>>rp;};
struct H19{
    size_t operator()(const std::array<u64,3>&a)const noexcept{
        auto mix=[](u64 x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);};
        return(size_t)(mix(a[0])^(mix(a[1])<<1)^(mix(a[2])>>1));
    }
};
static std::vector<u64> read19(const std::string&path){
    std::ifstream f(path);if(!f)throw std::runtime_error("open input");std::vector<u64>z;std::string line;
    while(std::getline(f,line)){if(line.empty()||line[0]=='#')continue;std::istringstream is(line);long long n;unsigned long long d;if(is>>n>>d)z.push_back((u64)d);}return z;
}
static void merge19(const std::string&path,int exact,std::map<u64,int>&want,size_t expected_count){
    auto v=read19(path);if(v.size()!=expected_count)throw std::runtime_error("input count");
    for(u64 D:v){auto it=want.find(D);if(it==want.end())want.emplace(D,exact);else if(exact){if(it->second&&it->second!=exact)throw std::runtime_error("multiplicity conflict");it->second=exact;}}
}
static mpq_class shift19(u64 D,int sign,u64 g){
    mpz_class den(std::to_string(g));den=den*den*den;mpq_class q(mpz_class(std::to_string(D)),den);if(sign<0)q=-q;q.canonicalize();return q;
}
static u128 qpair19(u64 a,u64 b){return(u128)a*a+(u128)a*b+(u128)b*b;}
static bool same_signed19(u64 a,u64 b,u64 p,u64 q,bool&pos,u128&mag){
    u128 A=c3(a),B=c3(b),P=c3(p),Q=c3(q);
    if(P>=A){pos=true;mag=P-A;return Q>=B&&Q-B==mag;}
    pos=false;mag=A-P;return B>=Q&&B-Q==mag;
}
static bool verify19(const G19&G,int sign,const std::array<u64,3>&base,const std::array<u64,3>&aa,
                     const std::array<u64,3>&bb,bool epos,u128 emag,std::ostream&out){
    for(int i=0;i<3;i++){
        if(sign>0){if(c3(aa[i])<c3(base[i])||c3(aa[i])-c3(base[i])!=(u128)G.D)throw std::runtime_error("first shift replay");}
        else{if(c3(base[i])<c3(aa[i])||c3(base[i])-c3(aa[i])!=(u128)G.D)throw std::runtime_error("first shift replay");}
        if(epos){if(c3(bb[i])<c3(base[i])||c3(bb[i])-c3(base[i])!=emag)throw std::runtime_error("second shift replay");}
        else{if(c3(base[i])<c3(bb[i])||c3(base[i])-c3(bb[i])!=emag)throw std::runtime_error("second shift replay");}
    }
    if(emag==0)return false;
    if((epos&&sign>0&&emag==(u128)G.D)||(!epos&&sign<0&&emag==(u128)G.D))return false;
    std::array<u64,9>z={base[0],bb[2],aa[1],bb[1],aa[0],base[2],aa[2],base[1],bb[0]};
    std::set<u64>ss(z.begin(),z.end());if(ss.size()!=9||*ss.begin()==0)return false;
    std::array<u128,9>x;for(int i=0;i<9;i++)x[i]=c3(z[i]);
    std::array<u128,6>s={x[0]+x[1]+x[2],x[3]+x[4]+x[5],x[6]+x[7]+x[8],x[0]+x[3]+x[6],x[1]+x[4]+x[7],x[2]+x[5]+x[8]};
    for(int i=1;i<6;i++)if(s[i]!=s[0])throw std::runtime_error("six-sum replay");
    out<<"HIT D0="<<G.D<<" sign0="<<sign<<" sign1="<<(epos?1:-1)<<" D1="<<s128(emag)<<" bases=";
    for(int i=0;i<9;i++){if(i)out<<',';out<<z[i];}out<<" S="<<s128(s[0])<<"\n";return true;
}

int main(int argc,char**argv){
    if(argc!=6){std::cerr<<"usage: r19 BPLUS B3 B4 B5 OUT\n";return 2;}
    auto t0=std::chrono::steady_clock::now();std::map<u64,int>want;
    try{merge19(argv[1],0,want,10000);merge19(argv[2],3,want,10000);merge19(argv[3],4,want,1000);merge19(argv[4],5,want,150);}catch(const std::exception&e){std::cerr<<"INPUT_FAIL "<<e.what()<<"\n";return 11;}
    for(u64 D:{424910390480793ULL,15490327057569000ULL,123922616460552000ULL})if(!want.count(D))want.emplace(D,0);
    std::vector<G19>gs;gs.reserve(want.size());size_t under3=0,mismatch=0,maxrep=0;bool anchor=false;
    for(auto[D,exact]:want){auto rp=reps(D);if(rp.size()<3)under3++;if(exact&&(int)rp.size()!=exact)mismatch++;maxrep=std::max(maxrep,rp.size());if(D==4118877ULL){std::set<std::pair<u64,u64>>q(rp.begin(),rp.end());anchor=q.count({51,162})&&q.count({72,165})&&q.count({115,178})&&q.count({675,678});}gs.push_back({D,std::move(rp)});}
    if(under3||mismatch||!anchor){std::cerr<<"SOURCE_REPLAY_FAIL under3="<<under3<<" mismatch="<<mismatch<<" anchor="<<anchor<<"\n";return 12;}

    std::ofstream out(argv[5]);if(!out)return 3;
    std::unordered_map<std::array<u64,3>,std::vector<mpq_class>,H19>seen;seen.reserve(gs.size()*3);
    u64 raw=0,unique=0,dups=0,qoverflow=0,pair_reps=0,nonzero_second=0,third_cubes=0,degenerate=0,hits=0;
    for(size_t gi=0;gi<gs.size();gi++){
        auto const&rp=gs[gi].rp;
        for(size_t i=0;i<rp.size();i++)for(size_t j=i+1;j<rp.size();j++)for(size_t k=j+1;k<rp.size();k++)for(int sign:{1,-1}){
            raw++;std::array<u64,3>base,aa;std::array<size_t,3>ix={i,j,k};
            for(int t=0;t<3;t++){auto[lo,hi]=rp[ix[t]];if(sign>0){base[t]=lo;aa[t]=hi;}else{base[t]=hi;aa[t]=lo;}}
            std::array<std::pair<u64,u64>,3>ba={{{base[0],aa[0]},{base[1],aa[1]},{base[2],aa[2]}}};std::sort(ba.begin(),ba.end());for(int t=0;t<3;t++){base[t]=ba[t].first;aa[t]=ba[t].second;}
            u64 g=std::gcd(base[0],std::gcd(base[1],base[2]));std::array<u64,3>key={base[0]/g,base[1]/g,base[2]/g};mpq_class nq=shift19(gs[gi].D,sign,g);
            auto&sv=seen[key];bool dup=false;for(auto const&q:sv)if(q==nq){dup=true;break;}if(dup){dups++;continue;}sv.push_back(nq);unique++;

            int ia=0,ib=1,ir=2;u128 q01=qpair19(base[0],base[1]),q12=qpair19(base[1],base[2]);if(q12<q01){ia=1;ib=2;ir=0;}
            u128 Q=qpair19(base[ia],base[ib]);if(Q>UINT64_MAX){qoverflow++;continue;}
            auto rr=reps_from_known(base[ia],base[ib]);pair_reps+=rr.size();
            for(auto[p,q]:rr){
                if(p==base[ia]&&q==base[ib])continue;bool epos;u128 emag;if(!same_signed19(base[ia],base[ib],p,q,epos,emag))throw std::runtime_error("pair alignment");if(!emag)continue;nonzero_second++;
                u128 cr=c3(base[ir]),target;
                if(epos){u128 mx=(u128)-1;if(mx-cr<emag)continue;target=cr+emag;}else{if(cr<=emag)continue;target=cr-emag;}
                u64 r=fcbrt(target);if(c3(r)!=target)continue;third_cubes++;
                std::array<u64,3>bb;base[0]=base[0];bb[ia]=p;bb[ib]=q;bb[ir]=r;
                if(verify19(gs[gi],sign,base,aa,bb,epos,emag,out))hits++;else degenerate++;
            }
        }
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT groups="<<gs.size()<<" max_rep="<<maxrep<<" raw="<<raw<<" unique="<<unique<<" duplicate="<<dups
       <<" qoverflow="<<qoverflow<<" pair_reps="<<pair_reps<<" nonzero_second="<<nonzero_second
       <<" third_cubes="<<third_cubes<<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    std::cerr<<"STAT groups="<<gs.size()<<" max_rep="<<maxrep<<" raw="<<raw<<" unique="<<unique<<" duplicate="<<dups
             <<" qoverflow="<<qoverflow<<" pair_reps="<<pair_reps<<" nonzero_second="<<nonzero_second
             <<" third_cubes="<<third_cubes<<" degenerate="<<degenerate<<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
