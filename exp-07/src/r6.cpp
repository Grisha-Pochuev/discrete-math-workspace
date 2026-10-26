#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <vector>

using namespace std;
using u32 = uint32_t;
using u64 = uint64_t;

static constexpr u32 P1 = 1000000007u;
static constexpr u32 P2 = 1000000009u;
static constexpr u32 BAD = 0xffffffffu;

inline u32 addp(u32 a,u32 b,u32 p){u64 s=(u64)a+b;if(s>=p)s-=p;return (u32)s;}
inline u32 subp(u32 a,u32 b,u32 p){return a>=b?a-b:(u32)((u64)a+p-b);}
inline u32 mulp(u32 a,u32 b,u32 p){return (u64)a*b%p;}
u32 powp(u32 a,u64 e,u32 p){u32 r=1;while(e){if(e&1)r=mulp(r,a,p);a=mulp(a,a,p);e>>=1;}return r;}
inline u32 normll(long long x,u32 p){long long r=x%(long long)p;if(r<0)r+=p;return (u32)r;}

pair<u32,u32> nd(u32 a,u32 b,u32 p){
    u32 A=mulp(mulp(a,a,p),a,p),B=mulp(mulp(b,b,p),b,p);
    u32 d=subp(B,A,p),s=addp(A,B,p);
    u32 r=mulp(d,d,p),t=mulp(s,s,p);
    u32 rp[9],tp[9];rp[0]=tp[0]=1;
    for(int i=1;i<=8;i++){rp[i]=mulp(rp[i-1],r,p);tp[i]=mulp(tp[i-1],t,p);}
    static const long long c[9]={1,1224,-67284,328536,-1115370,367416,1338444,-1417176,531441};
    u32 n=0;
    for(int i=0;i<=8;i++){
        u32 term=mulp(rp[8-i],tp[i],p);
        term=mulp(term,normll(c[i],p),p);
        n=addp(n,term,p);
    }
    u32 d2=r,d3=mulp(r,d,p),d4=mulp(r,r,p),s2=t,s4=mulp(t,t,p);
    u32 q=addp(d4,mulp(18,mulp(d2,s2,p),p),p);
    q=addp(q,mulp(normll(-27,p),s4,p),p);
    u32 den=mulp(64,mulp(d3,mulp(mulp(q,q,p),q,p),p),p);
    return {n,den};
}

u32 direct(u32 a,u32 b,u32 p,bool&ok){
    auto [n,d]=nd(a,b,p);
    if(!d){ok=false;return 0;}
    ok=true;
    return mulp(n,powp(d,p-2,p),p);
}

int main(int argc,char**argv){
    if(argc!=4){cerr<<"usage: r6 N part parts\n";return 2;}
    int N=stoi(argv[1]),part=stoi(argv[2]),parts=stoi(argv[3]);
    if(N<3||part<0||part>=parts)return 2;
    auto t0=chrono::steady_clock::now();
    vector<u32>D((size_t)(N+1)*(N+1),BAD);
    u64 bad=0;
    vector<u32>dens,nums,pref,pos;
    for(u32 b=2;b<=(u32)N;b++){
        dens.clear();nums.clear();pos.clear();
        for(u32 a=1;a<b;a++){
            auto [n,d]=nd(a,b,P1);
            if(!d){bad++;continue;}
            nums.push_back(n);dens.push_back(d);pos.push_back(a);
        }
        pref.resize(dens.size());
        u32 prod=1;
        for(size_t i=0;i<dens.size();i++){prod=mulp(prod,dens[i],P1);pref[i]=prod;}
        u32 inv=powp(prod,P1-2,P1);
        for(size_t ii=dens.size();ii-->0;){
            u32 before=ii?pref[ii-1]:1;
            u32 di=mulp(inv,before,P1);
            inv=mulp(inv,dens[ii],P1);
            D[(size_t)pos[ii]*(N+1)+b]=mulp(nums[ii],di,P1);
        }
    }

    u64 triples=0,p1cand=0,p2cand=0,p2bad=0;
    u64 signs[4]={0,0,0,0};
    for(u32 a=1;a+2<=(u32)N;a++) if((a-1)%parts==(u32)part){
        for(u32 b=a+1;b<(u32)N;b++){
            u32 x=D[(size_t)a*(N+1)+b];
            for(u32 c=b+1;c<=(u32)N;c++){
                triples++;
                u32 y=D[(size_t)b*(N+1)+c],z=D[(size_t)a*(N+1)+c];
                if(x==BAD||y==BAD||z==BAD){p2bad++;continue;}
                int mask=0;
                if(addp(x,y,P1)==z)mask|=1;
                if(addp(x,z,P1)==y)mask|=2;
                if(addp(y,z,P1)==x)mask|=4;
                if(addp(addp(x,y,P1),z,P1)==0)mask|=8;
                if(!mask)continue;
                p1cand++;

                bool o1,o2,o3;
                u32 X=direct(a,b,P2,o1),Y=direct(b,c,P2,o2),Z=direct(a,c,P2,o3);
                if(!(o1&&o2&&o3)){p2bad++;continue;}
                int mask2=0;
                if(addp(X,Y,P2)==Z)mask2|=1;
                if(addp(X,Z,P2)==Y)mask2|=2;
                if(addp(Y,Z,P2)==X)mask2|=4;
                if(addp(addp(X,Y,P2),Z,P2)==0)mask2|=8;
                int both=mask&mask2;
                if(both){
                    p2cand++;
                    cerr<<"SURVIVOR "<<a<<' '<<b<<' '<<c<<" mask="<<both<<"\n";
                    for(int k=0;k<4;k++)if(both&(1<<k))signs[k]++;
                }
            }
        }
    }
    auto ms=chrono::duration_cast<chrono::milliseconds>(chrono::steady_clock::now()-t0).count();
    cerr<<"STAT N="<<N<<" part="<<part<<" parts="<<parts
        <<" bad="<<bad<<" triples="<<triples<<" p1="<<p1cand
        <<" p2="<<p2cand<<" p2bad="<<p2bad
        <<" signs="<<signs[0]<<','<<signs[1]<<','<<signs[2]<<','<<signs[3]
        <<" ms="<<ms<<"\n";
    return p2cand?10:0;
}
