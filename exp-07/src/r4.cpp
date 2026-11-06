#include <gmpxx.h>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <unordered_map>
#include <vector>

using namespace std;

struct Pt {
    mpq_class x, y;
    bool inf = false;
};

struct Rep {
    mpq_class d;
    int i, j;
    Pt p;
    uint32_t h1, h2;
};

Pt neg(Pt p) {
    if (!p.inf) p.y = -p.y;
    return p;
}

Pt add(const Pt& A, const Pt& B, const mpq_class& curve_b) {
    (void)curve_b;
    if (A.inf) return B;
    if (B.inf) return A;
    if (A.x == B.x && A.y == -B.y) return Pt{{}, {}, true};
    mpq_class s;
    if (A.x == B.x && A.y == B.y) {
        if (A.y == 0) return Pt{{}, {}, true};
        s = 3 * A.x * A.x / (2 * A.y);
    } else {
        s = (B.y - A.y) / (B.x - A.x);
    }
    Pt R;
    R.x = s*s - A.x - B.x;
    R.y = s*(A.x - R.x) - A.y;
    return R;
}

Pt mul(Pt P, int n, const mpq_class& B) {
    if (n < 0) {
        P = neg(P);
        n = -n;
    }
    Pt R{{}, {}, true};
    while (n) {
        if (n & 1) R = add(R, P, B);
        P = add(P, P, B);
        n >>= 1;
    }
    return R;
}

mpq_class Q(long a, long b = 1) {
    return mpq_class(a, b);
}

uint32_t modpow(uint64_t a, uint64_t e, uint32_t p) {
    uint64_t r = 1;
    while (e) {
        if (e & 1) r = r*a % p;
        a = a*a % p;
        e >>= 1;
    }
    return static_cast<uint32_t>(r);
}

bool qmod(const mpq_class& q, uint32_t p, uint32_t& out) {
    uint32_t n = mpz_fdiv_ui(q.get_num_mpz_t(), p);
    uint32_t d = mpz_fdiv_ui(q.get_den_mpz_t(), p);
    if (!d) return false;
    out = static_cast<uint64_t>(n) * modpow(d, p - 2, p) % p;
    return true;
}

struct Edge {
    long lo, hi, zlo, zhi;
    mpq_class M, a, K, B;
    Pt T, P;

    Edge(long l, long h, long zl, long zh)
        : lo(l), hi(h), zlo(zl), zhi(zh) {
        M = Q(l + h, 2);
        a = Q(h - l, h + l);
        K = 1 + 3*a*a;
        B = -27*K*K;
        T = {3*K, 9*K*a, false};

        mpq_class N = Q(zl + zh, 2);
        mpq_class m = N/M;
        mpq_class b = Q(zh - zl, zh + zl);
        P = {3*K/m, 9*K*b, false};

        if (T.y*T.y != T.x*T.x*T.x + B) throw runtime_error("bad T");
        if (P.y*P.y != P.x*P.x*P.x + B) throw runtime_error("bad P");
    }

    vector<Rep> gen(int R, uint64_t& bad) const {
        static constexpr uint32_t p1 = 1000000007u;
        static constexpr uint32_t p2 = 1000000009u;
        bad = 0;

        vector<Pt> mt(2*R + 1), mp(2*R + 1);
        for (int i = -R; i <= R; ++i) {
            mt[i + R] = mul(T, i, B);
            mp[i + R] = mul(P, i, B);
        }

        vector<Rep> out;
        out.reserve((2*R + 1)*(2*R + 1)/8);
        mpq_class top_d = Q(static_cast<long long>(hi)*hi*hi - static_cast<long long>(lo)*lo*lo);
        mpq_class M3 = M*M*M;
        mpq_class K2 = K*K;

        for (int i = -R; i <= R; ++i) {
            for (int j = -R; j <= R; ++j) {
                // Quotient by Z -> -Z, which has the same unordered pair and |difference|.
                if (i < 0 || (i == 0 && j <= 0)) continue;
                Pt Z = add(mt[i + R], mp[j + R], B);
                if (Z.inf || Z.x <= 0) continue;

                mpq_class ay = Z.y;
                if (ay < 0) ay = -ay;
                // Equivalent to both recovered endpoints being positive.
                if (ay >= 9*K) continue;

                mpq_class X3 = Z.x*Z.x*Z.x;
                mpq_class d = 2*M3*Z.y*(X3 + 216*K2)/(27*X3);
                if (d < 0) d = -d;
                if (d == top_d) continue;

                uint32_t h1, h2;
                if (!qmod(d, p1, h1) || !qmod(d, p2, h2)) {
                    ++bad;
                    continue;
                }
                out.push_back({d, i, j, Z, h1, h2});
            }
        }
        return out;
    }
};

struct Key {
    uint32_t a, b;
    bool operator==(const Key& o) const { return a == o.a && b == o.b; }
};

struct KH {
    size_t operator()(const Key& k) const {
        return (static_cast<uint64_t>(k.a) << 32) ^ k.b;
    }
};

bool check_sum(const vector<Rep>& A, const vector<Rep>& B, const vector<Rep>& C,
               const char* name) {
    static constexpr uint32_t p1 = 1000000007u;
    static constexpr uint32_t p2 = 1000000009u;

    unordered_multimap<Key, int, KH> index;
    index.reserve(C.size()*2 + 1);
    for (int k = 0; k < static_cast<int>(C.size()); ++k) {
        index.emplace(Key{C[k].h1, C[k].h2}, k);
    }

    uint64_t pairs = 0, modular_candidates = 0;
    for (const auto& a : A) {
        for (const auto& b : B) {
            ++pairs;
            Key key{
                static_cast<uint32_t>((static_cast<uint64_t>(a.h1) + b.h1) % p1),
                static_cast<uint32_t>((static_cast<uint64_t>(a.h2) + b.h2) % p2)
            };
            auto range = index.equal_range(key);
            for (auto it = range.first; it != range.second; ++it) {
                ++modular_candidates;
                const auto& c = C[it->second];
                if (a.d + b.d == c.d) {
                    cerr << "EXACT " << name << " coeff "
                         << a.i << ',' << a.j << " ; "
                         << b.i << ',' << b.j << " ; "
                         << c.i << ',' << c.j << '\n';
                    return true;
                }
            }
        }
    }

    cerr << name << " pairs=" << pairs
         << " modular_candidates=" << modular_candidates << '\n';
    return false;
}

int main(int argc, char** argv) {
    int R = argc > 1 ? stoi(argv[1]) : 20;
    if (R < 1) return 2;

    auto t0 = chrono::steady_clock::now();

    // Three fixed anchors and one independent nontrivial point on each curve.
    Edge AB(3, 36, 27, 30);
    Edge BC(36, 60, 8, 64);
    Edge AC(3, 60, 22, 59);

    uint64_t badA, badB, badC;
    auto A = AB.gen(R, badA);
    auto B = BC.gen(R, badB);
    auto C = AC.gen(R, badC);

    cerr << "R=" << R
         << " sizes AB=" << A.size()
         << " BC=" << B.size()
         << " AC=" << C.size()
         << " bad=" << badA << ',' << badB << ',' << badC
         << " gen_ms="
         << chrono::duration_cast<chrono::milliseconds>(chrono::steady_clock::now() - t0).count()
         << '\n';

    // A bad modular denominator means the modular sieve is not a complete
    // certificate for this R.  Fail closed rather than silently dropping it.
    if (badA || badB || badC) {
        cerr << "INCOMPLETE: modular denominator encountered\n";
        return 3;
    }

    if (check_sum(B, C, A, "AB=BC+AC")) return 10;
    if (check_sum(C, A, B, "BC=AC+AB")) return 10;
    if (check_sum(B, A, C, "AC=BC+AB")) return 10;

    cerr << "NO_HIT total_ms="
         << chrono::duration_cast<chrono::milliseconds>(chrono::steady_clock::now() - t0).count()
         << '\n';
    return 0;
}
