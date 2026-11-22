#include <bits/stdc++.h>
#include <omp.h>
using namespace std;
struct V{uint64_t m0=0,m1=0,m2=0;uint32_t code=0,pref=0;};
struct Opt{array<uint64_t,3> bits{};array<uint8_t,35> d{};};
struct KeyHash{size_t operator()(array<uint64_t,3> const&x)const noexcept{uint64_t h=x[0]*0x9e3779b97f4a7c15ULL;h^=x[1]+0x517cc1b727220a95ULL+(h<<6)+(h>>2);h^=x[2]+0x6eed0e9da4d94a4fULL+(h<<6)+(h>>2);return (size_t)h;}};
static uint64_t smix(uint64_t&x){x+=0x9e3779b97f4a7c15ULL;uint64_t z=x;z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;z=(z^(z>>27))*0x94d049bb133111ebULL;return z^(z>>31);}
int main(int ac,char**av){
 if(ac!=6){cerr<<"usage data seed block want out\n";return 1;}
 string path=av[1],outp=av[5];uint64_t seed=stoull(av[2]);int bid=stoi(av[3]),want=stoi(av[4]);if(bid<0||bid>=8||want<1)return 2;
 ifstream in(path,ios::binary);uint32_t R,N;in.read((char*)&R,4);in.read((char*)&N,4);if(R!=57||N!=1029)return 3;vector<uint32_t>q(R);in.read((char*)q.data(),4*R);vector<uint16_t>A((size_t)R*N);in.read((char*)A.data(),2*A.size());vector<uint8_t>x0(N);in.read((char*)x0.data(),N);if(!in)return 4;
 vector<int>perm(N);iota(perm.begin(),perm.end(),0);mt19937_64 pg(seed^0x62426b10ULL);shuffle(perm.begin(),perm.end(),pg);int lo=(int)((long long)bid*N/8),hi=(int)((long long)(bid+1)*N/8);vector<int>cols(perm.begin()+lo,perm.begin()+hi);int nb=cols.size();
 vector<uint8_t>M((size_t)R*(nb+1));
 for(int r=0;r<(int)R;r++){int t=0;for(int j=0;j<nb;j++){uint8_t z=A[(size_t)r*N+cols[j]]%3;M[(size_t)r*(nb+1)+j]=z;t+=z*x0[cols[j]];}M[(size_t)r*(nb+1)+nb]=t%3;}
 vector<int>piv;int row=0;
 for(int c=0;c<nb&&row<(int)R;c++){
  int z=row;while(z<(int)R&&!M[(size_t)z*(nb+1)+c])z++;if(z==(int)R)continue;
  if(z!=row)for(int j=0;j<=nb;j++)swap(M[(size_t)z*(nb+1)+j],M[(size_t)row*(nb+1)+j]);
  if(M[(size_t)row*(nb+1)+c]==2)for(int j=0;j<=nb;j++)M[(size_t)row*(nb+1)+j]=2*M[(size_t)row*(nb+1)+j]%3;
  for(int i=0;i<(int)R;i++)if(i!=row){int w=M[(size_t)i*(nb+1)+c];if(w)for(int j=0;j<=nb;j++)M[(size_t)i*(nb+1)+j]=(M[(size_t)i*(nb+1)+j]+6-w*M[(size_t)row*(nb+1)+j])%3;}
  piv.push_back(c);row++;
 }
 if(row!=57){cerr<<"rank="<<row<<"\n";return 5;}
 for(int r=0;r<57;r++)for(int s=0;s<57;s++)if(M[(size_t)r*(nb+1)+piv[s]]!=(r==s))return 6;
 vector<char>isp(nb);for(int z:piv)isp[z]=1;vector<int>fre;for(int j=0;j<nb;j++)if(!isp[j])fre.push_back(j);if((int)fre.size()<34)return 7;
 shuffle(fre.begin(),fre.end(),pg);const int T=34,H=17,D=10,BC=59049,AL=1024,LN=1<<H;
 vector<int>adj(fre.begin(),fre.begin()+T),bg(fre.begin()+T,fre.end());
 auto mk=[&](int off){vector<V>L(LN);vector<array<uint8_t,57>>val(LN);for(int id=0;id<LN;id++){if(id){int bit=__builtin_ctz((unsigned)id),pr=id&(id-1);val[id]=val[pr];int lc=adj[off+bit];for(int r=0;r<57;r++)val[id][r]=(val[id][r]+M[(size_t)r*(nb+1)+lc])%3;}V v;v.code=id;int pc=0,mul=1;for(int r=0;r<57;r++){int z=val[id][r];if(z==0)v.m0|=1ULL<<r;else if(z==1)v.m1|=1ULL<<r;else v.m2|=1ULL<<r;if(r<D){pc+=z*mul;mul*=3;}}v.pref=pc;L[id]=v;}return L;};
 vector<V>L1=mk(0),L2=mk(H);vector<int>cnt(BC),ofs(BC+1),ids(LN);for(auto&v:L2)cnt[v.pref]++;for(int i=0;i<BC;i++)ofs[i+1]=ofs[i]+cnt[i];vector<int>pos=ofs;for(int i=0;i<LN;i++)ids[pos[L2[i].pref]++]=i;
 vector<uint16_t>allow((size_t)BC*AL);vector<array<uint8_t,D>>dig(BC);for(int c=0;c<BC;c++){int z=c;for(int j=0;j<D;j++){dig[c][j]=z%3;z/=3;}}
 #pragma omp parallel for schedule(static)
 for(int f=0;f<BC;f++){uint16_t*out=&allow[(size_t)f*AL];for(int mask=0;mask<AL;mask++){int code=0,mul=1;for(int j=0;j<D;j++){int z=(dig[f][j]+1+((mask>>j)&1))%3;code+=z*mul;mul*=3;}out[mask]=code;}}
 vector<int>liftRows;for(int r=0;r<57;r++)if(q[r]>3)liftRows.push_back(r);int nd=0;for(int r:liftRows){uint32_t z=q[r]/3;while(z>1){nd++;z/=3;}}if(nd!=35)return 8;
 vector<Opt>opts;opts.reserve(want);unordered_set<array<uint64_t,3>,KeyHash>seen;mutex mu;atomic<unsigned long long>attempts(0),checks(0);
 auto addopt=[&](vector<uint8_t> const&y){Opt o;for(int j=0;j<nb;j++)if(y[j])o.bits[j>>6]|=1ULL<<(j&63);int di=0;for(int r:liftRows){long long dlt=0;for(int j=0;j<nb;j++)dlt+=(long long)A[(size_t)r*N+cols[j]]*((int)y[j]-(int)x0[cols[j]]);if(dlt%3){cerr<<"div\n";abort();}int mod=q[r]/3;long long z=(dlt/3)%mod;if(z<0)z+=mod;while(mod>1){o.d[di++]=z%3;z/=3;mod/=3;}}lock_guard<mutex>lk(mu);if((int)opts.size()<want&&seen.insert(o.bits).second)opts.push_back(o);};
 {vector<uint8_t>y(nb);for(int j=0;j<nb;j++)y[j]=x0[cols[j]];addopt(y);}
 double st=omp_get_wtime();
 #pragma omp parallel
 {
  uint64_t sr=seed^((uint64_t)bid<<48)^0x63d83595ULL^(uint64_t)(omp_get_thread_num()+1)*0x9e3779b97f4a7c15ULL;
  vector<uint8_t>fv(fre.size()),y(nb);array<uint8_t,57>c{};
  while(true){
   {lock_guard<mutex>lk(mu);if((int)opts.size()>=want)break;}
   attempts.fetch_add(1,memory_order_relaxed);for(int j=0;j<(int)bg.size();j++)fv[T+j]=smix(sr)&1;
   for(int r=0;r<57;r++){int s=0;for(int j=0;j<(int)bg.size();j++)if(fv[T+j])s+=M[(size_t)r*(nb+1)+bg[j]];c[r]=(M[(size_t)r*(nb+1)+nb]+3-s%3)%3;}
   int fia=-1,fib=-1;unsigned long long lc=0;
   uint64_t start=smix(sr)&(LN-1);
   for(int zz=0;zz<LN&&fia<0;zz++){int ia=(start+zz)&(LN-1);auto&a=L1[ia];uint64_t F[3]={0,0,0};int fc=0,mul=1;for(int r=0;r<57;r++){int av=(a.m1>>r&1)?1:((a.m2>>r&1)?2:0);int z=(c[r]-av+1)%3;if(z<0)z+=3;F[z]|=1ULL<<r;if(r<D){fc+=z*mul;mul*=3;}}auto al=&allow[(size_t)fc*AL];for(int z=0;z<AL&&fia<0;z++){int bc=al[z];for(int pp=ofs[bc];pp<ofs[bc+1];pp++){int ib=ids[pp];auto&bb=L2[ib];lc++;if(((bb.m0&F[0])|(bb.m1&F[1])|(bb.m2&F[2]))==0){fia=ia;fib=ib;break;}}}}
   checks.fetch_add(lc,memory_order_relaxed);if(fia<0)continue;uint32_t a=L1[fia].code,b=L2[fib].code;for(int j=0;j<T;j++)fv[j]=(j<H)?((a>>j)&1):((b>>(j-H))&1);fill(y.begin(),y.end(),0);for(int j=0;j<T;j++)y[adj[j]]=fv[j];for(int j=0;j<(int)bg.size();j++)y[bg[j]]=fv[T+j];bool ok=1;for(int r=0;r<57;r++){int s=0;for(int j:fre)if(y[j])s+=M[(size_t)r*(nb+1)+j];int z=(M[(size_t)r*(nb+1)+nb]+3-s%3)%3;if(z>1){ok=0;break;}y[piv[r]]=z;}if(!ok)abort();for(int r=0;r<57;r++){int s=0;for(int j=0;j<nb;j++)s+=(A[(size_t)r*N+cols[j]]%3)*y[j];int t=0;for(int j=0;j<nb;j++)t+=(A[(size_t)r*N+cols[j]]%3)*x0[cols[j]];if((s-t)%3){cerr<<"verify\n";abort();}}addopt(y);
   if(omp_get_thread_num()==0&&attempts.load()%64==0){lock_guard<mutex>lk(mu);cerr<<"b="<<bid<<" o="<<opts.size()<<" a="<<attempts.load()<<" sec="<<omp_get_wtime()-st<<"\n";}
  }
 }
 cerr<<"DONE b="<<bid<<" o="<<opts.size()<<" a="<<attempts.load()<<" checks="<<checks.load()<<" sec="<<omp_get_wtime()-st<<"\n";
 ofstream out(outp,ios::binary);uint32_t magic=0x62336231,bb=bid,nn=nb,oo=opts.size(),dd=35;out.write((char*)&magic,4);out.write((char*)&bb,4);out.write((char*)&nn,4);out.write((char*)&oo,4);out.write((char*)&dd,4);for(int z:cols){uint16_t w=z;out.write((char*)&w,2);}for(auto&o:opts){out.write((char*)o.bits.data(),24);out.write((char*)o.d.data(),35);}return out?0:9;
}
