// r61: exact modular certificate search on the lambda=9 elliptic orbit.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <numeric>
#include <set>
#include <string>
#include <tuple>
#include <vector>

using u64 = std::uint64_t;
using u128 = __uint128_t;

struct Point { u64 x=0,y=0; bool inf=true; };
static u64 modpow(u64 a,u64 e,u64 p){ u64 r=1; while(e){ if(e&1) r=(u128)r*a%p; a=(u128)a*a%p; e>>=1; } return r; }
static u64 inv(u64 a,u64 p){ return modpow(a,p-2,p); }
static Point add(Point P, Point Q, u64 p){
    if(P.inf) return Q; if(Q.inf) return P;
    if(P.x==Q.x && (P.y+Q.y)%p==0) return {};
    u64 m;
    if(P.x==Q.x && P.y==Q.y){
        if(P.y==0) return {};
        m=(u128)(3*(u128)P.x%p)*P.x%p * inv((2*P.y)%p,p)%p;
    }else{
        u64 num=(Q.y+p-P.y)%p, den=(Q.x+p-P.x)%p;
        m=(u128)num*inv(den,p)%p;
    }
    u64 x3=((u128)m*m + 2*p - P.x - Q.x)%p;
    u64 y3=((u128)m*((P.x+p-x3)%p) + p - P.y)%p;
    return {x3,y3,false};
}
struct Filter {u64 p,ord; std::vector<unsigned char> ok; double ratio;};
static bool prime(u64 n){ if(n<2)return false; if(n%2==0)return n==2; for(u64 d=3;d*d<=n;d+=2) if(n%d==0)return false; return true; }
static Filter make_filter(u64 p){
    Point G{4%p,(p-4%p)%p,false}, P{};
    u64 bound=p+1+2*(u64)std::sqrt((long double)p)+20, ord=0;
    std::vector<Point> pts; pts.reserve(bound+1); pts.push_back(P);
    for(u64 n=1;n<=bound;n++){ P=add(P,G,p); if(P.inf){ord=n;break;} pts.push_back(P); }
    if(!ord){ std::cerr<<"no order p="<<p<<"\n"; std::exit(3); }
    std::vector<unsigned char> ok(ord,0); ok[0]=1; u64 inv7=inv(7%p,p), cnt=1;
    for(u64 n=1;n<ord;n++){
        auto R=pts[n]; u64 y=R.y;
        u64 a=(y+p-4%p)%p;
        u64 yy=(u128)y*y%p;
        u64 b=(yy + p - (24%p)*y%p + 336%p)%p;
        u64 val=(u128)((p-a)%p)*b%p*inv7%p;
        bool good=(val==0 || modpow(val,(p-1)/3,p)==1);
        ok[n]=good; cnt+=good;
    }
    return {p,ord,std::move(ok),(double)cnt/(double)ord};
}
static u64 gcd64(u64 a,u64 b){while(b){u64 t=a%b;a=b;b=t;}return a;}
static u64 lcm64(u64 a,u64 b){return a/gcd64(a,b)*b;}
static std::pair<u64,std::vector<u64>> extend(u64 L,const std::vector<u64>& res,const Filter& f){
    u64 L2=lcm64(L,f.ord), mult=L2/L; std::vector<u64> out;
    for(u64 r:res) for(u64 k=0,x=r;k<mult;k++,x+=L) if(f.ok[x%f.ord]) out.push_back(x);
    std::sort(out.begin(),out.end()); out.erase(std::unique(out.begin(),out.end()),out.end()); return {L2,std::move(out)};
}
static u64 signed_mod(bool neg,u64 n,u64 m){u64 r=n%m; return neg && r ? m-r:r;}

int main(int argc,char**argv){
    if(argc<7){std::cerr<<"usage: r61 N id parts pmax maxfilters seconds\n";return 2;}
    u64 N=std::strtoull(argv[1],nullptr,10), id=std::strtoull(argv[2],nullptr,10), parts=std::strtoull(argv[3],nullptr,10);
    u64 pmax=std::strtoull(argv[4],nullptr,10), maxfilters=std::strtoull(argv[5],nullptr,10), seconds=std::strtoull(argv[6],nullptr,10);
    if(!N||id>=parts||parts==0||pmax<100||seconds<1)return 2;
    std::set<u64> wheelp={367,1531,3943,163,1429,991,4027,151,271,1291,1741};
    std::vector<Filter> wheel;
    for(u64 p:wheelp) wheel.push_back(make_filter(p));
    std::vector<u64> order={367,1531,3943,163,1429,991,4027,151,271,1291,1741};
    u64 W=1; std::vector<u64> R{0};
    for(u64 p:order){ auto it=std::find_if(wheel.begin(),wheel.end(),[&](auto const& f){return f.p==p;}); auto z=extend(W,R,*it); W=z.first; R=std::move(z.second); }
    const std::vector<u64> want={0,1,822511,16943705};
    if(W!=16943706 || R!=want){ std::cerr<<"wheel replay mismatch W="<<W<<" size="<<R.size()<<"\n"; return 4; }

    std::vector<Filter> fs;
    for(u64 p=5;p<=pmax;p+=2) if(p%3==1 && p!=7 && prime(p) && !wheelp.count(p)) fs.push_back(make_filter(p));
    std::sort(fs.begin(),fs.end(),[](auto const&a,auto const&b){ if(a.ratio!=b.ratio)return a.ratio<b.ratio; return a.ord<b.ord; });
    if(fs.size()>maxfilters) fs.resize(maxfilters);
    if(fs.empty()) return 5;
    std::vector<u64> reject(fs.size(),0);
    u64 assigned=0, done=0, survivors=0; bool partial=false;
    auto start=std::chrono::steady_clock::now();
    auto elapsed=[&](){return std::chrono::duration_cast<std::chrono::seconds>(std::chrono::steady_clock::now()-start).count();};
    auto test=[&](u64 n,bool neg){
        for(size_t j=0;j<fs.size();j++){
            auto &f=fs[j]; u64 rr=signed_mod(neg,n,f.ord);
            if(!f.ok[rr]){reject[j]++; return false;}
        }
        survivors++; std::cout<<"SURV n="<<(neg?"-":"")<<n<<"\n"; return true;
    };
    for(u64 r:R){
        u64 k0=0; if(r<2) k0=(2-r+W-1)/W;
        if(r>N) continue;
        u64 kmax=(N-r)/W;
        if(k0>kmax) continue;
        u64 rem=k0%parts; if(rem!=id) k0 += (id+parts-rem)%parts;
        for(u64 k=k0;k<=kmax;){
            u64 n=r+k*W;
            assigned+=2; test(n,false); test(n,true); done+=2;
            if((done & ((1u<<20)-1))==0 && elapsed()>=(long long)seconds){partial=true;break;}
            if(kmax-k<parts) break; k+=parts;
        }
        if(partial) break;
    }
    std::cout<<"STAT N="<<N<<" part="<<id<<" parts="<<parts<<" pmax="<<pmax<<" filters="<<fs.size()
             <<" wheel="<<W<<" wheel_res="<<R.size()<<" assigned="<<assigned<<" done="<<done
             <<" survivors="<<survivors<<" partial="<<(partial?1:0)<<" seconds="<<elapsed()<<"\n";
    std::cout<<"FILTERS"; for(size_t j=0;j<std::min<size_t>(fs.size(),20);j++) std::cout<<" p"<<fs[j].p<<"="<<reject[j]; std::cout<<"\n";
    if(partial) return 124; return survivors?10:0;
}
