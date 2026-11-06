// r9: generalized one-parameter top rows (1,r^p,r^q)
#define main r8_old_main
#include "r8.cpp"
#undef main

#include <tuple>

struct GCombo {
    int pe, qe;
    int mab, mbc, sab, sbc;
};

struct GFilter {
    u32 p;
    size_t words;
    vector<u64> masks; // residue-major: p * words
    vector<u32> invq;
};

static vector<std::pair<int,int>> exponent_pairs() {
    // Primitive exponent pairs only; non-primitive pairs are already contained
    // in a smaller pair after replacing r by a rational power.
    vector<std::pair<int,int>> v;
    for(int q=2;q<=4;q++) for(int p=1;p<q;p++)
        if(std::gcd(p,q)==1) v.push_back({p,q});
    return v; // (1,2),(1,3),(2,3),(1,4),(3,4)
}

static GFilter make_gfilter(u32 mod, int H, const vector<GCombo>& cs) {
    const size_t words=(cs.size()+63)/64;
    vector<unsigned char> cube(mod,0);
    for(u32 x=0;x<mod;x++) cube[mulp(mulp(x,x,mod),x,mod)]=1;
    const u32 inv2=(mod+1)/2;
    vector<u64> masks((size_t)mod*words,0);

    for(u32 x=0;x<mod;x++) {
        u32 xp[19]; xp[0]=1;
        for(int e=1;e<=18;e++) xp[e]=mulp(xp[e-1],x,mod);

        u32 D[5][4];
        for(int e=1;e<=4;e++) for(int m=3;m<=6;m++) D[e][m-3]=dmod(xp[e],m,mod);

        u64* dst=&masks[(size_t)x*words];
        for(size_t k=0;k<cs.size();k++) {
            const auto &c=cs[k];
            u32 A=D[c.pe][c.mab-3];
            u32 B=D[c.qe-c.pe][c.mbc-3];
            if(A==BAD || B==BAD) {
                dst[k>>6] |= u64(1)<<(k&63);
                continue;
            }
            B=mulp(xp[3*c.pe],B,mod);
            u32 T=0;
            T=c.sab>0 ? addp(T,A,mod) : subp(T,A,mod);
            T=c.sbc>0 ? addp(T,B,mod) : subp(T,B,mod);
            u32 K=addp(1,xp[3*c.qe],mod);
            u32 e3=mulp(addp(K,T,mod),inv2,mod);
            u32 h3=mulp(subp(K,T,mod),inv2,mod);
            if(cube[e3] && cube[h3]) dst[k>>6] |= u64(1)<<(k&63);
        }
    }

    // Clear unused high bits in the final word.
    if(cs.size()%64) {
        const u64 keep=(u64(1)<<(cs.size()%64))-1;
        for(u32 x=0;x<mod;x++) masks[(size_t)x*words+words-1]&=keep;
    }

    vector<u32> invq(H+1,0);
    for(int q=1;q<=H;q++) invq[q]=powp((u32)q,mod-2,mod);
    return {mod,words,std::move(masks),std::move(invq)};
}

static mpq_class qpow_small(mpq_class x,int e) {
    mpq_class z=1;
    while(e){if(e&1)z*=x;e>>=1;if(e)x*=x;}
    return z;
}

static bool reconstruct_g(const mpq_class& r,const GCombo& c,std::string& text) {
    const mpq_class rp=qpow_small(r,c.pe);
    const mpq_class rq=qpow_small(r,c.qe);
    const mpq_class ry=qpow_small(r,c.qe-c.pe);
    QMap A=qmap(rp,c.mab), B=qmap(ry,c.mbc);
    if(!A.ok||!B.ok||A.u<=0||A.v<=0||B.u<=0||B.v<=0) return false;

    mpq_class T=A.d;
    if(c.sab<0) T=-T;
    mpq_class TB=rp*rp*rp*B.d;
    if(c.sbc<0) TB=-TB;
    T+=TB;

    mpq_class K=1+rq*rq*rq;
    mpq_class e3=(K+T)/2,h3=(K-T)/2,e,h;
    if(!qcube(e3,e)||!qcube(h3,h)) return false;

    auto ori=[](const QMap&M,int s){
        return s>0 ? std::make_pair(M.v,M.u) : std::make_pair(M.u,M.v);
    };
    auto AB=ori(A,c.sab),BC0=ori(B,c.sbc);
    std::pair<mpq_class,mpq_class> BC={rp*BC0.first,rp*BC0.second};
    array<mpq_class,9> q={1,rp,rq, BC.first,h,AB.first, BC.second,e,AB.second};
    for(auto const&x:q) if(x<=0) return false;
    for(int i=0;i<9;i++) for(int j=i+1;j<9;j++) if(q[i]==q[j]) return false;

    mpz_class L=1;
    for(auto const&x:q) L=lcmz(L,x.get_den());
    array<mpz_class,9> z;
    for(int i=0;i<9;i++) z[i]=q[i].get_num()*(L/q[i].get_den());
    mpz_class G=0;
    for(auto const&x:z){mpz_class ax=x>=0?x:-x,g;mpz_gcd(g.get_mpz_t(),G.get_mpz_t(),ax.get_mpz_t());G=g;}
    if(G>1) for(auto&x:z)x/=G;
    std::set<mpz_class> ss(z.begin(),z.end());
    if(ss.size()!=9||*ss.begin()<=0) return false;
    array<mpz_class,9> z3;for(int i=0;i<9;i++)z3[i]=z[i]*z[i]*z[i];
    array<mpz_class,6> s={z3[0]+z3[1]+z3[2],z3[3]+z3[4]+z3[5],z3[6]+z3[7]+z3[8],
                          z3[0]+z3[3]+z3[6],z3[1]+z3[4]+z3[7],z3[2]+z3[5]+z3[8]};
    for(int i=1;i<6;i++)if(s[i]!=s[0])throw std::runtime_error("r9 six-sum replay failed");
    text="r="+r.get_str()+" p="+std::to_string(c.pe)+" q="+std::to_string(c.qe)+
         " mab="+std::to_string(c.mab)+" mbc="+std::to_string(c.mbc)+
         " sab="+std::to_string(c.sab)+" sbc="+std::to_string(c.sbc)+" bases=";
    for(int i=0;i<9;i++){if(i)text+=",";text+=z[i].get_str();}
    text+=" S="+s[0].get_str();
    return true;
}

int main(int argc,char**argv) {
    if(argc!=6){std::cerr<<"usage: r9 H part parts OUT filters\n";return 2;}
    const int H=std::stoi(argv[1]),part=std::stoi(argv[2]),parts=std::stoi(argv[3]);
    const std::string outp=argv[4];const int nf=std::stoi(argv[5]);
    if(H<2||part<0||part>=parts||nf<1||nf>12)return 2;

    vector<GCombo> cs;
    auto eps=exponent_pairs();
    for(auto [pe,qe]:eps) for(int a=3;a<=6;a++) for(int b=3;b<=6;b++)
        for(int sa:{-1,1}) for(int sb:{-1,1}) cs.push_back({pe,qe,a,b,sa,sb});
    const size_t words=(cs.size()+63)/64;

    auto mods=sieve_primes((u32)H+1,nf);
    vector<GFilter> fs;fs.reserve(mods.size());
    auto t0=std::chrono::steady_clock::now();
    for(u32 p:mods)fs.push_back(make_gfilter(p,H,cs));

    std::ofstream out(outp);if(!out)return 3;
    u64 fractions=0,modsurv=0,exacttests=0,hits=0;
    vector<u64> mask(words);
    for(int q=1;q<=H;q++) {
        if((q-1)%parts!=part)continue;
        for(int n=q+1;n<=H;n++) {
            if(std::gcd(n,q)!=1)continue;
            fractions++;
            std::fill(mask.begin(),mask.end(),~u64(0));
            if(cs.size()%64)mask.back()=(u64(1)<<(cs.size()%64))-1;
            bool any=true;
            for(auto const&f:fs) {
                u32 x=mulp((u32)n,f.invq[q],f.p);
                const u64* src=&f.masks[(size_t)x*words];
                any=false;
                for(size_t w=0;w<words;w++){mask[w]&=src[w];any|=(mask[w]!=0);}
                if(!any)break;
            }
            if(!any)continue;
            modsurv++;
            mpq_class rr(n,q);rr.canonicalize();
            for(size_t w=0;w<words;w++) {
                u64 bits=mask[w];
                while(bits){int b=__builtin_ctzll(bits);bits&=bits-1;size_t k=w*64+b;if(k>=cs.size())continue;exacttests++;
                    std::string text;if(reconstruct_g(rr,cs[k],text)){hits++;out<<"HIT "<<text<<"\n";out.flush();}
                }
            }
        }
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT H="<<H<<" part="<<part<<" parts="<<parts<<" filters="<<nf
       <<" exponent_pairs="<<eps.size()<<" combos="<<cs.size()<<" fractions="<<fractions
       <<" modular_survivors="<<modsurv<<" exact_tests="<<exacttests<<" hits="<<hits<<" ms="<<ms<<" primes=";
    for(size_t i=0;i<mods.size();i++){if(i)out<<',';out<<mods[i];}out<<"\n";
    std::cerr<<"pairs="<<eps.size()<<" combos="<<cs.size()<<" fractions="<<fractions
             <<" modular_survivors="<<modsurv<<" exact_tests="<<exacttests
             <<" hits="<<hits<<" ms="<<ms<<"\n";
    return hits?10:0;
}
