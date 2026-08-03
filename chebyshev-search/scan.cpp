#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <numeric>
#include <random>
#include <sstream>
#include <string>
#include <vector>
#include <boost/multiprecision/cpp_int.hpp>

using u64 = std::uint64_t;
using u128 = unsigned __int128;
using u256 = boost::multiprecision::uint256_t;
using boost::multiprecision::cpp_int;

static std::string to_string_u128(u128 x) {
    if (x == 0) return "0";
    std::string s;
    while (x) { s.push_back(char('0' + x % 10)); x /= 10; }
    std::reverse(s.begin(), s.end());
    return s;
}

static u128 parse_u128(const std::string& s) {
    u128 x = 0;
    bool any = false;
    for (unsigned char c : s) {
        if (c >= '0' && c <= '9') { x = x * 10 + (c - '0'); any = true; }
        else if (any) break;
    }
    return x;
}

static u128 gcd128(u128 a, u128 b) {
    while (b) { u128 t = a % b; a = b; b = t; }
    return a;
}

static u128 mul_mod128(u128 a, u128 b, u128 m) {
    u256 z = u256(a) * u256(b);
    z %= u256(m);
    return static_cast<u128>(z);
}

static u128 pow_mod128(u128 a, u128 e, u128 m) {
    u128 r = 1 % m;
    while (e) {
        if (e & 1) r = mul_mod128(r, a, m);
        e >>= 1;
        if (e) a = mul_mod128(a, a, m);
    }
    return r;
}

static bool is_prime128(u128 n) {
    if (n < 2) return false;
    static constexpr u64 small[] = {2,3,5,7,11,13,17,19,23,29,31,37};
    for (u64 p : small) {
        if (n % p == 0) return n == p;
    }
    u128 d = n - 1;
    unsigned s = 0;
    while ((d & 1) == 0) { d >>= 1; ++s; }
    for (u64 a0 : small) {
        if (u128(a0) >= n) continue;
        u128 x = pow_mod128(a0, d, n);
        if (x == 1 || x == n - 1) continue;
        bool witness = true;
        for (unsigned j = 1; j < s; ++j) {
            x = mul_mod128(x, x, n);
            if (x == n - 1) { witness = false; break; }
        }
        if (witness) return false;
    }
    return true;
}

static u128 absdiff(u128 a, u128 b) { return a > b ? a - b : b - a; }

static u128 pollard_brent(u128 n, u64 seed) {
    if (n % 2 == 0) return 2;
    if (n % 3 == 0) return 3;
    std::mt19937_64 rng(seed ^ u64(n) ^ u64(n >> 64));
    for (unsigned restart = 0; restart < 64; ++restart) {
        u128 y = 2 + u128(rng()) % (n - 3);
        u128 c = 1 + u128(rng()) % (n - 1);
        u128 m = 64 + (rng() & 127);
        u128 g = 1, r = 1, q = 1, x = 0, ys = 0;
        auto f = [&](u128 v) { return (mul_mod128(v, v, n) + c) % n; };
        while (g == 1) {
            x = y;
            for (u128 i = 0; i < r; ++i) y = f(y);
            q = 1;
            for (u128 k = 0; k < r && g == 1; k += m) {
                ys = y;
                u128 lim = std::min(m, r - k);
                for (u128 i = 0; i < lim; ++i) {
                    y = f(y);
                    u128 d = absdiff(x, y);
                    if (d == 0) d = n;
                    q = mul_mod128(q, d, n);
                }
                g = gcd128(q, n);
            }
            r <<= 1;
        }
        if (g == n) {
            do {
                ys = f(ys);
                g = gcd128(absdiff(x, ys), n);
            } while (g == 1);
        }
        if (g != n && g != 1) return g;
    }
    return 0;
}

static void factor_rec(u128 n, std::vector<u128>& out, u64 seed) {
    if (n == 1) return;
    if (is_prime128(n)) { out.push_back(n); return; }
    u128 d = 0;
    for (u64 k = 0; k < 128 && (d == 0 || d == n); ++k)
        d = pollard_brent(n, seed + 0x9e3779b97f4a7c15ULL * (k + 1));
    if (d == 0 || d == n) throw std::runtime_error("Pollard rho failed on " + to_string_u128(n));
    factor_rec(d, out, seed + 1);
    factor_rec(n / d, out, seed + 2);
}

static std::vector<unsigned> sieve_primes(unsigned limit) {
    std::vector<bool> is(limit + 1, true);
    is[0] = false;
    if (limit >= 1) is[1] = false;
    for (unsigned i = 2; i * 1ULL * i <= limit; ++i)
        if (is[i]) for (unsigned j = i*i; j <= limit; j += i) is[j] = false;
    std::vector<unsigned> ps;
    for (unsigned i = 2; i <= limit; ++i) if (is[i]) ps.push_back(i);
    return ps;
}

static unsigned smallest_r(u128 n, const std::vector<unsigned>& primes) {
    for (unsigned r : primes) {
        if (r == 2) continue;
        u64 a = static_cast<u64>(n % r);
        if (a != 0 && (u64(a) * a) % r != 1) return r;
    }
    throw std::runtime_error("r search bound exhausted for n=" + to_string_u128(n));
}

using Poly = std::vector<u64>;

static Poly mul_poly(const Poly& a, const Poly& b, u64 mod) {
    const std::size_t r = a.size();
    std::vector<u128> acc(r, 0);
    for (std::size_t i = 0; i < r; ++i) if (a[i])
        for (std::size_t j = 0; j < r; ++j) if (b[j])
            acc[(i + j) % r] += u128(a[i]) * b[j];
    Poly c(r);
    for (std::size_t i = 0; i < r; ++i) c[i] = static_cast<u64>(acc[i] % mod);
    return c;
}

static Poly twice_minus_basis(Poly a, std::size_t idx, u64 mod) {
    for (u64& v : a) v = static_cast<u64>((u128(2) * v) % mod);
    a[idx] = (a[idx] + mod - 1) % mod;
    return a;
}

static bool local_check_poly(u128 n, u64 p, unsigned r) {
    const u128 m = n / p;
    Poly A(r, 0), B(r, 0);
    A[0] = 1 % p;
    B[1 % r] = 1 % p;
    int top = 127;
    while (top > 0 && ((m >> top) & 1) == 0) --top;
    for (int bit = top; bit >= 0; --bit) {
        Poly AA = mul_poly(A, A, p);
        Poly AB = mul_poly(A, B, p);
        Poly BB = mul_poly(B, B, p);
        Poly C0 = twice_minus_basis(std::move(AA), 0, p);
        Poly C1 = twice_minus_basis(std::move(AB), 1 % r, p);
        Poly C2 = twice_minus_basis(std::move(BB), 0, p);
        if ((m >> bit) & 1) { A = std::move(C1); B = std::move(C2); }
        else { A = std::move(C0); B = std::move(C1); }
    }
    std::size_t target = static_cast<std::size_t>(m % r);
    for (std::size_t i = 0; i < r; ++i) {
        u64 want = (i == target ? 1 % p : 0);
        if (A[i] != want) return false;
    }
    return true;
}

static bool local_check_r5_formula(u128 n, u64 p) {
    u256 P = p;
    u256 p2 = P * P;
    u256 p3 = p2 * P;
    u256 p4 = p2 * p2;
    u256 p5 = p4 * P;
    u256 p7 = p5 * p2;
    u256 M = 5 * (p4 + 1) / 2;
    u256 N = u256(n) % M;
    return N == (P % M) || N == (p3 % M) || N == (p5 % M) || N == (p7 % M);
}

using Poly128 = std::vector<u128>;

static Poly128 mul_poly128(const Poly128& a, const Poly128& b, u128 mod) {
    const std::size_t r = a.size();
    std::vector<u256> acc(r, 0);
    for (std::size_t i = 0; i < r; ++i) if (a[i])
        for (std::size_t j = 0; j < r; ++j) if (b[j])
            acc[(i + j) % r] += u256(a[i]) * u256(b[j]);
    Poly128 c(r);
    const u256 M(mod);
    for (std::size_t i = 0; i < r; ++i) c[i] = static_cast<u128>(acc[i] % M);
    return c;
}

static Poly128 twice_minus_basis128(Poly128 a, std::size_t idx, u128 mod) {
    const u256 M(mod);
    for (u128& v : a) v = static_cast<u128>((u256(2) * u256(v)) % M);
    a[idx] = (a[idx] + mod - 1) % mod;
    return a;
}

static bool cheb_check_poly128(u128 exponent, u128 mod, unsigned r) {
    Poly128 A(r, 0), B(r, 0);
    A[0] = 1 % mod;
    B[1 % r] = 1 % mod;
    int top = 127;
    while (top > 0 && ((exponent >> top) & 1) == 0) --top;
    for (int bit = top; bit >= 0; --bit) {
        Poly128 AA = mul_poly128(A, A, mod);
        Poly128 AB = mul_poly128(A, B, mod);
        Poly128 BB = mul_poly128(B, B, mod);
        Poly128 C0 = twice_minus_basis128(std::move(AA), 0, mod);
        Poly128 C1 = twice_minus_basis128(std::move(AB), 1 % r, mod);
        Poly128 C2 = twice_minus_basis128(std::move(BB), 0, mod);
        if ((exponent >> bit) & 1) { A = std::move(C1); B = std::move(C2); }
        else { A = std::move(C0); B = std::move(C1); }
    }
    const std::size_t target = static_cast<std::size_t>(exponent % r);
    for (std::size_t i = 0; i < r; ++i) {
        const u128 want = (i == target ? 1 % mod : 0);
        if (A[i] != want) return false;
    }
    return true;
}

static bool local_check_poly_any(u128 n, u128 p, unsigned r) {
    const u128 m = n / p;
    if (p <= u128(100000000000ULL)) return local_check_poly(n, static_cast<u64>(p), r);
    return cheb_check_poly128(m, p, r);
}

static bool local_check_r5_formula_any(u128 n, u128 p) {
    if (p > u128(100000000000ULL)) return local_check_poly_any(n, p, 5);
    return local_check_r5_formula(n, static_cast<u64>(p));
}

static bool check_local(u128 n, u128 p, unsigned r, bool& used_r5) {
    used_r5 = (r == 5 && (p % 5 == 2 || p % 5 == 3));
    if (used_r5) return local_check_r5_formula_any(n, p);
    return local_check_poly_any(n, p, r);
}

struct Counters {
    u64 lines = 0, processed = 0, malformed = 0;
    u64 rejected_r5 = 0, rejected_poly = 0, passed_factor = 0;
    u64 factor_fail = 0, full_candidates = 0;
    unsigned max_r = 0;
    std::array<u64, 101> r_hist{};
};

static std::string json_escape(const std::string& s) {
    std::string o;
    for (char c : s) {
        if (c == '"' || c == '\\') { o.push_back('\\'); o.push_back(c); }
        else if (c == '\n') o += "\\n";
        else o.push_back(c);
    }
    return o;
}

static std::string factors_json(const std::vector<u128>& fs) {
    std::ostringstream os; os << '[';
    for (std::size_t i=0;i<fs.size();++i) { if(i) os<<','; os << '"' << to_string_u128(fs[i]) << '"'; }
    os << ']'; return os.str();
}

int main(int argc, char** argv) {
    unsigned shard = 0, shards = 1;
    std::string output = "result.json";
    u64 max_processed = 0;
    for (int i=1;i<argc;++i) {
        std::string a=argv[i];
        if(a=="--shard" && i+1<argc) shard=std::stoul(argv[++i]);
        else if(a=="--shards" && i+1<argc) shards=std::stoul(argv[++i]);
        else if(a=="--output" && i+1<argc) output=argv[++i];
        else if(a=="--max-processed" && i+1<argc) max_processed=std::stoull(argv[++i]);
        else { std::cerr << "Unknown argument: " << a << "\n"; return 2; }
    }
    if(shard>=shards || shards==0) { std::cerr<<"bad shard\n"; return 2; }

    const auto trial_primes = sieve_primes(10000);
    const auto r_primes = sieve_primes(100000);
    Counters c;
    std::vector<std::string> candidate_rows, errors;
    std::string tok;
    const auto started = std::chrono::steady_clock::now();

    while (std::cin >> tok) {
        u64 line_idx = c.lines++;
        if (line_idx % shards != shard) continue;
        if (max_processed && c.processed >= max_processed) break;
        u128 n = parse_u128(tok);
        if (n <= 3 || (n & 1) == 0) { ++c.malformed; continue; }
        ++c.processed;
        bool rejected = false;
        try {
            unsigned r = smallest_r(n, r_primes);
            c.max_r = std::max(c.max_r, r);
            if (r <= 100) c.r_hist[r]++;

            u128 rem = n;
            std::vector<u128> factors;
            for (unsigned pp : trial_primes) {
                u128 p = pp;
                if (p * p > rem) break;
                if (rem % p == 0) {
                    do { factors.push_back(p); rem /= p; } while (rem % p == 0);
                    bool used_r5 = false;
                    bool ok = check_local(n, p, r, used_r5);
                    if (!ok) {
                        if (used_r5) ++c.rejected_r5; else ++c.rejected_poly;
                        rejected = true; break;
                    }
                    ++c.passed_factor;
                }
            }
            if (rejected) continue;

            if (rem > 1) {
                std::vector<u128> tail;
                factor_rec(rem, tail, u64(n) ^ u64(n >> 64) ^ line_idx);
                std::sort(tail.begin(), tail.end());
                for (u128 q : tail) {
                    factors.push_back(q);
                    bool used_r5 = false;
                    bool ok = check_local(n, q, r, used_r5);
                    if (!ok) {
                        if (used_r5) ++c.rejected_r5; else ++c.rejected_poly;
                        rejected = true; break;
                    }
                    ++c.passed_factor;
                }
            }
            if (rejected) continue;
            std::sort(factors.begin(), factors.end());
            u128 product = 1;
            for (std::size_t i = 0; i < factors.size(); ++i) {
                if (i && factors[i] == factors[i-1]) throw std::runtime_error("dataset entry is not squarefree");
                product *= factors[i];
            }
            if (product != n) throw std::runtime_error("factor product mismatch");
            if (!cheb_check_poly128(n, n, r)) throw std::runtime_error("CRT-local checks passed but direct check failed");
            ++c.full_candidates;
            std::ostringstream row;
            row << "{\"n\":\"" << to_string_u128(n) << "\",\"r\":" << r
                << ",\"factors\":" << factors_json(factors) << "}";
            candidate_rows.push_back(row.str());
            std::cerr << "CANDIDATE n=" << to_string_u128(n) << " r=" << r << "\n";
        } catch (const std::exception& e) {
            ++c.factor_fail;
            if (errors.size() < 100) {
                std::ostringstream er;
                er << "{\"n\":\"" << to_string_u128(n) << "\",\"error\":\"" << json_escape(e.what()) << "\"}";
                errors.push_back(er.str());
            }
        }
        if (c.processed % 100000 == 0) {
            auto sec = std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
            std::cerr << "shard=" << shard << " processed=" << c.processed << " rate=" << (c.processed/sec) << "/s candidates=" << c.full_candidates << " errors=" << c.factor_fail << "\n";
        }
    }

    auto elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now()-started).count();
    std::ofstream os(output);
    os << "{\n  \"shard\":" << shard << ",\n  \"shards\":" << shards
       << ",\n  \"lines_seen\":" << c.lines << ",\n  \"processed\":" << c.processed
       << ",\n  \"elapsed_seconds\":" << elapsed << ",\n  \"max_r\":" << c.max_r
       << ",\n  \"rejected_r5_formula\":" << c.rejected_r5
       << ",\n  \"rejected_polynomial\":" << c.rejected_poly
       << ",\n  \"passed_local_factor_checks\":" << c.passed_factor
       << ",\n  \"errors_count\":" << c.factor_fail
       << ",\n  \"candidates_count\":" << c.full_candidates << ",\n  \"r_histogram\":{";
    bool first=true;
    for(unsigned r=0;r<=100;++r) if(c.r_hist[r]) { if(!first) os<<','; first=false; os << "\""<<r<<"\":"<<c.r_hist[r]; }
    os << "},\n  \"candidates\":[";
    for(std::size_t i=0;i<candidate_rows.size();++i){if(i)os<<',';os<<candidate_rows[i];}
    os << "],\n  \"errors\":[";
    for(std::size_t i=0;i<errors.size();++i){if(i)os<<',';os<<errors[i];}
    os << "]\n}\n";
    std::cerr << "DONE shard=" << shard << " processed=" << c.processed << " elapsed=" << elapsed << " candidates=" << c.full_candidates << " errors=" << c.factor_fail << "\n";
    return 0;
}
