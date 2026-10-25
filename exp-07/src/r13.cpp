// r13: broaden r9 to primitive exponent pairs q<=6 and multiples 3..10.
#define main r8_old_main
#include "r8.cpp"
#undef main

#include <tuple>

static constexpr int MLO=3, MHI=10, NM=MHI-MLO+1;
struct XCombo { int pe,qe,mab,mbc,sab,sbc; };
struct XFilter { u32 p; size_t words; vector<u64> masks; vector<u32> invq; };

static vector<std::pair<int,int>> xpairs(){
    vector<std::pair<int,int>> v;
    for(int q=2;q<=6;q++)for(int p=1;p<q;p++)if(std::gcd(p,q)==1)v.push_back({p,q});
    return v;
}

static XFilter make_xfilter(u32 mod,int H,const vector<XCombo>&cs){
    const size_t words=(cs.size()+63)/64;
    vector<unsigned char> cube(mod,0);for(u32 x=0;x<mod;x++)cube[mulp(mulp(x,x,mod),x,mod)]=1;
    const u32 inv2=(mod+1)/2;
    vector<u64> masks((size_t)mod*words,0);
    for(u32 x=0;x<mod;x++){
        u32 pw[19];pw[0]=1;for(int e=1;e<=18;e++)pw[e]=mulp(pw[e-1],x,mod);
        u32 D[6][NM];for(int e=1;e<=5;e++)for(int m=MLO;m<=MHI;m++)D[e][m-MLO]=dmod(pw[e],m,mod);
        u64*dst=&masks[(size_t)x*words];
        for(size_t k=0;k<cs.size();k++){
            auto const&c=cs[k];u32 A=D[c.pe][c.mab-MLO],B=D[c.qe-c.pe][c.mbc-MLO];
            if(A==BAD||B==BAD){dst[k>>6]|=u64(1)<<(k&63);continue;}
            B=mulp(pw[3*c.pe],B,mod);u32 T=0;
            T=c.sab>0?addp(T,A,mod):subp(T,A,mod);T=c.sbc>0?addp(T,B,mod):subp(T,B,mod);
            u32 K=addp(1,pw[3*c.qe],mod),e3=mulp(addp(K,T,mod),inv2,mod),h3=mulp(subp(K,T,mod),inv2,mod);
            if(cube[e3]&&cube[h3])dst[k>>6]|=u64(1)<<(k&63);
        }
    }
    if(cs.size()%64){u64 keep=(u64(1)<<(cs.size()%64))-1;for(u32 x=0;x<mod;x++)masks[(size_t)x*words+words-1]&=keep;}
    vector<u32> invq(H+1);for(int q=1;q<=H;q++)invq[q]=powp((u32)q,mod-2,mod);
    return {mod,words,std::move(masks),std::move(invq)};
}

static mpq_class qpowx(mpq_class x,int e){mpq_class z=1;while(e){if(e&1)z*=x;e>>=1;if(e)x*=x;}return z;}

static bool replay_x(const mpq_class&r,const XCombo&c,std::string&text){
    mpq_class a=qpowx(r,c.pe),z=qpowx(r,c.qe),y=qpowx(r,c.qe-c.pe);
    QMap A=qmap(a,c.mab),B=qmap(y,c.mbc);if(!A.ok||!B.ok||A.u<=0||A.v<=0||B.u<=0||B.v<=0)return false;
    mpq_class T=A.d;if(c.sab<0)T=-T;mpq_class TB=a*a*a*B.d;if(c.sbc<0)TB=-TB;T+=TB;
    mpq_class K=1+z*z*z,e3=(K+T)/2,h3=(K-T)/2,e,h;if(!qcube(e3,e)||!qcube(h3,h))return false;
    auto ori=[](const QMap&M,int s){return s>0?std::make_pair(M.v,M.u):std::make_pair(M.u,M.v);};
    auto AB=ori(A,c.sab),BC0=ori(B,c.sbc);std::pair<mpq_class,mpq_class>BC={a*BC0.first,a*BC0.second};
    array<mpq_class,9>q={1,a,z,BC.first,h,AB.first,BC.second,e,AB.second};for(auto const&w:q)if(w<=0)return false;for(int i=0;i<9;i++)for(int j=i+1;j<9;j++)if(q[i]==q[j])return false;
    mpz_class L=1;for(auto const&w:q)L=lcmz(L,w.get_den());array<mpz_class,9>b;
    for(int i=0;i<9;i++)b[i]=q[i].get_num()*(L/q[i].get_den());mpz_class G=0;for(auto const&w:b){mpz_class aw=w>=0?w:-w,g;mpz_gcd(g.get_mpz_t(),G.get_mpz_t(),aw.get_mpz_t());G=g;}if(G>1)for(auto&w:b)w/=G;
    std::set<mpz_class>ss(b.begin(),b.end());if(ss.size()!=9||*ss.begin()<=0)return false;array<mpz_class,9>c3;for(int i=0;i<9;i++)c3[i]=b[i]*b[i]*b[i];
    array<mpz_class,6>s={c3[0]+c3[1]+c3[2],c3[3]+c3[4]+c3[5],c3[6]+c3[7]+c3[8],c3[0]+c3[3]+c3[6],c3[1]+c3[4]+c3[7],c3[2]+c3[5]+c3[8]};for(int i=1;i<6;i++)if(s[i]!=s[0])throw std::runtime_error("r13 replay failed");
    text="r="+r.get_str()+" p="+std::to_string(c.pe)+" q="+std::to_string(c.qe)+" ma="+std::to_string(c.mab)+" mb="+std::to_string(c.mbc)+" sa="+std::to_string(c.sab)+" sb="+std::to_string(c.sbc)+" bases=";for(int i=0;i<9;i++){if(i)text+=",";text+=b[i].get_str();}text+=" S="+s[0].get_str();return true;
}

int main(int argc,char**argv){
    if(argc!=6){std::cerr<<"usage: r13 H part parts OUT filters\n";return 2;}int H=std::stoi(argv[1]),part=std::stoi(argv[2]),parts=std::stoi(argv[3]);std::string outp=argv[4];int nf=std::stoi(argv[5]);if(H<2||part<0||part>=parts||nf<1||nf>12)return 2;
    auto ep=xpairs();vector<XCombo>cs;for(auto [p,q]:ep)for(int a=MLO;a<=MHI;a++)for(int b=MLO;b<=MHI;b++)for(int sa:{-1,1})for(int sb:{-1,1})cs.push_back({p,q,a,b,sa,sb});size_t words=(cs.size()+63)/64;
    auto mods=sieve_primes((u32)H+1,nf);vector<XFilter>fs;auto t0=std::chrono::steady_clock::now();for(u32 p:mods)fs.push_back(make_xfilter(p,H,cs));
    std::ofstream out(outp);u64 fractions=0,modsurv=0,exacttests=0,hits=0;vector<u64>mask(words);
    for(int q=1;q<=H;q++){if((q-1)%parts!=part)continue;for(int n=q+1;n<=H;n++){if(std::gcd(n,q)!=1)continue;fractions++;std::fill(mask.begin(),mask.end(),~u64(0));if(cs.size()%64)mask.back()=(u64(1)<<(cs.size()%64))-1;bool any=true;
        for(auto const&f:fs){u32 x=mulp((u32)n,f.invq[q],f.p);const u64*src=&f.masks[(size_t)x*words];any=false;for(size_t w=0;w<words;w++){mask[w]&=src[w];any|=mask[w]!=0;}if(!any)break;}if(!any)continue;modsurv++;mpq_class rr(n,q);rr.canonicalize();
        for(size_t w=0;w<words;w++){u64 bits=mask[w];while(bits){int bit=__builtin_ctzll(bits);bits&=bits-1;size_t k=w*64+bit;if(k>=cs.size())continue;exacttests++;std::string text;if(replay_x(rr,cs[k],text)){hits++;out<<"HIT "<<text<<"\n";out.flush();}}}
    }}
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();out<<"STAT H="<<H<<" filters="<<nf<<" exponent_pairs="<<ep.size()<<" mlo="<<MLO<<" mhi="<<MHI<<" combos="<<cs.size()<<" fractions="<<fractions<<" modular_survivors="<<modsurv<<" exact_tests="<<exacttests<<" hits="<<hits<<" ms="<<ms<<"\n";std::cerr<<"STAT H="<<H<<" filters="<<nf<<" exponent_pairs="<<ep.size()<<" combos="<<cs.size()<<" fractions="<<fractions<<" modular_survivors="<<modsurv<<" exact_tests="<<exacttests<<" hits="<<hits<<" ms="<<ms<<"\n";return hits?10:0;
}
