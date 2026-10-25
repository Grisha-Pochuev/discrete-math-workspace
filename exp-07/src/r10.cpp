// r10: one-parameter probes anchored at the classical 8-of-9-cubes example.
#define main r8_old_main
#include "r8.cpp"
#undef main

struct ACombo { int mode,m,sa,sb; };

static u32 fmodq(u64 n,u64 d,u32 p){return mulp((u32)(n%p),powp((u32)(d%p),p-2,p),p);}

struct AFilter {u32 p;vector<u64> mask;vector<u32> invq;};

static AFilter make_afilter(u32 p,int H,const vector<ACombo>& cs){
    vector<unsigned char> cube(p,0);for(u32 x=0;x<p;x++)cube[mulp(mulp(x,x,p),x,p)]=1;
    const u32 inv2=(p+1)/2;
    const u32 x0=fmodq(55,17,p), y0=fmodq(619,165,p);
    const u32 au=fmodq(24,17,p), av=fmodq(54,17,p);
    const u32 bu=fmodq(178,165,p), bv=fmodq(618,165,p);
    const u32 da=subp(mulp(mulp(av,av,p),av,p),mulp(mulp(au,au,p),au,p),p);
    const u32 db=subp(mulp(mulp(bv,bv,p),bv,p),mulp(mulp(bu,bu,p),bu,p),p);
    const u32 x03=mulp(mulp(x0,x0,p),x0,p);
    vector<u64> mask(p,0);
    for(u32 t=0;t<p;t++){
        u32 dt[8];for(int m=3;m<=10;m++)dt[m-3]=dmod(t,m,p);
        const u32 t3=mulp(mulp(t,t,p),t,p);
        u64 M=0;
        for(size_t k=0;k<cs.size();k++){
            auto c=cs[k];u32 A=0,B=0,K=0;
            if(c.mode==0){ // x=x0 fixed, y=t varies
                A=da;B=dt[c.m-3];
                if(B==BAD){M|=u64(1)<<k;continue;}
                B=mulp(x03,B,p);
                u32 xy=mulp(x0,t,p),xy3=mulp(mulp(xy,xy,p),xy,p);K=addp(1,xy3,p);
            }else{ // y=y0 fixed, x=t varies
                A=dt[c.m-3];
                if(A==BAD){M|=u64(1)<<k;continue;}
                B=mulp(t3,db,p);
                u32 xy=mulp(t,y0,p),xy3=mulp(mulp(xy,xy,p),xy,p);K=addp(1,xy3,p);
            }
            u32 T=0;T=c.sa>0?addp(T,A,p):subp(T,A,p);T=c.sb>0?addp(T,B,p):subp(T,B,p);
            u32 e3=mulp(addp(K,T,p),inv2,p),h3=mulp(subp(K,T,p),inv2,p);
            if(cube[e3]&&cube[h3])M|=u64(1)<<k;
        }
        mask[t]=M;
    }
    vector<u32> invq(H+1,0);for(int q=1;q<=H;q++)invq[q]=powp((u32)q,p-2,p);
    return {p,std::move(mask),std::move(invq)};
}

static std::pair<mpq_class,mpq_class> orient_pair(mpq_class u,mpq_class v,int s){return s>0?std::make_pair(v,u):std::make_pair(u,v);}

static bool replay_anchor(const mpq_class&t,const ACombo&c,std::string&text){
    const mpq_class x0(55,17),y0(619,165),au(24,17),av(54,17),bu(178,165),bv(618,165);
    mpq_class x,y;mpq_class AU,AV,BU,BV;mpq_class da=av*av*av-au*au*au,db=bv*bv*bv-bu*bu*bu;
    mpq_class A,B;
    if(c.mode==0){
        x=x0;y=t;AU=au;AV=av;A=da;
        QMap qm=qmap(y,c.m);if(!qm.ok||qm.u<=0||qm.v<=0)return false;BU=qm.u;BV=qm.v;B=x*x*x*qm.d;
    }else{
        x=t;y=y0;
        QMap qm=qmap(x,c.m);if(!qm.ok||qm.u<=0||qm.v<=0)return false;AU=qm.u;AV=qm.v;A=qm.d;
        BU=bu;BV=bv;B=x*x*x*db;
    }
    mpq_class T=A;if(c.sa<0)T=-T;mpq_class TB=B;if(c.sb<0)TB=-TB;T+=TB;
    mpq_class z=x*y,K=1+z*z*z,e3=(K+T)/2,h3=(K-T)/2,e,h;
    if(!qcube(e3,e)||!qcube(h3,h))return false;
    auto AB=orient_pair(AU,AV,c.sa),BC0=orient_pair(BU,BV,c.sb);
    std::pair<mpq_class,mpq_class> BC={x*BC0.first,x*BC0.second};
    array<mpq_class,9> q={1,x,z,BC.first,h,AB.first,BC.second,e,AB.second};
    for(auto const&w:q)if(w<=0)return false;for(int i=0;i<9;i++)for(int j=i+1;j<9;j++)if(q[i]==q[j])return false;
    mpz_class L=1;for(auto const&w:q)L=lcmz(L,w.get_den());array<mpz_class,9>bases;
    for(int i=0;i<9;i++)bases[i]=q[i].get_num()*(L/q[i].get_den());mpz_class G=0;
    for(auto const&w:bases){mpz_class aw=w>=0?w:-w,g;mpz_gcd(g.get_mpz_t(),G.get_mpz_t(),aw.get_mpz_t());G=g;}if(G>1)for(auto&w:bases)w/=G;
    std::set<mpz_class>ss(bases.begin(),bases.end());if(ss.size()!=9||*ss.begin()<=0)return false;
    array<mpz_class,9>c3;for(int i=0;i<9;i++)c3[i]=bases[i]*bases[i]*bases[i];
    array<mpz_class,6>s={c3[0]+c3[1]+c3[2],c3[3]+c3[4]+c3[5],c3[6]+c3[7]+c3[8],c3[0]+c3[3]+c3[6],c3[1]+c3[4]+c3[7],c3[2]+c3[5]+c3[8]};
    for(int i=1;i<6;i++)if(s[i]!=s[0])throw std::runtime_error("r10 six-sum replay failed");
    text="mode="+std::to_string(c.mode)+" t="+t.get_str()+" m="+std::to_string(c.m)+" sa="+std::to_string(c.sa)+" sb="+std::to_string(c.sb)+" bases=";
    for(int i=0;i<9;i++){if(i)text+=",";text+=bases[i].get_str();}text+=" S="+s[0].get_str();return true;
}

static void selfcheck_near(){
    const mpq_class x(55,17),y(619,165),au(24,17),av(54,17),bu(178,165),bv(618,165);
    mpq_class da=av*av*av-au*au*au,db=bv*bv*bv-bu*bu*bu,z=x*y,K=1+z*z*z,T=da+x*x*x*db;
    mpq_class h3=(K-T)/2,target=mpq_class(115,51);target=target*target*target;
    if(h3!=target)throw std::runtime_error("near-solution anchor self-check failed");
}

int main(int argc,char**argv){
    if(argc!=6){std::cerr<<"usage: r10 H part parts OUT filters\n";return 2;}int H=std::stoi(argv[1]),part=std::stoi(argv[2]),parts=std::stoi(argv[3]);std::string outp=argv[4];int nf=std::stoi(argv[5]);
    if(H<166||part<0||part>=parts||nf<1||nf>12)return 2;selfcheck_near();
    vector<ACombo>cs;for(int mode=0;mode<2;mode++)for(int m=3;m<=10;m++)for(int sa:{-1,1})for(int sb:{-1,1})cs.push_back({mode,m,sa,sb});if(cs.size()!=64)return 3;
    auto ps=sieve_primes((u32)H+1,nf);vector<AFilter>fs;auto t0=std::chrono::steady_clock::now();for(u32 p:ps)fs.push_back(make_afilter(p,H,cs));
    std::ofstream out(outp);u64 fractions=0,modsurv=0,exacttests=0,hits=0;
    for(int q=1;q<=H;q++){if((q-1)%parts!=part)continue;for(int n=q+1;n<=H;n++){if(std::gcd(n,q)!=1)continue;fractions++;u64 mask=~u64(0);
        for(auto const&f:fs){u32 t=mulp((u32)n,f.invq[q],f.p);mask&=f.mask[t];if(!mask)break;}if(!mask)continue;modsurv++;mpq_class tt(n,q);tt.canonicalize();
        while(mask){int bit=__builtin_ctzll(mask);mask&=mask-1;exacttests++;std::string text;if(replay_anchor(tt,cs[bit],text)){hits++;out<<"HIT "<<text<<"\n";out.flush();}}
    }}
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();out<<"STAT H="<<H<<" part="<<part<<" parts="<<parts<<" filters="<<nf<<" combos="<<cs.size()<<" fractions="<<fractions<<" modular_survivors="<<modsurv<<" exact_tests="<<exacttests<<" hits="<<hits<<" ms="<<ms<<" primes=";for(size_t i=0;i<ps.size();i++){if(i)out<<',';out<<ps[i];}out<<"\n";
    std::cerr<<"fractions="<<fractions<<" modular_survivors="<<modsurv<<" exact_tests="<<exacttests<<" hits="<<hits<<" ms="<<ms<<"\n";return hits?10:0;
}
