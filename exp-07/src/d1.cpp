// d1-r2
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <map>
#include <random>
#include <set>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

using u64 = std::uint64_t;
using u128 = __uint128_t;

static inline u128 c3(u64 x) { return (u128)x*x*x; }
static std::string s128(u128 v){if(!v)return "0";std::string s;while(v){s.push_back(char('0'+v%10));v/=10;}std::reverse(s.begin(),s.end());return s;}
static u64 fcbrt(u128 n){u64 x=(u64)std::cbrt((long double)n);while(c3(x)>n)--x;while(c3(x+1)<=n)++x;return x;}
static u64 ccbrt(u128 n){u64 x=fcbrt(n);return c3(x)==n?x:x+1;}

static u64 mm(u64 a,u64 b,u64 m){return (u128)a*b%m;}
static u64 mp(u64 a,u64 d,u64 m){u64 r=1;for(;d;d>>=1,a=mm(a,a,m))if(d&1)r=mm(r,a,m);return r;}
static bool isp(u64 n){if(n<2)return false;for(u64 p:{2ULL,3ULL,5ULL,7ULL,11ULL,13ULL,17ULL,19ULL,23ULL,29ULL,31ULL,37ULL})if(n%p==0)return n==p;u64 d=n-1,s=0;while(!(d&1))d>>=1,++s;for(u64 a:{2ULL,325ULL,9375ULL,28178ULL,450775ULL,9780504ULL,1795265022ULL}){if(a%n==0)continue;u64 x=mp(a%n,d,n);if(x==1||x==n-1)continue;bool ok=false;for(u64 r=1;r<s;r++){x=mm(x,x,n);if(x==n-1){ok=true;break;}}if(!ok)return false;}return true;}
static std::mt19937_64 rng(0x8f3d9a71b5c2e647ULL);
static u64 gcd64(u64 a,u64 b){while(b){u64 t=a%b;a=b;b=t;}return a;}
static u64 rho(u64 n){if(!(n&1))return 2;if(n%3==0)return 3;for(;;){u64 c=rng()%(n-1)+1,x=rng()%(n-2)+2,y=x,d=1;auto f=[&](u64 z){return(mm(z,z,n)+c)%n;};while(d==1){x=f(x);y=f(f(y));d=gcd64(x>y?x-y:y-x,n);}if(d!=n)return d;}}
static void factor(u64 n,std::map<u64,int>& f){if(n==1)return;if(isp(n)){++f[n];return;}u64 d=rho(n);factor(d,f);factor(n/d,f);}
static void divisors_rec(const std::vector<std::pair<u64,int>>& f,int i,u64 v,std::vector<u64>& out){if(i==(int)f.size()){out.push_back(v);return;}u64 q=1;for(int e=0;e<=f[i].second;e++){divisors_rec(f,i+1,v*q,out);if(e<f[i].second)q*=f[i].first;}}
static u64 isqrt64(u64 n){u64 x=(u64)std::sqrt((long double)n);while((u128)(x+1)*(x+1)<=n)++x;while((u128)x*x>n)--x;return x;}
static std::vector<std::pair<u64,u64>> reps(u64 D){std::map<u64,int> fm;factor(D,fm);std::vector<std::pair<u64,int>> fs(fm.begin(),fm.end());std::vector<u64> ds;divisors_rec(fs,0,1,ds);std::vector<std::pair<u64,u64>> r;for(u64 d:ds){u64 M=D/d;u128 A=(u128)12*M,B=(u128)3*d*d;if(A<=B||A-B>UINT64_MAX)continue;u64 q=(u64)(A-B),s=isqrt64(q);if((u128)s*s!=q||s<=3*d||(s-3*d)%6)continue;u64 x=(s-3*d)/6,y=x+d;if(x&&c3(y)-c3(x)==D)r.push_back({x,y});}std::sort(r.begin(),r.end());r.erase(std::unique(r.begin(),r.end()),r.end());return r;}

struct Rec{u64 d;std::uint32_t x,y;bool operator<(const Rec&o)const{return d<o.d||(d==o.d&&(x<o.x||(x==o.x&&y<o.y)));}};
static u64 isqrt128(u128 n){u64 x=(u64)std::sqrt((long double)n);while((u128)(x+1)*(x+1)<=n)++x;while((u128)x*x>n)--x;return x;}
static void merge_factor(u64 n,std::map<u64,int>& fm){std::map<u64,int> t;factor(n,t);for(auto [p,e]:t)fm[p]+=e;}
static void divisors128_rec(const std::vector<std::pair<u64,int>>& f,int i,u128 v,u64 lim,std::vector<u64>& out){
  if(v>lim)return;
  if(i==(int)f.size()){out.push_back((u64)v);return;}
  u128 q=1;
  for(int e=0;e<=f[i].second;e++){
    if(v*q>lim)break;
    divisors128_rec(f,i+1,v*q,lim,out);
    q*=f[i].first;
  }
}
static std::vector<std::pair<u64,u64>> reps_from_known(u64 a,u64 b){
  u64 delta=b-a;
  u128 K=c3(b)-c3(a);
  u128 Qu=K/delta;
  if(Qu>UINT64_MAX){std::cerr<<"Q overflow\n";std::abort();}
  std::map<u64,int> fm;merge_factor(delta,fm);merge_factor((u64)Qu,fm);
  std::vector<std::pair<u64,int>> fs(fm.begin(),fm.end());
  u64 lim=fcbrt(K-1);std::vector<u64> ds;divisors128_rec(fs,0,1,lim,ds);
  std::vector<std::pair<u64,u64>> r;
  for(u64 d:ds){
    u128 M=K/d,A=12*M,B=(u128)3*d*d;if(A<=B)continue;u128 disc=A-B;u64 ss=isqrt128(disc);
    if((u128)ss*ss!=disc||ss<=3*d||(ss-3*d)%6)continue;
    u64 x=(ss-3*d)/6,y=x+d;if(x&&c3(y)-c3(x)==K)r.push_back({x,y});
  }
  std::sort(r.begin(),r.end());r.erase(std::unique(r.begin(),r.end()),r.end());return r;
}

static bool test_group(const std::vector<Rec>& v,size_t lo,size_t hi,std::ostream& out){
  const int m=(int)(hi-lo); if(m<3)return false;
  for(int i=0;i<m;i++)for(int j=i+1;j<m;j++)for(int k=j+1;k<m;k++){
    u64 a=v[lo+i].x,b=v[lo+j].x,c=v[lo+k].x;
    u64 au=v[lo+i].y,bu=v[lo+j].y,cu=v[lo+k].y;
    std::array<std::pair<u64,u64>,3> q={{{a,au},{b,bu},{c,cu}}};
    std::sort(q.begin(),q.end()); a=q[0].first;au=q[0].second;b=q[1].first;bu=q[1].second;c=q[2].first;cu=q[2].second;
    u128 K128=c3(b)-c3(a);
    auto rk=reps_from_known(a,b);
    for(auto [u,w2]:rk){
      if(u<=a)continue; u128 E=c3(u)-c3(a); if(E==(u128)v[lo].d)continue;
      u128 t=c3(c)+E;u64 w=fcbrt(t);if(c3(w)!=t)continue;
      if(c3(w2)-c3(b)!=E)continue;
      std::array<u64,9> z={a,b,c,au,bu,cu,u,w2,w};std::set<u64> ss(z.begin(),z.end());if(ss.size()!=9)continue;
      out<<"HIT\n"<<"d0 "<<v[lo].d<<"\nd1 "<<s128(E)<<"\n";
      out<<"r0 "<<a<<" "<<b<<" "<<c<<"\n";
      out<<"r1 "<<au<<" "<<bu<<" "<<cu<<"\n";
      out<<"r2 "<<u<<" "<<w2<<" "<<w<<"\n";
      return true;
    }
  }
  return false;
}

int main(int argc,char**argv){
  if(argc<4){std::cerr<<"usage: d1 LO HI OUT\n";return 2;}u64 L=std::stoull(argv[1]),R=std::stoull(argv[2]);std::ofstream out(argv[3]);
  auto t0=std::chrono::steady_clock::now();u64 ymax=(u64)std::sqrt((long double)R/3.0L)+16;while(ymax>1&&c3(ymax)-c3(ymax-1)>R)--ymax;while(c3(ymax+1)-c3(ymax)<=R)++ymax;
  std::vector<Rec> v; long double est=0;
  for(u64 y=2;y<=ymax;y++){
    u128 Y=c3(y);u64 xmin=1,xmax=y-1;
    if(Y>R)xmin=std::max<u64>(xmin,ccbrt(Y-R));
    if(Y<L)continue;u128 top=Y-L;xmax=std::min<u64>(xmax,fcbrt(top));
    if(xmin<=xmax)est+=(long double)(xmax-xmin+1);
  }
  if(est>0&&est<1.5e9L)v.reserve((size_t)est);
  for(u64 y=2;y<=ymax;y++){
    u128 Y=c3(y);u64 xmin=1,xmax=y-1;
    if(Y>R)xmin=std::max<u64>(xmin,ccbrt(Y-R));
    if(Y<L)continue;u128 top=Y-L;xmax=std::min<u64>(xmax,fcbrt(top));
    for(u64 x=xmin;x<=xmax;x++){u128 dd=Y-c3(x);if(dd<L||dd>R)continue;v.push_back({(u64)dd,(uint32_t)x,(uint32_t)y});}
  }
  std::sort(v.begin(),v.end());
  size_t groups=0, triples=0,maxm=0;bool hit=false;
  for(size_t i=0;i<v.size();){size_t j=i+1;while(j<v.size()&&v[j].d==v[i].d)++j;size_t m=j-i;if(m>=3){++groups;maxm=std::max(maxm,m);triples+=m*(m-1)*(m-2)/6;if(test_group(v,i,j,out)){hit=true;break;}}i=j;}
  double sec=std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count();
  out<<"STAT lo="<<L<<" hi="<<R<<" rec="<<v.size()<<" groups="<<groups<<" triples="<<triples<<" max="<<maxm<<" sec="<<sec<<" hit="<<hit<<"\n";
  std::cerr<<"rec="<<v.size()<<" groups="<<groups<<" sec="<<sec<<" hit="<<hit<<"\n";
  return hit?10:0;
}
