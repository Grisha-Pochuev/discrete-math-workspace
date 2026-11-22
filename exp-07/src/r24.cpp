#define main d1_old_main
#include "d1.cpp"
#undef main

#include <stdexcept>

static inline u128 q24(u64 d,u64 x){
    return (u128)3*x*x+(u128)3*d*x+(u128)d*d;
}
static u64 fx24(u64 d,u128 M){
    if(M<(u128)d*d)return 0;
    u128 disc=(u128)12*M-(u128)3*d*d;
    u64 s=isqrt128(disc),x=0;
    if(s>3*d)x=(s-3*d)/6;
    while(q24(d,x+1)<=M)++x;
    while(x&&q24(d,x)>M)--x;
    return x;
}

struct S24{
    u64 groups=0,triples=0,orient=0,k3=0,exact=0,hits=0;
};

static bool triple24(u64 D,const Rec&A,const Rec&B,const Rec&C,std::ostream&out,S24&st){
    const u64 a=A.x,au=A.y,b=B.x,bu=B.y,c=C.x,cu=C.y;
    u128 K=c3(b)-c3(a);
    if(K<(u128)D)return false;
    ++st.orient;
    auto rr=reps_from_known(a,b);
    if(rr.size()<3)return false;
    ++st.k3;
    for(auto [p,q]:rr){
        if(p<=a)continue;
        u128 E=c3(p)-c3(a);
        if(E==(u128)D)continue;
        ++st.exact;
        if(c3(q)-c3(b)!=E)throw std::runtime_error("K replay");
        u128 wc=c3(c)+E;u64 w=fcbrt(wc);if(c3(w)!=wc)continue;
        std::array<u64,9>z={a,w,bu,q,au,c,cu,b,p};
        std::set<u64>ss(z.begin(),z.end());if(ss.size()!=9||*ss.begin()==0)continue;
        std::array<u128,6>s={
            c3(z[0])+c3(z[1])+c3(z[2]),c3(z[3])+c3(z[4])+c3(z[5]),c3(z[6])+c3(z[7])+c3(z[8]),
            c3(z[0])+c3(z[3])+c3(z[6]),c3(z[1])+c3(z[4])+c3(z[7]),c3(z[2])+c3(z[5])+c3(z[8])};
        for(int i=1;i<6;i++)if(s[i]!=s[0])throw std::runtime_error("six sums");
        ++st.hits;out<<"HIT D="<<D<<" E="<<s128(E)<<"\n";return true;
    }
    return false;
}

int main(int argc,char**argv){
    if(argc!=4){std::cerr<<"usage: r24 LO HI OUT\n";return 2;}
    u64 L=std::stoull(argv[1]),R=std::stoull(argv[2]);if(!L||L>R)return 2;
    std::ofstream out(argv[3]);if(!out)return 3;
    auto t0=std::chrono::steady_clock::now();
    u64 dmax=fcbrt((u128)R+1);if(dmax)--dmax;
    std::vector<Rec>v;
    for(u64 d=1;d<=dmax;d++){
        u128 Mlo=((u128)L+d-1)/d,Mhi=(u128)R/d;if(Mlo>Mhi)continue;
        u64 xmin=fx24(d,Mlo-1)+1;if(xmin<1)xmin=1;u64 xmax=fx24(d,Mhi);if(xmin>xmax)continue;
        for(u64 x=xmin;x<=xmax;x++){
            u64 y=x+d;if(y>0xffffffffULL)return 13;
            u128 DD=(u128)d*q24(d,x);if(DD<L||DD>R||DD>UINT64_MAX)return 14;
            v.push_back({(u64)DD,(uint32_t)x,(uint32_t)y});
        }
    }
    std::sort(v.begin(),v.end());S24 st;size_t maxm=0;
    for(size_t i=0;i<v.size();){
        size_t j=i+1;while(j<v.size()&&v[j].d==v[i].d)++j;size_t m=j-i;maxm=std::max(maxm,m);
        if(m>=3){
            ++st.groups;
            for(size_t a=i;a<j;a++)for(size_t b=a+1;b<j;b++)for(size_t c=b+1;c<j;c++){
                ++st.triples;triple24(v[i].d,v[a],v[b],v[c],out,st);
            }
        }
        i=j;
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT lo="<<L<<" hi="<<R<<" rec="<<v.size()<<" groups="<<st.groups<<" triples="<<st.triples
       <<" orient="<<st.orient<<" k3="<<st.k3<<" exact="<<st.exact<<" hits="<<st.hits<<" max="<<maxm<<" ms="<<ms<<"\n";
    std::cerr<<"STAT rec="<<v.size()<<" groups="<<st.groups<<" triples="<<st.triples<<" orient="<<st.orient
             <<" k3="<<st.k3<<" exact="<<st.exact<<" hits="<<st.hits<<" ms="<<ms<<"\n";
    return st.hits?10:0;
}
