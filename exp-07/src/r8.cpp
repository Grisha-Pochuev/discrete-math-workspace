// r8-r1
#include <gmpxx.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <numeric>
#include <set>
#include <string>
#include <vector>

using u32 = std::uint32_t;
using u64 = std::uint64_t;
using std::array;
using std::vector;

struct Combo { int mab, mbc, sab, sbc; };

static u32 mulp(u32 a, u32 b, u32 p) { return (u64)a*b % p; }
static u32 addp(u32 a, u32 b, u32 p) { u64 s=(u64)a+b; if(s>=p)s-=p; return (u32)s; }
static u32 subp(u32 a, u32 b, u32 p) { return a>=b ? a-b : (u32)((u64)a+p-b); }
static u32 powp(u32 a, u64 e, u32 p) { u32 r=1; for(;e;e>>=1,a=mulp(a,a,p)) if(e&1) r=mulp(r,a,p); return r; }
static bool prime(u32 n) {
    if(n<2) return false;
    if(!(n&1)) return n==2;
    for(u32 d=3;(u64)d*d<=n;d+=2) if(n%d==0) return false;
    return true;
}
static vector<u32> sieve_primes(u32 start, int count) {
    vector<u32> out;
    for(u32 p=std::max<u32>(start|1u,7u); out.size()<(size_t)count; p+=2)
        if(p%3==1 && prime(p)) out.push_back(p);
    return out;
}

struct MP { u32 x=0,y=0; bool inf=true; };

static MP madd(MP A, MP B, u32 p) {
    if(A.inf) return B; if(B.inf) return A;
    if(A.x==B.x) {
        if(addp(A.y,B.y,p)==0) return MP{};
        if(A.y!=B.y) return MP{};
        if(A.y==0) return MP{};
        u32 den=mulp(2,A.y,p), lam=mulp(mulp(3,mulp(A.x,A.x,p),p),powp(den,p-2,p),p);
        u32 x3=subp(mulp(lam,lam,p),addp(A.x,A.x,p),p);
        u32 y3=subp(mulp(lam,subp(A.x,x3,p),p),A.y,p);
        return {x3,y3,false};
    }
    u32 lam=mulp(subp(B.y,A.y,p),powp(subp(B.x,A.x,p),p-2,p),p);
    u32 x3=subp(subp(mulp(lam,lam,p),A.x,p),B.x,p);
    u32 y3=subp(mulp(lam,subp(A.x,x3,p),p),A.y,p);
    return {x3,y3,false};
}

static MP mmul(MP P, int n, u32 p) {
    MP R;
    while(n) {
        if(n&1) R=madd(R,P,p);
        n>>=1;
        if(n) P=madd(P,P,p);
    }
    return R;
}

static constexpr u32 BAD = 0xffffffffu;

// D_m(r) = v^3-u^3 for the m-fold distinguished point on
// u^3+v^3=1+r^3.  BAD means this prime cannot be used for this value.
static u32 dmod(u32 r, int m, u32 p) {
    u32 onepr=addp(1,r,p);
    if(!onepr) return BAD;
    u32 r2=mulp(r,r,p), r3=mulp(r2,r,p), K=addp(1,r3,p);
    u32 inv=powp(onepr,p-2,p);
    MP P{mulp(mulp(12,K,p),inv,p),
         mulp(mulp(mulp(36,K,p),subp(1,r,p),p),inv,p),false};
    MP Q=mmul(P,m,p);
    if(Q.inf || Q.x==0) return BAD;
    u32 den=mulp(6,Q.x,p);
    if(!den) return BAD;
    u32 id=powp(den,p-2,p);
    u32 t=mulp(36,K,p);
    u32 u=mulp(addp(t,Q.y,p),id,p);
    u32 v=mulp(subp(t,Q.y,p),id,p);
    u32 u3=mulp(mulp(u,u,p),u,p), v3=mulp(mulp(v,v,p),v,p);
    return subp(v3,u3,p);
}

struct Filter {
    u32 p;
    vector<u64> mask;
    vector<u32> invq;
};

static Filter make_filter(u32 p, int H, const vector<Combo>& combos) {
    vector<array<u32,4>> D(p);
    for(u32 x=0;x<p;x++) for(int j=0;j<4;j++) D[x][j]=dmod(x,j+3,p);
    vector<unsigned char> cube(p,0);
    for(u32 x=0;x<p;x++) cube[mulp(mulp(x,x,p),x,p)]=1;
    u32 inv2=(p+1)/2;
    u64 all = combos.size()==64 ? ~u64(0) : ((u64(1)<<combos.size())-1);
    vector<u64> mask(p,0);
    for(u32 x=0;x<p;x++) {
        u32 x2=mulp(x,x,p), x3=mulp(x2,x,p), x6=mulp(x3,x3,p);
        u32 kac=addp(1,x6,p);
        u64 M=0;
        for(size_t k=0;k<combos.size();k++) {
            auto c=combos[k];
            u32 A=D[x][c.mab-3], B=D[x][c.mbc-3];
            if(A==BAD || B==BAD) { M |= u64(1)<<k; continue; }
            B=mulp(x3,B,p);
            u32 T=0;
            T = c.sab>0 ? addp(T,A,p) : subp(T,A,p);
            T = c.sbc>0 ? addp(T,B,p) : subp(T,B,p);
            u32 e=mulp(addp(kac,T,p),inv2,p);
            u32 h=mulp(subp(kac,T,p),inv2,p);
            if(cube[e] && cube[h]) M |= u64(1)<<k;
        }
        mask[x]=M & all;
    }
    vector<u32> invq(H+1,0);
    for(int q=1;q<=H;q++) invq[q]=powp((u32)q,p-2,p); // p>H
    return {p,std::move(mask),std::move(invq)};
}

struct QP { mpq_class x,y; bool inf=true; };
static QP qadd(QP A, QP B) {
    if(A.inf) return B; if(B.inf) return A;
    if(A.x==B.x) {
        if(A.y==-B.y || A.y==0) return QP{};
        if(A.y!=B.y) return QP{};
        mpq_class lam=3*A.x*A.x/(2*A.y);
        mpq_class x3=lam*lam-2*A.x;
        mpq_class y3=lam*(A.x-x3)-A.y;
        return {x3,y3,false};
    }
    mpq_class lam=(B.y-A.y)/(B.x-A.x);
    mpq_class x3=lam*lam-A.x-B.x;
    mpq_class y3=lam*(A.x-x3)-A.y;
    return {x3,y3,false};
}
static QP qmul(QP P, int n) {
    QP R;
    while(n) {
        if(n&1) R=qadd(R,P);
        n>>=1;
        if(n) P=qadd(P,P);
    }
    return R;
}

struct QMap { mpq_class u,v,d; bool ok=false; };
static QMap qmap(const mpq_class& r, int m) {
    mpq_class K=1+r*r*r;
    QP P{12*K/(1+r),36*K*(1-r)/(1+r),false};
    QP Q=qmul(P,m);
    if(Q.inf || Q.x==0) return {};
    mpq_class u=(36*K+Q.y)/(6*Q.x), v=(36*K-Q.y)/(6*Q.x);
    if(u*u*u+v*v*v!=K) throw std::runtime_error("bad exact map");
    return {u,v,v*v*v-u*u*u,true};
}

static bool qcube(const mpq_class& q, mpq_class& root) {
    if(q<=0) return false;
    mpz_class rn,rd;
    if(!mpz_root(rn.get_mpz_t(),q.get_num_mpz_t(),3)) return false;
    if(!mpz_root(rd.get_mpz_t(),q.get_den_mpz_t(),3)) return false;
    root=mpq_class(rn,rd); root.canonicalize();
    return root*root*root==q;
}

static mpz_class lcmz(const mpz_class&a,const mpz_class&b) {
    mpz_class g; mpz_gcd(g.get_mpz_t(),a.get_mpz_t(),b.get_mpz_t()); return a/g*b;
}

static bool reconstruct(const mpq_class& r, const Combo& c,
                        const array<QMap,4>& maps, std::string& text) {
    const QMap &A=maps[c.mab-3], &B=maps[c.mbc-3];
    if(!A.ok||!B.ok||A.u<=0||A.v<=0||B.u<=0||B.v<=0) return false;
    mpq_class r3=r*r*r, r6=r3*r3;
    mpq_class T=A.d;
    if(c.sab<0) T=-T;
    mpq_class TB=r3*B.d;
    if(c.sbc<0) TB=-TB;
    T += TB;
    mpq_class e3=(1+r6+T)/2, h3=(1+r6-T)/2, e,h;
    if(!qcube(e3,e)||!qcube(h3,h)) return false;

    auto ori=[](const QMap&M,int s){
        return s>0 ? std::make_pair(M.v,M.u) : std::make_pair(M.u,M.v);
    };
    auto AB=ori(A,c.sab), BC0=ori(B,c.sbc);
    std::pair<mpq_class,mpq_class> BC={r*BC0.first,r*BC0.second};
    // e^3-h^3 = T, so put h above e to contribute -T.
    array<mpq_class,9> q={1,r,r*r, BC.first,h,AB.first, BC.second,e,AB.second};
    for(auto const&x:q) if(x<=0) return false;
    for(int i=0;i<9;i++) for(int j=i+1;j<9;j++) if(q[i]==q[j]) return false;

    mpz_class L=1;
    for(auto const&x:q) L=lcmz(L,x.get_den());
    array<mpz_class,9> z;
    for(int i=0;i<9;i++) z[i]=q[i].get_num()*(L/q[i].get_den());
    mpz_class G=0;
    for(auto const&x:z) { mpz_class g,ax=abs(x); mpz_gcd(g.get_mpz_t(),G.get_mpz_t(),ax.get_mpz_t()); G=g; }
    if(G>1) for(auto&x:z) x/=G;
    std::set<mpz_class> ss(z.begin(),z.end()); if(ss.size()!=9||*ss.begin()<=0) return false;
    array<mpz_class,9> z3; for(int i=0;i<9;i++) z3[i]=z[i]*z[i]*z[i];
    array<mpz_class,6> s={z3[0]+z3[1]+z3[2],z3[3]+z3[4]+z3[5],z3[6]+z3[7]+z3[8],
                         z3[0]+z3[3]+z3[6],z3[1]+z3[4]+z3[7],z3[2]+z3[5]+z3[8]};
    for(int i=1;i<6;i++) if(s[i]!=s[0]) throw std::runtime_error("six-sum replay failed");
    text="r="+r.get_str()+" mab="+std::to_string(c.mab)+" mbc="+std::to_string(c.mbc)+
         " sab="+std::to_string(c.sab)+" sbc="+std::to_string(c.sbc)+" bases=";
    for(int i=0;i<9;i++) { if(i) text+=","; text+=z[i].get_str(); }
    text+=" S="+s[0].get_str();
    return true;
}

int main(int argc,char**argv) {
    if(argc!=6) {
        std::cerr<<"usage: r8 H part parts OUT filters\n";
        return 2;
    }
    int H=std::stoi(argv[1]),part=std::stoi(argv[2]),parts=std::stoi(argv[3]);
    std::string outp=argv[4]; int nf=std::stoi(argv[5]);
    if(H<2||part<0||part>=parts||nf<1||nf>12) return 2;

    vector<Combo> combos;
    for(int a=3;a<=6;a++) for(int b=3;b<=6;b++)
        for(int sa:{-1,1}) for(int sb:{-1,1}) combos.push_back({a,b,sa,sb});
    if(combos.size()!=64) return 3;

    auto ps=sieve_primes((u32)H+1,nf);
    vector<Filter> fs; fs.reserve(ps.size());
    auto t0=std::chrono::steady_clock::now();
    for(u32 p:ps) fs.push_back(make_filter(p,H,combos));

    std::ofstream out(outp); if(!out) return 3;
    u64 fractions=0,modsurv=0,exacttests=0,hits=0;
    for(int q=1;q<=H;q++) {
        if((q-1)%parts!=part) continue;
        for(int n=q+1;n<=H;n++) {
            if(std::gcd(n,q)!=1) continue;
            fractions++;
            u64 mask=~u64(0);
            for(auto const&f:fs) {
                u32 x=mulp((u32)n,f.invq[q],f.p);
                mask &= f.mask[x];
                if(!mask) break;
            }
            if(!mask) continue;
            modsurv++;
            mpq_class rr(n,q); rr.canonicalize();
            array<QMap,4> maps;
            for(int m=3;m<=6;m++) maps[m-3]=qmap(rr,m);
            while(mask) {
                int bit=__builtin_ctzll(mask); mask&=mask-1; exacttests++;
                std::string text;
                if(reconstruct(rr,combos[bit],maps,text)) {
                    hits++; out<<"HIT "<<text<<"\n"; out.flush();
                }
            }
        }
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT H="<<H<<" part="<<part<<" parts="<<parts<<" filters="<<nf
       <<" fractions="<<fractions<<" modular_survivors="<<modsurv
       <<" exact_tests="<<exacttests<<" hits="<<hits<<" ms="<<ms<<" primes=";
    for(size_t i=0;i<ps.size();i++){if(i)out<<',';out<<ps[i];} out<<"\n";
    std::cerr<<"fractions="<<fractions<<" modular_survivors="<<modsurv
             <<" exact_tests="<<exacttests<<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
