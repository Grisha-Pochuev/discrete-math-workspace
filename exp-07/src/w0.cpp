#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <numeric>
#include <string>
#include <unordered_map>
#include <vector>
#include <cmath>

using u64 = std::uint64_t;
using u128 = unsigned __int128;

struct Ratio { u64 n,d; bool operator==(Ratio const&o) const{return n==o.n&&d==o.d;} };
struct RH { size_t operator()(Ratio const&r) const noexcept { auto mix=[](u64 x){x+=0x9e3779b97f4a7c15ULL;x=(x^(x>>30))*0xbf58476d1ce4e5b9ULL;x=(x^(x>>27))*0x94d049bb133111ebULL;return x^(x>>31);}; return (size_t)(mix(r.n)^(mix(r.d)<<1)); }};

u128 gcd128(u128 a,u128 b){while(b){u128 r=a%b;a=b;b=r;}return a;}
Ratio reduce64(u64 a,u64 b){u64 g=std::gcd(a,b);return {a/g,b/g};}
bool divide_ratio(Ratio x, Ratio y, Ratio &out){
    u128 n=(u128)x.n*y.d, d=(u128)x.d*y.n;
    u128 g=gcd128(n,d); n/=g; d/=g;
    if(n>UINT64_MAX || d>UINT64_MAX) return false;
    out={(u64)n,(u64)d}; return true;
}

struct Param {
    u64 a,b;
    Ratio r[2];
    long double f[2];
};

int main(int argc,char**argv){
    if(argc!=9){std::cerr<<"usage: worker type shard shards limit seconds out summary near_tol\n";return 2;}
    int type=std::stoi(argv[1]), shard=std::stoi(argv[2]), shards=std::stoi(argv[3]);
    int limit=std::stoi(argv[4]), seconds=std::stoi(argv[5]);
    std::string outp=argv[6], sump=argv[7]; long double tol=std::stold(argv[8]);
    static const int TYPES[6][3]={{0,0,1},{0,1,0},{0,1,1},{1,0,0},{1,0,1},{1,1,0}};
    if(type<0||type>=6||shard<0||shard>=shards||limit<2) return 2;
    std::vector<Param> ps; ps.reserve((size_t)limit*limit/8);
    for(u64 b=2;b<=(u64)limit;++b){
        for(u64 a=1;2*a<b;++a){
            if(std::gcd(a,b)!=1) continue;
            u64 b2=b*b, a2=a*a;
            u64 P=b2-a*b+3*a2, Q=b2+a*b+3*a2;
            u64 b3=b2*b, a3=a2*a;
            __int128 Cs=(__int128)b3-2*(__int128)a*b2-3*(__int128)a3;
            if(Cs<=0) continue;
            u64 C=(u64)Cs, D=b3+2*a*b2+3*a3;
            long double u=(long double)a/(long double)b;
            long double p=1-u+3*u*u, q=1+u+3*u*u;
            long double c=1-2*u-3*u*u*u, d=1+2*u+3*u*u*u;
            Param z; z.a=a;z.b=b; z.r[0]=reduce64(P,Q); z.r[1]=reduce64(C,D);
            z.f[0]=(d*d*d-c*c*c)/(q*q*q);
            z.f[1]=(q*q*q-p*p*p)/(d*d*d);
            ps.push_back(z);
        }
    }
    std::unordered_map<Ratio,std::vector<uint32_t>,RH> mp[2];
    mp[0].reserve(ps.size()*2); mp[1].reserve(ps.size()*2);
    for(uint32_t i=0;i<ps.size();++i){mp[0][ps[i].r[0]].push_back(i);mp[1][ps[i].r[1]].push_back(i);}
    int ta=TYPES[type][0], tb=TYPES[type][1], tc=TYPES[type][2];
    std::ofstream out(outp); if(!out){std::cerr<<"open output failed\n";return 3;}
    out<<"ua\tub\tva\tvb\twa\twb\trelgap\n";
    auto start=std::chrono::steady_clock::now();
    uint64_t processed=0, pair_tests=0, ratio_hits=0, near_hits=0; long long last_index=-1;
    bool timed=false;
    for(size_t ui=shard;ui<ps.size();ui+=shards){
        auto now=std::chrono::steady_clock::now();
        if(std::chrono::duration_cast<std::chrono::seconds>(now-start).count()>=seconds){timed=true;break;}
        const auto &pu=ps[ui];
        for(size_t wi=0;wi<ps.size();++wi){
            ++pair_tests;
            Ratio rv;
            if(!divide_ratio(ps[wi].r[tc],pu.r[ta],rv)) continue;
            auto it=mp[tb].find(rv); if(it==mp[tb].end()) continue;
            for(uint32_t vi:it->second){
                ++ratio_hits;
                long double dab=std::pow((long double)ps[vi].r[tb].n/(long double)ps[vi].r[tb].d,3)*pu.f[ta];
                long double dbc=ps[vi].f[tb], dac=ps[wi].f[tc];
                long double x[3]={dab,dbc,dac}; std::sort(x,x+3);
                long double den=x[0]+x[1]+x[2];
                long double gap= den>0 ? fabsl(x[2]-x[1]-x[0])/den : 1;
                if(gap<=tol){
                    ++near_hits;
                    out<<pu.a<<'\t'<<pu.b<<'\t'<<ps[vi].a<<'\t'<<ps[vi].b<<'\t'<<ps[wi].a<<'\t'<<ps[wi].b<<'\t'<<(double)gap<<'\n';
                }
            }
        }
        ++processed; last_index=(long long)ui;
    }
    out.flush();
    auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-start).count();
    std::ofstream s(sump);
    s<<"{\n"
     <<"  \"type\": "<<type<<",\n  \"shard\": "<<shard<<",\n  \"shards\": "<<shards<<",\n"
     <<"  \"limit\": "<<limit<<",\n  \"parameter_count\": "<<ps.size()<<",\n"
     <<"  \"processed_assigned_u\": "<<processed<<",\n  \"last_u_index\": "<<last_index<<",\n"
     <<"  \"pair_tests\": "<<pair_tests<<",\n  \"ratio_hits\": "<<ratio_hits<<",\n  \"near_hits\": "<<near_hits<<",\n"
     <<"  \"timed_out_cleanly\": "<<(timed?"true":"false")<<",\n  \"elapsed_ms\": "<<elapsed<<"\n}\n";
    return 0;
}
