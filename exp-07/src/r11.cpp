// r11: search for two-parameter universal difference identities.
#define main r8_old_main
#include "r8.cpp"
#undef main

#include <tuple>

struct Sample {
    u32 p,x3;
    vector<u32> A,B,C;
};

static vector<Sample> build_samples(int M) {
    vector<Sample> out;
    auto primes=sieve_primes(1000000,4);
    static const int xy[][2]={{2,3},{2,5},{3,4},{3,7},{4,5},{5,7},{5,11},{7,8},{7,13},{11,13}};
    for(u32 p:primes) for(auto const& q:xy) {
        u32 x=q[0],y=q[1],z=mulp(x,y,p);
        Sample s; s.p=p; s.x3=mulp(mulp(x,x,p),x,p);
        s.A.assign(M+1,BAD);s.B.assign(M+1,BAD);s.C.assign(M+1,BAD);
        for(int m=1;m<=M;m++) {
            s.A[m]=dmod(x,m,p);
            s.B[m]=dmod(y,m,p);
            s.C[m]=dmod(z,m,p);
        }
        out.push_back(std::move(s));
    }
    return out;
}

static bool value(const Sample&s,int m,int n,int k,int sa,int sb,u32&v) {
    u32 A=s.A[m],B=s.B[n],C=s.C[k];
    if(A==BAD||B==BAD||C==BAD)return false;
    B=mulp(s.x3,B,s.p);
    v=C;
    v=sa>0?addp(v,A,s.p):subp(v,A,s.p);
    v=sb>0?addp(v,B,s.p):subp(v,B,s.p);
    return true;
}

int main(int argc,char**argv) {
    if(argc!=3){std::cerr<<"usage: r11 MAXM OUT\n";return 2;}
    int M=std::stoi(argv[1]);std::string outp=argv[2];
    if(M<3||M>200)return 2;
    auto t0=std::chrono::steady_clock::now();
    auto ss=build_samples(M);

    // Exact structural sanity check in modular form:
    // -(x^3-1)-x^3(y^3-1)+(x^3y^3-1)=0, i.e. m=n=k=1.
    size_t sanity_good=0;
    for(auto const&s:ss){u32 v;if(value(s,1,1,1,-1,-1,v)){sanity_good++;if(v!=0){std::cerr<<"SANITY_FAIL\n";return 12;}}}
    if(sanity_good<ss.size()/2){std::cerr<<"SANITY_UNDERSAMPLED\n";return 13;}

    std::ofstream out(outp);if(!out)return 3;
    u64 candidates=0,eliminated=0,unresolved=0,survivors=0;
    // Normalize the third sign to +1; global negation covers all 8 sign choices.
    for(int m=2;m<=M;m++) for(int n=2;n<=M;n++) for(int k=2;k<=M;k++)
      for(int sa:{-1,1}) for(int sb:{-1,1}) {
        candidates++;
        bool killed=false,good=false;
        int witness=-1;
        for(size_t i=0;i<ss.size();i++) {
            u32 v;
            if(!value(ss[i],m,n,k,sa,sb,v))continue;
            good=true;
            if(v!=0){killed=true;witness=(int)i;break;}
        }
        if(killed){eliminated++;continue;}
        if(!good){unresolved++;out<<"UNRESOLVED "<<m<<' '<<n<<' '<<k<<' '<<sa<<' '<<sb<<"\n";continue;}
        survivors++;
        out<<"SURVIVOR "<<m<<' '<<n<<' '<<k<<' '<<sa<<' '<<sb<<"\n";
    }
    auto ms=std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-t0).count();
    out<<"STAT M="<<M<<" samples="<<ss.size()<<" sanity="<<sanity_good
       <<" candidates="<<candidates<<" eliminated="<<eliminated
       <<" unresolved="<<unresolved<<" survivors="<<survivors<<" ms="<<ms<<"\n";
    std::cerr<<"STAT M="<<M<<" samples="<<ss.size()<<" sanity="<<sanity_good
             <<" candidates="<<candidates<<" eliminated="<<eliminated
             <<" unresolved="<<unresolved<<" survivors="<<survivors<<" ms="<<ms<<"\n";
    return (unresolved||survivors)?10:0;
}
