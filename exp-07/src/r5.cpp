#include <gmpxx.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <numeric>
#include <sstream>
#include <string>
#include <unordered_map>
#include <vector>

using namespace std;
using u32 = uint32_t;
using u64 = uint64_t;

static constexpr u32 PM1 = 1000000007u;
static constexpr u32 PM2 = 1000000009u;

struct PairRec { u64 s; u32 x,y; bool operator<(PairRec const&o)const{return s<o.s;} };
struct Group { u64 s; vector<pair<u32,u32>> reps; };
struct Tri { u32 a,b,c; int gab,gbc,gac; };
struct Pt { mpq_class x,y; bool inf=false; };
struct Alt { mpq_class d; int i,j; u32 seed_lo,seed_hi; u32 h1,h2; bool modok; };

static u64 ekey(u32 a,u32 b){ if(a>b) swap(a,b); return (u64(a)<<32)|b; }
static mpq_class Q(long long a,long long b=1){ mpq_class q(mpz_class((long)a),mpz_class((long)b)); q.canonicalize(); return q; }

Pt neg(Pt p){ if(!p.inf)p.y=-p.y; return p; }
Pt add(const Pt&A,const Pt&B){
    if(A.inf)return B; if(B.inf)return A;
    if(A.x==B.x && A.y==-B.y)return Pt{{},{},true};
    mpq_class s;
    if(A.x==B.x && A.y==B.y){ if(A.y==0)return Pt{{},{},true}; s=3*A.x*A.x/(2*A.y); }
    else s=(B.y-A.y)/(B.x-A.x);
    Pt R; R.x=s*s-A.x-B.x; R.y=s*(A.x-R.x)-A.y; return R;
}
Pt mul(Pt P,int n){ if(n<0){P=neg(P);n=-n;} Pt R{{},{},true}; while(n){if(n&1)R=add(R,P);P=add(P,P);n>>=1;}return R; }

u32 modpow(u64 a,u64 e,u32 p){u64 r=1;while(e){if(e&1)r=r*a%p;a=a*a%p;e>>=1;}return (u32)r;}
bool qmod(const mpq_class&q,u32 p,u32&out){u32 n=mpz_fdiv_ui(q.get_num_mpz_t(),p),d=mpz_fdiv_ui(q.get_den_mpz_t(),p);if(!d)return false;out=(u64)n*modpow(d,p-2,p)%p;return true;}

struct CurveEdge {
    u32 lo,hi; mpq_class M,a,K,B; Pt T;
    CurveEdge(u32 l,u32 h):lo(l),hi(h){
        M=Q((long long)l+h,2); a=Q((long long)h-l,(long long)h+l); K=1+3*a*a; B=-27*K*K; T={3*K,9*K*a,false};
        if(T.y*T.y!=T.x*T.x*T.x+B){ cerr<<"bad T edge "<<l<<","<<h<<" a="<<a<<" K="<<K<<" lhs="<<T.y*T.y<<" rhs="<<T.x*T.x*T.x+B<<"\n"; throw runtime_error("bad T"); }
    }
    Pt seed_point(u32 zl,u32 zh)const{
        mpq_class N=Q((long long)zl+zh,2),m=N/M,b=Q((long long)zh-zl,(long long)zh+zl);
        Pt P{3*K/m,9*K*b,false};
        if(P.y*P.y!=P.x*P.x*P.x+B) throw runtime_error("bad P");
        return P;
    }
    pair<mpq_class,mpq_class> pair_from(const Pt&Z)const{
        mpq_class m=3*K/Z.x,b=Z.y/(9*K); mpq_class z1=m*M*(1-b),z2=m*M*(1+b); if(z1>z2)swap(z1,z2); return {z1,z2};
    }
    vector<Alt> gen(int R,const Group&g,u64&bad)const{
        bad=0; vector<Alt> out; out.reserve((size_t)(2*R+1)*(2*R+1)*max<size_t>(1,g.reps.size()-1)/6);
        vector<Pt> mt(2*R+1); for(int i=-R;i<=R;i++)mt[i+R]=mul(T,i);
        mpq_class topd=Q((long long)hi*hi*hi-(long long)lo*lo*lo),M3=M*M*M,K2=K*K;
        for(auto [zl,zh]:g.reps){
            if(zl==lo && zh==hi) continue;
            Pt P=seed_point(zl,zh); vector<Pt> mp(2*R+1); for(int j=-R;j<=R;j++)mp[j+R]=mul(P,j);
            for(int i=-R;i<=R;i++)for(int j=-R;j<=R;j++){
                if(i<0 || (i==0 && j<=0)) continue;
                Pt Z=add(mt[i+R],mp[j+R]); if(Z.inf||Z.x<=0)continue;
                mpq_class ay=Z.y; if(ay<0)ay=-ay; if(ay>=9*K)continue;
                mpq_class X3=Z.x*Z.x*Z.x;
                mpq_class d=2*M3*Z.y*(X3+216*K2)/(27*X3); if(d<0)d=-d; if(d==topd)continue;
                u32 h1=0,h2=0; bool ok=qmod(d,PM1,h1)&&qmod(d,PM2,h2); if(!ok)bad++;
                out.push_back({d,i,j,zl,zh,h1,h2,ok});
            }
        }
        return out;
    }
    Pt point_from(const Alt&r)const{ return add(mul(T,r.i),mul(seed_point(r.seed_lo,r.seed_hi),r.j)); }
};

struct K2 { u32 a,b; bool operator==(K2 const&o)const{return a==o.a&&b==o.b;} };
struct K2H { size_t operator()(K2 const&k)const{return (u64(k.a)<<32)^k.b;} };
struct Stats { u64 pairs=0,modcand=0,exactcand=0; };

bool equal_sum_mod(const vector<Alt>&A,const vector<Alt>&B,const vector<Alt>&C,
                   const Alt*&ha,const Alt*&hb,const Alt*&hc,Stats&st){
    bool allmod=true; for(auto&r:A)allmod&=r.modok;for(auto&r:B)allmod&=r.modok;for(auto&r:C)allmod&=r.modok;
    if(allmod){
        unordered_multimap<K2,int,K2H> idx; idx.reserve(C.size()*2+1); for(int k=0;k<(int)C.size();k++)idx.emplace(K2{C[k].h1,C[k].h2},k);
        for(auto const&a:A)for(auto const&b:B){st.pairs++;K2 key{(u32)(((u64)a.h1+b.h1)%PM1),(u32)(((u64)a.h2+b.h2)%PM2)};auto [it,en]=idx.equal_range(key);for(;it!=en;++it){st.modcand++;auto const&c=C[it->second];if(a.d+b.d==c.d){st.exactcand++;ha=&a;hb=&b;hc=&c;return true;}}}
        return false;
    }
    map<mpq_class,int> idx; for(int k=0;k<(int)C.size();k++)idx.emplace(C[k].d,k);
    for(auto const&a:A)for(auto const&b:B){st.pairs++;auto it=idx.find(a.d+b.d);if(it!=idx.end()){st.exactcand++;ha=&a;hb=&b;hc=&C[it->second];return true;}}
    return false;
}

mpz_class lcmz(const mpz_class&a,const mpz_class&b){mpz_class g;mpz_gcd(g.get_mpz_t(),a.get_mpz_t(),b.get_mpz_t());return a/g*b;}

bool verify_hit(const Tri&t,const CurveEdge&eAB,const CurveEdge&eBC,const CurveEdge&eAC,
                const Alt&rAB,const Alt&rBC,const Alt&rAC,int largest,string&solution){
    auto pAB=eAB.pair_from(eAB.point_from(rAB));
    auto pBC=eBC.pair_from(eBC.point_from(rBC));
    auto pAC=eAC.pair_from(eAC.point_from(rAC));
    if(pAB.first<=0||pBC.first<=0||pAC.first<=0)return false;
    if(pAB.first*pAB.first*pAB.first+pAB.second*pAB.second*pAB.second!=Q((long long)t.a*t.a*t.a+(long long)t.b*t.b*t.b))return false;
    if(pBC.first*pBC.first*pBC.first+pBC.second*pBC.second*pBC.second!=Q((long long)t.b*t.b*t.b+(long long)t.c*t.c*t.c))return false;
    if(pAC.first*pAC.first*pAC.first+pAC.second*pAC.second*pAC.second!=Q((long long)t.a*t.a*t.a+(long long)t.c*t.c*t.c))return false;
    int sBC=largest==0?1:-1, sAC=largest==1?1:-1, sAB=largest==2?1:-1;
    auto orient=[](pair<mpq_class,mpq_class> p,int s){return s>0?make_pair(p.second,p.first):p;};
    auto BC=orient(pBC,sBC), AC=orient(pAC,sAC), AB=orient(pAB,sAB);
    vector<mpq_class> q={Q(t.a),Q(t.b),Q(t.c),BC.first,AC.first,AB.first,BC.second,AC.second,AB.second};
    for(auto&x:q)if(x<=0)return false;
    for(int i=0;i<9;i++)for(int j=i+1;j<9;j++)if(q[i]==q[j])return false;
    mpz_class L=1;for(auto&x:q)L=lcmz(L,x.get_den());vector<mpz_class> z;z.reserve(9);for(auto&x:q)z.push_back(x.get_num()*(L/x.get_den()));mpz_class G=0;for(auto&x:z){mpz_class ax=abs(x),g;mpz_gcd(g.get_mpz_t(),G.get_mpz_t(),ax.get_mpz_t());G=g;}if(G>1)for(auto&x:z)x/=G;
    auto cube=[](mpz_class x){return x*x*x;}; vector<mpz_class> c(9);for(int i=0;i<9;i++)c[i]=cube(z[i]);vector<mpz_class>sums={c[0]+c[1]+c[2],c[3]+c[4]+c[5],c[6]+c[7]+c[8],c[0]+c[3]+c[6],c[1]+c[4]+c[7],c[2]+c[5]+c[8]};for(int i=1;i<6;i++)if(sums[i]!=sums[0])return false;
    ostringstream o;o<<"top="<<t.a<<","<<t.b<<","<<t.c<<" largest="<<largest<<" bases=";for(int i=0;i<9;i++){if(i)o<<',';o<<z[i].get_str();}o<<" S="<<sums[0].get_str()<<"\n";solution=o.str();return true;
}

int main(int argc,char**argv){
    if(argc!=8){cerr<<"usage: r5 N R part parts soft_seconds out progress\n";return 2;}
    int N=stoi(argv[1]),R=stoi(argv[2]),part=stoi(argv[3]),parts=stoi(argv[4]),soft=stoi(argv[5]);string outp=argv[6],prog=argv[7];
    if(N<3||R<1||part<0||part>=parts||soft<1)return 2;
    auto start=chrono::steady_clock::now();
    vector<u64> cubes(N+1);for(int i=1;i<=N;i++)cubes[i]=(u64)i*i*i;
    vector<PairRec> all;all.reserve((u64)N*(N-1)/2);for(u32 y=2;y<=(u32)N;y++)for(u32 x=1;x<y;x++)all.push_back({cubes[x]+cubes[y],x,y});sort(all.begin(),all.end());
    unordered_map<u64,int> edgeg;edgeg.reserve(all.size()/100);vector<Group> gs;
    for(size_t i=0;i<all.size();){size_t j=i+1;while(j<all.size()&&all[j].s==all[i].s)j++;if(j-i>=2){int id=gs.size();Group g;g.s=all[i].s;for(size_t k=i;k<j;k++){g.reps.push_back({all[k].x,all[k].y});edgeg[ekey(all[k].x,all[k].y)]=id;}gs.push_back(move(g));}i=j;}
    all.clear();all.shrink_to_fit();
    vector<vector<u32>> adj(N+1);for(auto const&kv:edgeg){u32 x=kv.first>>32,y=(u32)kv.first;adj[x].push_back(y);adj[y].push_back(x);}for(auto&a:adj)sort(a.begin(),a.end());
    vector<Tri> tris;for(u32 a=1;a<=(u32)N;a++)for(u32 b:adj[a])if(b>a){auto const&A=adj[a];auto const&B=adj[b];size_t i=0,j=0;while(i<A.size()&&j<B.size()){if(A[i]==B[j]){u32 c=A[i];if(c>b)tris.push_back({a,b,c,edgeg[ekey(a,b)],edgeg[ekey(b,c)],edgeg[ekey(a,c)]});i++;j++;}else if(A[i]<B[j])i++;else j++;}}
    ofstream out(outp);ofstream pf(prog);if(!out||!pf)return 3;out<<"status\ttri\tdetail\n";
    u64 assigned=0,done=0,totalpairs=0,totalmod=0,totalexact=0,totalbad=0,totalalts=0;bool partial=false;
    for(size_t ti=part;ti<tris.size();ti+=parts){assigned++;if(chrono::duration_cast<chrono::seconds>(chrono::steady_clock::now()-start).count()>=soft){partial=true;break;}auto const&t=tris[ti];
        CurveEdge eAB(t.a,t.b),eBC(t.b,t.c),eAC(t.a,t.c);u64 b1,b2,b3;auto AB=eAB.gen(R,gs[t.gab],b1),BC=eBC.gen(R,gs[t.gbc],b2),AC=eAC.gen(R,gs[t.gac],b3);totalbad+=b1+b2+b3;totalalts+=AB.size()+BC.size()+AC.size();Stats st;const Alt *x,*y,*z;
        if(equal_sum_mod(AC,AB,BC,x,y,z,st)){string sol;if(verify_hit(t,eAB,eBC,eAC,*y,*z,*x,0,sol)){out<<"HIT\t"<<ti<<'\t'<<sol;out.flush();return 10;}}
        if(equal_sum_mod(BC,AB,AC,x,y,z,st)){string sol;if(verify_hit(t,eAB,eBC,eAC,*y,*x,*z,1,sol)){out<<"HIT\t"<<ti<<'\t'<<sol;out.flush();return 10;}}
        if(equal_sum_mod(BC,AC,AB,x,y,z,st)){string sol;if(verify_hit(t,eAB,eBC,eAC,*z,*x,*y,2,sol)){out<<"HIT\t"<<ti<<'\t'<<sol;out.flush();return 10;}}
        totalpairs+=st.pairs;totalmod+=st.modcand;totalexact+=st.exactcand;done++;
        if(done%10==0){pf<<"done="<<done<<" tri="<<ti<<" pairs="<<totalpairs<<" mod="<<totalmod<<" exact="<<totalexact<<" bad="<<totalbad<<" alts="<<totalalts<<"\n";pf.flush();}
    }
    auto sec=chrono::duration_cast<chrono::seconds>(chrono::steady_clock::now()-start).count();
    out<<"SUMMARY\t-\tN="<<N<<" R="<<R<<" part="<<part<<" parts="<<parts<<" triangles="<<tris.size()<<" assigned_seen="<<assigned<<" done="<<done<<" pairs="<<totalpairs<<" modular_candidates="<<totalmod<<" exact_candidates="<<totalexact<<" bad_mod_den="<<totalbad<<" generated_alts="<<totalalts<<" partial="<<(partial?1:0)<<" sec="<<sec<<"\n";out.flush();
    return partial?124:0;
}
