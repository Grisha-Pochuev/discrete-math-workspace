// r25: distributed exact tail engine using the r20/r22/r23 reductions.
#define main d1_old_main
#include "d1.cpp"
#undef main

#include <array>
#include <stdexcept>

static inline u128 q25(u64 d,u64 x){
    return (u128)3*x*x+(u128)3*d*x+(u128)d*d;
}
static u64 fx25(u64 d,u128 M){
    if(M<(u128)d*d)return 0;
    const u128 disc=(u128)12*M-(u128)3*d*d;
    const u64 s=isqrt128(disc);
    u64 x=0;
    if(s>3*d)x=(s-3*d)/6;
    while(q25(d,x+1)<=M)++x;
    while(x&&q25(d,x)>M)--x;
    return x;
}

struct S25{
    u64 rec=0,groups=0,triples=0,orient=0,k01_3=0,all3=0,exact=0,hits=0;
    size_t max_group=0,max_trans=0;
};

static bool has25(const std::vector<std::pair<u64,u64>>&v,std::pair<u64,u64>q){
    return std::binary_search(v.begin(),v.end(),q);
}

static bool close25(u64 D,const Rec&A,const Rec&B,const Rec&C,
                    const std::vector<std::pair<u64,u64>>&kab,
                    std::ostream&out,S25&st){
    const u64 a=A.x,au=A.y,b=B.x,bu=B.y,c=C.x,cu=C.y;
    for(auto [p,q]:kab){
        if(p<=a)continue;
        const u128 E=c3(p)-c3(a);
        if(E==(u128)D)continue;
        ++st.exact;
        if(c3(q)-c3(b)!=E)throw std::runtime_error("r25 K01 replay");
        const u128 wc=c3(c)+E;
        const u64 w=fcbrt(wc);
        if(c3(w)!=wc)continue;
        std::array<u64,9>z={a,w,bu,q,au,c,cu,b,p};
        std::set<u64>ss(z.begin(),z.end());
        if(ss.size()!=9||*ss.begin()==0)continue;
        std::array<u128,6>s={
            c3(z[0])+c3(z[1])+c3(z[2]),
            c3(z[3])+c3(z[4])+c3(z[5]),
            c3(z[6])+c3(z[7])+c3(z[8]),
            c3(z[0])+c3(z[3])+c3(z[6]),
            c3(z[1])+c3(z[4])+c3(z[7]),
            c3(z[2])+c3(z[5])+c3(z[8])};
        for(int i=1;i<6;i++)if(s[i]!=s[0])throw std::runtime_error("r25 six sums");
        ++st.hits;
        out<<"HIT D="<<D<<" E="<<s128(E)<<" bases=";
        for(int i=0;i<9;i++){if(i)out<<',';out<<z[i];}
        out<<" S="<<s128(s[0])<<"\n";
        out.flush();
        return true;
    }
    return false;
}

static void triple25(u64 D,const Rec&A,const Rec&B,const Rec&C,std::ostream&out,S25&st){
    const u64 a=A.x,b=B.x,c=C.x;
    // By transposing the additive grid, choose D as the smaller of the two
    // coordinate directions. Equality would duplicate a cell, so K01>D.
    const u128 K01=c3(b)-c3(a);
    if(K01<=(u128)D)return;
    ++st.orient;

    auto ab=reps_from_known(a,b);
    st.max_trans=std::max(st.max_trans,ab.size());
    if(ab.size()<3)return;
    ++st.k01_3;
    if(!has25(ab,{A.x,B.x})||!has25(ab,{A.y,B.y}))
        throw std::runtime_error("r25 AB known reps missing");

    // r22: every transverse difference must have a third positive
    // representation.  Check the other two before closure.
    auto bc=reps_from_known(b,c);
    st.max_trans=std::max(st.max_trans,bc.size());
    if(bc.size()<3)return;
    if(!has25(bc,{B.x,C.x})||!has25(bc,{B.y,C.y}))
        throw std::runtime_error("r25 BC known reps missing");

    auto ac=reps_from_known(a,c);
    st.max_trans=std::max(st.max_trans,ac.size());
    if(ac.size()<3)return;
    if(!has25(ac,{A.x,C.x})||!has25(ac,{A.y,C.y}))
        throw std::runtime_error("r25 AC known reps missing");

    ++st.all3;
    close25(D,A,B,C,ab,out,st);
}

static void range25(u64 L,u64 R,std::ostream&out,S25&st){
    u64 dmax=fcbrt((u128)R+1);if(dmax)--dmax;
    std::vector<Rec>v;
    // r24 measured about 25.7M records per 1e14 near 1.2e19.
    const long double width=(long double)R-(long double)L+1.0L;
    const long double est=3.2e7L*(width/1.0e14L)+1024.0L;
    if(est>0&&est<1.2e8L)v.reserve((size_t)est);

    for(u64 d=1;d<=dmax;d++){
        const u128 Mlo=((u128)L+d-1)/d,Mhi=(u128)R/d;
        if(Mlo>Mhi)continue;
        u64 xmin=fx25(d,Mlo-1)+1;if(xmin<1)xmin=1;
        const u64 xmax=fx25(d,Mhi);if(xmin>xmax)continue;
        for(u64 x=xmin;x<=xmax;x++){
            const u64 y=x+d;
            if(y>0xffffffffULL)throw std::runtime_error("r25 endpoint overflow");
            const u128 DD=(u128)d*q25(d,x);
            if(DD<L||DD>R||DD>UINT64_MAX)throw std::runtime_error("r25 enum error");
            v.push_back({(u64)DD,(uint32_t)x,(uint32_t)y});
        }
    }
    std::sort(v.begin(),v.end());
    st.rec+=v.size();
    for(size_t i=0;i<v.size();){
        size_t j=i+1;while(j<v.size()&&v[j].d==v[i].d)++j;
        const size_t m=j-i;st.max_group=std::max(st.max_group,m);
        if(m>=3){
            ++st.groups;
            for(size_t a=i;a<j;a++)for(size_t b=a+1;b<j;b++)for(size_t c=b+1;c<j;c++){
                ++st.triples;
                triple25(v[i].d,v[a],v[b],v[c],out,st);
            }
        }
        i=j;
    }
}

int main(int argc,char**argv){
    if(argc!=9){
        std::cerr<<"usage: r25 LO HI CHUNK part parts soft_seconds OUT PROGRESS\n";
        return 2;
    }
    const u64 LO=std::stoull(argv[1]),HI=std::stoull(argv[2]),CH=std::stoull(argv[3]);
    const int part=std::stoi(argv[4]),parts=std::stoi(argv[5]),soft=std::stoi(argv[6]);
    const std::string outp=argv[7],progp=argv[8];
    if(!LO||LO>HI||!CH||part<0||part>=parts||soft<1)return 2;
    std::ofstream out(outp),prog(progp);if(!out||!prog)return 3;
    const auto t0=std::chrono::steady_clock::now();
    S25 st;u64 assigned=0,done=0;bool partial=false;u64 lastL=0,lastR=0;
    const u128 total=((u128)HI-LO)/CH+1;
    if(total>UINT64_MAX)return 4;
    const u64 chunks=(u64)total;
    for(u64 ci=(u64)part;ci<chunks;ci+=(u64)parts){
        const auto elapsed=std::chrono::duration_cast<std::chrono::seconds>(std::chrono::steady_clock::now()-t0).count();
        if(elapsed>=soft){partial=true;break;}
        ++assigned;
        const u128 Lu=(u128)LO+(u128)ci*CH;
        const u128 Ru=std::min<u128>((u128)HI,Lu+CH-1);
        const u64 L=(u64)Lu,R=(u64)Ru;
        range25(L,R,out,st);++done;lastL=L;lastR=R;
        prog<<"CHUNK idx="<<ci<<" lo="<<L<<" hi="<<R<<" done="<<done
            <<" rec="<<st.rec<<" groups="<<st.groups<<" triples="<<st.triples
            <<" orient="<<st.orient<<" all3="<<st.all3<<" exact="<<st.exact
            <<" hits="<<st.hits<<"\n";
        prog.flush();out.flush();
    }
    const auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT lo="<<LO<<" hi="<<HI<<" chunk="<<CH<<" part="<<part<<" parts="<<parts
       <<" chunks="<<chunks<<" assigned="<<assigned<<" done="<<done
       <<" last_lo="<<lastL<<" last_hi="<<lastR<<" rec="<<st.rec<<" groups="<<st.groups
       <<" triples="<<st.triples<<" orient="<<st.orient<<" k01_3="<<st.k01_3
       <<" all3="<<st.all3<<" exact="<<st.exact<<" hits="<<st.hits
       <<" max_group="<<st.max_group<<" max_trans="<<st.max_trans
       <<" partial="<<partial<<" ms="<<ms<<"\n";
    std::cerr<<"STAT part="<<part<<" done="<<done<<'/'<<assigned<<" rec="<<st.rec
             <<" groups="<<st.groups<<" triples="<<st.triples<<" orient="<<st.orient
             <<" all3="<<st.all3<<" exact="<<st.exact<<" hits="<<st.hits
             <<" partial="<<partial<<" ms="<<ms<<"\n";
    if(st.hits)return 10;
    if(partial)return 124;
    return 0;
}
