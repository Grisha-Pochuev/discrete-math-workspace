#include <cstdint>
#include <cmath>
#include <vector>
using I=__int128_t;
int64_t dist(const int64_t*x,int a,int b){I q=0;for(int k=0;k<3;k++){I d=I(x[3*a+k])-x[3*b+k];q+=d*d;}int64_t r=sqrtl((long double)q)/1000000;while(I(r+1)*(r+1)*1000000000000LL<=q)r++;while(I(r)*r*1000000000000LL>q)r--;return r+(4*q>=I(1000000000000LL)*(2*r+1)*(2*r+1));}
extern "C" int audit(int n,const int32_t*s,const int32_t*f,const int64_t*x,int32_t*t,int64_t*out){std::vector<char>seen(n);int cur=0;*out=0;for(int i=0;i<n;i++){if(cur<0||cur>=n||seen[cur])return 1;seen[cur]=1;t[i]=cur;int v=s[cur];if(v<0||v>=n)return 2;*out+=dist(x,cur,v);cur=v;}if(cur)return 3;for(int i=0;i<n;i++)for(int k=0;k<2;k++){int j=f[2*i+k];if(j>=0&&s[i]!=j&&s[j]!=i)return 4;}return 0;}
extern "C" int64_t fullcost(int n,const int32_t*t,const int64_t*x){int64_t out=0;for(int i=0;i<n;i++)out+=dist(x,t[i],t[(i+1)%n]);return out;}
extern "C" int walk(int n,const int32_t*a,int32_t*t){std::vector<char>s(n);int cur=0,prev=-1;for(int i=0;i<n;i++){if(cur<0||cur>=n||s[cur])return 1;s[cur]=1;t[i]=cur;int v=a[2*cur]==prev?a[2*cur+1]:a[2*cur];prev=cur;cur=v;}return cur!=0;}
