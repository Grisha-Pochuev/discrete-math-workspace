// r26: exact signed closure over independently reconstructed repeated differences.
#define main d1_old_main
#include "d1.cpp"
#undef main

#include <array>
#include <sstream>
#include <stdexcept>

using i128 = __int128_t;

static std::vector<u64> read26(const std::string& path){
    std::ifstream f(path);if(!f)throw std::runtime_error("open input");
    std::vector<u64>z;std::string line;
    while(std::getline(f,line)){
        if(line.empty()||line[0]=='#')continue;
        std::istringstream is(line);long long n;unsigned long long d;
        if(is>>n>>d)z.push_back((u64)d);
    }
    return z;
}

static u128 c26(u64 x){return c3(x);}

static bool verify26(const std::array<u64,3>& base,
                     const std::array<u64,3>& layer1,
                     const std::array<u64,3>& layer2,
                     std::ostream&out,u64 D,i128 T){
    std::array<u64,9>z={
        base[0],layer2[2],layer1[1],
        layer2[1],layer1[0],base[2],
        layer1[2],base[1],layer2[0]
    };
    std::set<u64>ss(z.begin(),z.end());
    if(ss.size()!=9||*ss.begin()==0)return false;
    std::array<u128,9>q;for(int i=0;i<9;i++)q[i]=c26(z[i]);
    std::array<u128,6>s={
        q[0]+q[1]+q[2],q[3]+q[4]+q[5],q[6]+q[7]+q[8],
        q[0]+q[3]+q[6],q[1]+q[4]+q[7],q[2]+q[5]+q[8]
    };
    for(int i=1;i<6;i++)if(s[i]!=s[0])throw std::runtime_error("r26 six sums");
    out<<"HIT D="<<D<<" signed="<<(T<0?"neg":"pos")<<" bases=";
    for(int i=0;i<9;i++){if(i)out<<',';out<<z[i];}
    out<<" S="<<s128(s[0])<<"\n";
    return true;
}

int main(int argc,char**argv){
    if(argc!=3){std::cerr<<"usage: r26 BFILE OUT\n";return 2;}
    auto t0=std::chrono::steady_clock::now();auto ds=read26(argv[1]);
    if(ds.size()!=10000){std::cerr<<"INPUT_COUNT_FAIL "<<ds.size()<<"\n";return 11;}
    for(u64 D:{424910390480793ULL,15490327057569000ULL,123922616460552000ULL})
        if(std::find(ds.begin(),ds.end(),D)==ds.end())ds.push_back(D);
    std::ofstream out(argv[2]);if(!out)return 3;
    u64 groups=0,triples=0,reps_tested=0,pos=0,neg=0,valid_pos=0,valid_neg=0,hits=0;
    size_t maxrep=0,under3=0;
    for(u64 D:ds){
        auto rp=reps(D);++groups;maxrep=std::max(maxrep,rp.size());
        if(rp.size()<3){under3++;continue;}
        for(size_t i=0;i<rp.size();i++)for(size_t j=i+1;j<rp.size();j++)for(size_t k=j+1;k<rp.size();k++){
            ++triples;
            const u64 a=rp[i].first,b=rp[j].first,c=rp[k].first;
            auto rr=reps_from_known(a,b);
            for(auto [p,q]:rr){
                if(p==a)continue;
                const i128 T=(i128)c26(p)-(i128)c26(a);
                if(T==(i128)D)continue;
                ++reps_tested;if(T>0)++pos;else ++neg;
                if((i128)c26(q)-(i128)c26(b)!=T)throw std::runtime_error("r26 K replay");
                const i128 rcube=(i128)c26(c)+T;
                if(rcube<=0)continue;
                const u64 r=fcbrt((u128)rcube);if(c26(r)!=(u128)rcube)continue;
                if(T>0){
                    ++valid_pos;
                    std::array<u64,3>B={a,b,c},U,V;
                    std::array<u64,3>Dlay={rp[i].second,rp[j].second,rp[k].second};
                    std::array<u64,3>Tlay={p,q,r};
                    if(T<(i128)D){U=Tlay;V=Dlay;}else{U=Dlay;V=Tlay;}
                    if(verify26(B,U,V,out,D,T)){++hits;out.flush();}
                }else{
                    ++valid_neg;
                    // The p,q,r layer is now the minimum layer.  Its positive
                    // offsets are -T and D-T, in that order.
                    std::array<u64,3>B={p,q,r};
                    std::array<u64,3>U={a,b,c};
                    std::array<u64,3>V={rp[i].second,rp[j].second,rp[k].second};
                    if(verify26(B,U,V,out,D,T)){++hits;out.flush();}
                }
            }
        }
    }
    if(under3){std::cerr<<"UNDER3 "<<under3<<"\n";return 12;}
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT groups="<<groups<<" max_rep="<<maxrep<<" triples="<<triples
       <<" reps_tested="<<reps_tested<<" pos="<<pos<<" neg="<<neg
       <<" valid_pos="<<valid_pos<<" valid_neg="<<valid_neg
       <<" hits="<<hits<<" ms="<<ms<<"\n";
    std::cerr<<"STAT groups="<<groups<<" triples="<<triples<<" reps_tested="<<reps_tested
             <<" pos="<<pos<<" neg="<<neg<<" valid_pos="<<valid_pos
             <<" valid_neg="<<valid_neg<<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
