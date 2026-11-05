#define main d1_old_main
#include "d1.cpp"
#undef main

static inline u128 qdx(u64 d, u64 x) {
  return (u128)3*x*x + (u128)3*d*x + (u128)d*d;
}

// Largest x >= 0 such that 3*x^2 + 3*d*x + d^2 <= M.
static u64 floor_x_for_m(u64 d, u128 M) {
  const u128 d2 = (u128)d*d;
  if (M < d2) return 0;
  const u128 disc = (u128)12*M - (u128)3*d2;
  const u64 s = isqrt128(disc);
  u64 x = 0;
  if (s > 3*d) x = (s - 3*d)/6;
  while (qdx(d, x+1) <= M) ++x;
  while (x && qdx(d, x) > M) --x;
  return x;
}

int main(int argc, char** argv) {
  if (argc < 4) {
    std::cerr << "usage: d2 LO HI OUT [reserve_records] [hardcap_records]\n";
    return 2;
  }
  const u64 L = std::stoull(argv[1]);
  const u64 R = std::stoull(argv[2]);
  if (L == 0 || L > R) return 2;
  const u64 reserve_records = argc >= 5 ? std::stoull(argv[4]) : 0;
  const u64 hardcap_records = argc >= 6 ? std::stoull(argv[5]) : 0;
  std::ofstream out(argv[3]);
  const auto t0 = std::chrono::steady_clock::now();

  // If y=x+d and x>=1, then the smallest value for a fixed d is
  // (d+1)^3-1.  Hence d only needs to run to cbrt(R+1)-1.
  u64 dmax = fcbrt((u128)R + 1);
  if (dmax) --dmax;

  std::vector<Rec> v;
  if (reserve_records) v.reserve((size_t)reserve_records);

  for (u64 d=1; d<=dmax; ++d) {
    const u128 Mlo = ((u128)L + d - 1) / d;
    const u128 Mhi = (u128)R / d;
    if (Mlo > Mhi) continue;

    u64 xmin = floor_x_for_m(d, Mlo - 1) + 1;
    if (xmin < 1) xmin = 1;
    const u64 xmax = floor_x_for_m(d, Mhi);
    if (xmin > xmax) continue;

    for (u64 x=xmin; x<=xmax; ++x) {
      const u64 y = x + d;
      if (y > 0xffffffffULL) {
        out << "RANGE_OVERFLOW d=" << d << " x=" << x << " y=" << y << "\n";
        return 13;
      }
      const u128 DD = (u128)d * qdx(d, x);
      if (DD < L || DD > R || DD > UINT64_MAX) {
        out << "ENUM_ERROR d=" << d << " x=" << x << "\n";
        return 14;
      }
      if (hardcap_records && v.size() >= hardcap_records) {
        out << "CAP lo=" << L << " hi=" << R << " rec=" << v.size() << "\n";
        return 12;
      }
      v.push_back({(u64)DD, (std::uint32_t)x, (std::uint32_t)y});
    }
  }

  std::sort(v.begin(), v.end());
  size_t groups=0, triples=0, maxm=0;
  bool hit=false;
  for (size_t i=0; i<v.size();) {
    size_t j=i+1;
    while (j<v.size() && v[j].d==v[i].d) ++j;
    const size_t m=j-i;
    if (m>=3) {
      ++groups;
      maxm=std::max(maxm,m);
      triples += m*(m-1)*(m-2)/6;
      if (test_group(v,i,j,out)) { hit=true; break; }
    }
    i=j;
  }

  const double sec = std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count();
  out << "STAT lo=" << L << " hi=" << R
      << " rec=" << v.size() << " groups=" << groups
      << " triples=" << triples << " max=" << maxm
      << " sec=" << sec << " hit=" << hit << "\n";
  std::cerr << "rec=" << v.size() << " groups=" << groups
            << " sec=" << sec << " hit=" << hit << "\n";
  return hit ? 10 : 0;
}
