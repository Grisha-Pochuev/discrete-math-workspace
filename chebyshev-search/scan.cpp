#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <boost/multiprecision/cpp_int.hpp>

using u64 = std::uint64_t;
using u128 = unsigned __int128;
using u256 = boost::multiprecision::uint256_t;

static std::string to_string_u128(u128 x) {
    if (x == 0) return "0";
    std::string s;
    while (x) { s.push_back(char('0' + x % 10)); x /= 10; }
    std::reverse(s.begin(), s.end());
    return s;
}

static bool parse_u128_strict(const std::string& s, u128& out) {
    if (s.empty()) return false;
    u128 x = 0;
    for (unsigned char c : s) {
        if (c < '0' || c > '9') return false;
        const unsigned d = c - '0';
        const u128 next = x * 10 + d;
        if (next < x) return false;
        x = next;
    }
    out = x;
    return true;
}

static u128 mul_mod128(u128 a, u128 b, u128 mod) {
    return static_cast<u128>((u256(a) * u256(b)) % u256(mod));
}

static u128 pow_mod128(u128 a, u128 e, u128 mod) {
    u128 result = 1 % mod;
    while (e) {
        if (e & 1) result = mul_mod128(result, a, mod);
        e >>= 1;
        if (e) a = mul_mod128(a, a, mod);
    }
    return result;
}

static bool is_prime128(u128 n) {
    if (n < 2) return false;
    static constexpr u64 bases[] = {2,3,5,7,11,13,17,19,23,29,31,37,41};
    for (u64 p : bases) {
        if (n % p == 0) return n == p;
    }
    u128 d = n - 1;
    unsigned s = 0;
    while ((d & 1) == 0) { d >>= 1; ++s; }
    for (u64 a0 : bases) {
        if (u128(a0) >= n) continue;
        u128 x = pow_mod128(a0, d, n);
        if (x == 1 || x == n - 1) continue;
        bool composite = true;
        for (unsigned j = 1; j < s; ++j) {
            x = mul_mod128(x, x, n);
            if (x == n - 1) { composite = false; break; }
        }
        if (composite) return false;
    }
    return true;
}

static std::vector<unsigned> sieve_primes(unsigned limit) {
    std::vector<bool> prime(limit + 1, true);
    prime[0] = false;
    if (limit >= 1) prime[1] = false;
    for (unsigned i = 2; u64(i) * i <= limit; ++i)
        if (prime[i]) for (unsigned j = i * i; j <= limit; j += i) prime[j] = false;
    std::vector<unsigned> result;
    for (unsigned i = 2; i <= limit; ++i) if (prime[i]) result.push_back(i);
    return result;
}

static unsigned smallest_r(u128 n, const std::vector<unsigned>& primes) {
    for (unsigned r : primes) {
        if (r == 2) continue;
        const u64 a = static_cast<u64>(n % r);
        if (a != 0 && (u64(a) * a) % r != 1) return r;
    }
    throw std::runtime_error("r search bound exhausted for n=" + to_string_u128(n));
}

using Poly64 = std::vector<u64>;

static Poly64 multiply64(const Poly64& a, const Poly64& b, u64 mod) {
    const std::size_t r = a.size();
    std::vector<u128> acc(r, 0);
    for (std::size_t i = 0; i < r; ++i) if (a[i])
        for (std::size_t j = 0; j < r; ++j) if (b[j])
            acc[(i + j) % r] += u128(a[i]) * b[j];
    Poly64 result(r);
    for (std::size_t i = 0; i < r; ++i) result[i] = static_cast<u64>(acc[i] % mod);
    return result;
}

static Poly64 twice_minus_basis64(Poly64 a, std::size_t index, u64 mod) {
    for (u64& v : a) v = static_cast<u64>((u128(2) * v) % mod);
    a[index] = (a[index] + mod - 1) % mod;
    return a;
}

static bool chebyshev_check64(u128 exponent, u64 mod, unsigned r) {
    Poly64 a(r, 0), b(r, 0);
    a[0] = 1 % mod;
    b[1 % r] = 1 % mod;
    int top = 127;
    while (top > 0 && ((exponent >> top) & 1) == 0) --top;
    for (int bit = top; bit >= 0; --bit) {
        Poly64 aa = multiply64(a, a, mod);
        Poly64 ab = multiply64(a, b, mod);
        Poly64 bb = multiply64(b, b, mod);
        Poly64 t2k  = twice_minus_basis64(std::move(aa), 0, mod);
        Poly64 t2k1 = twice_minus_basis64(std::move(ab), 1 % r, mod);
        Poly64 t2k2 = twice_minus_basis64(std::move(bb), 0, mod);
        if ((exponent >> bit) & 1) { a = std::move(t2k1); b = std::move(t2k2); }
        else { a = std::move(t2k); b = std::move(t2k1); }
    }
    const std::size_t target = static_cast<std::size_t>(exponent % r);
    for (std::size_t i = 0; i < r; ++i) {
        const u64 want = (i == target ? 1 % mod : 0);
        if (a[i] != want) return false;
    }
    return true;
}

using Poly128 = std::vector<u128>;

static Poly128 multiply128(const Poly128& a, const Poly128& b, u128 mod) {
    const std::size_t r = a.size();
    std::vector<u256> acc(r, 0);
    for (std::size_t i = 0; i < r; ++i) if (a[i])
        for (std::size_t j = 0; j < r; ++j) if (b[j])
            acc[(i + j) % r] += u256(a[i]) * u256(b[j]);
    Poly128 result(r);
    const u256 m(mod);
    for (std::size_t i = 0; i < r; ++i) result[i] = static_cast<u128>(acc[i] % m);
    return result;
}

static Poly128 twice_minus_basis128(Poly128 a, std::size_t index, u128 mod) {
    const u256 m(mod);
    for (u128& v : a) v = static_cast<u128>((u256(2) * u256(v)) % m);
    a[index] = (a[index] + mod - 1) % mod;
    return a;
}

static bool chebyshev_check128(u128 exponent, u128 mod, unsigned r) {
    Poly128 a(r, 0), b(r, 0);
    a[0] = 1 % mod;
    b[1 % r] = 1 % mod;
    int top = 127;
    while (top > 0 && ((exponent >> top) & 1) == 0) --top;
    for (int bit = top; bit >= 0; --bit) {
        Poly128 aa = multiply128(a, a, mod);
        Poly128 ab = multiply128(a, b, mod);
        Poly128 bb = multiply128(b, b, mod);
        Poly128 t2k  = twice_minus_basis128(std::move(aa), 0, mod);
        Poly128 t2k1 = twice_minus_basis128(std::move(ab), 1 % r, mod);
        Poly128 t2k2 = twice_minus_basis128(std::move(bb), 0, mod);
        if ((exponent >> bit) & 1) { a = std::move(t2k1); b = std::move(t2k2); }
        else { a = std::move(t2k); b = std::move(t2k1); }
    }
    const std::size_t target = static_cast<std::size_t>(exponent % r);
    for (std::size_t i = 0; i < r; ++i) {
        const u128 want = (i == target ? 1 % mod : 0);
        if (a[i] != want) return false;
    }
    return true;
}

static bool local_check_polynomial(u128 n, u128 p, unsigned r) {
    const u128 exponent = n / p;
    if (p <= u128(100000000000ULL))
        return chebyshev_check64(exponent, static_cast<u64>(p), r);
    return chebyshev_check128(exponent, p, r);
}

static bool local_check_r5_formula(u128 n, u128 p) {
    if (p > u128(10000000000ULL)) return local_check_polynomial(n, p, 5);
    const u256 P(p);
    const u256 p2 = P * P;
    const u256 p3 = p2 * P;
    const u256 p4 = p2 * p2;
    const u256 p5 = p4 * P;
    const u256 p7 = p5 * p2;
    const u256 modulus = 5 * (p4 + 1) / 2;
    const u256 N = u256(n) % modulus;
    return N == P % modulus || N == p3 % modulus ||
           N == p5 % modulus || N == p7 % modulus;
}

static bool check_local(u128 n, u128 p, unsigned r, bool& used_formula) {
    used_formula = (r == 5 && (p % 5 == 2 || p % 5 == 3));
    return used_formula ? local_check_r5_formula(n, p)
                        : local_check_polynomial(n, p, r);
}

struct Counters {
    u64 lines = 0, processed = 0, malformed = 0;
    u64 rejected_r5 = 0, rejected_polynomial = 0, passed_local_factors = 0;
    u64 errors = 0, candidates = 0;
    unsigned max_r = 0;
    std::array<u64, 101> r_hist{};
    u128 first_n = 0, last_n = 0;
};

static std::string json_escape(const std::string& s) {
    std::string out;
    for (char c : s) {
        if (c == '"' || c == '\\') { out.push_back('\\'); out.push_back(c); }
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else out.push_back(c);
    }
    return out;
}

static std::string factors_json(const std::vector<u128>& factors) {
    std::ostringstream out;
    out << '[';
    for (std::size_t i = 0; i < factors.size(); ++i) {
        if (i) out << ',';
        out << '"' << to_string_u128(factors[i]) << '"';
    }
    out << ']';
    return out.str();
}

int main(int argc, char** argv) {
    unsigned shard = 0, shards = 1;
    std::string output = "result.json";
    u64 max_processed = 0;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        if (arg == "--shard" && i + 1 < argc) shard = std::stoul(argv[++i]);
        else if (arg == "--shards" && i + 1 < argc) shards = std::stoul(argv[++i]);
        else if (arg == "--output" && i + 1 < argc) output = argv[++i];
        else if (arg == "--max-processed" && i + 1 < argc) max_processed = std::stoull(argv[++i]);
        else { std::cerr << "Unknown argument: " << arg << '\n'; return 2; }
    }
    if (shards == 0 || shard >= shards) { std::cerr << "Invalid shard\n"; return 2; }

    const auto r_primes = sieve_primes(100000);
    Counters c;
    std::vector<std::string> candidate_rows, error_rows;
    const auto started = std::chrono::steady_clock::now();
    std::string line;

    while (std::getline(std::cin, line)) {
        ++c.lines;
        if (max_processed && c.processed >= max_processed) break;
        if (line.empty()) { ++c.malformed; continue; }

        std::istringstream input(line);
        std::string token;
        std::vector<u128> values;
        while (input >> token) {
            u128 value = 0;
            if (!parse_u128_strict(token, value)) { values.clear(); break; }
            values.push_back(value);
        }
        if (values.size() < 4) {
            ++c.malformed;
            if (error_rows.size() < 100)
                error_rows.push_back("{\"line\":\"" + json_escape(line) + "\",\"error\":\"malformed row\"}");
            continue;
        }

        const u128 n = values.front();
        std::vector<u128> factors(values.begin() + 1, values.end());
        ++c.processed;
        if (c.first_n == 0) c.first_n = n;
        c.last_n = n;

        try {
            if (n <= 3 || (n & 1) == 0) throw std::runtime_error("invalid Carmichael n");
            u256 product = 1;
            u128 previous = 0;
            for (u128 p : factors) {
                if (p <= 2 || (p & 1) == 0 || p <= previous)
                    throw std::runtime_error("factor list is not strictly increasing odd integers");
                if (n % p != 0) throw std::runtime_error("listed factor does not divide n");
                product *= u256(p);
                previous = p;
            }
            if (product != u256(n)) throw std::runtime_error("factor product mismatch");

            const unsigned r = smallest_r(n, r_primes);
            c.max_r = std::max(c.max_r, r);
            if (r <= 100) ++c.r_hist[r];

            bool rejected = false;
            for (u128 p : factors) {
                bool used_formula = false;
                if (!check_local(n, p, r, used_formula)) {
                    if (used_formula) ++c.rejected_r5;
                    else ++c.rejected_polynomial;
                    rejected = true;
                    break;
                }
                ++c.passed_local_factors;
            }
            if (rejected) continue;

            for (u128 p : factors)
                if (!is_prime128(p)) throw std::runtime_error("survivor has a non-prime listed factor");
            if (!chebyshev_check128(n, n, r))
                throw std::runtime_error("all local checks passed but direct CRT check failed");

            ++c.candidates;
            std::ostringstream row;
            row << "{\"n\":\"" << to_string_u128(n) << "\",\"r\":" << r
                << ",\"factors\":" << factors_json(factors) << '}';
            candidate_rows.push_back(row.str());
            std::cerr << "CANDIDATE n=" << to_string_u128(n) << " r=" << r << '\n';
        } catch (const std::exception& e) {
            ++c.errors;
            if (error_rows.size() < 100) {
                std::ostringstream row;
                row << "{\"n\":\"" << to_string_u128(n) << "\",\"error\":\""
                    << json_escape(e.what()) << "\"}";
                error_rows.push_back(row.str());
            }
        }

        if (c.processed % 100000 == 0) {
            const double seconds = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
            std::cerr << "shard=" << shard << " processed=" << c.processed
                      << " rate=" << (seconds > 0 ? c.processed / seconds : 0)
                      << "/s candidates=" << c.candidates << " errors=" << c.errors << '\n';
        }
    }

    const double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    std::ofstream out(output);
    if (!out) { std::cerr << "Cannot open output file\n"; return 2; }
    out << "{\n  \"shard\":" << shard
        << ",\n  \"shards\":" << shards
        << ",\n  \"lines_seen\":" << c.lines
        << ",\n  \"processed\":" << c.processed
        << ",\n  \"malformed\":" << c.malformed
        << ",\n  \"first_n\":\"" << to_string_u128(c.first_n) << "\""
        << ",\n  \"last_n\":\"" << to_string_u128(c.last_n) << "\""
        << ",\n  \"elapsed_seconds\":" << elapsed
        << ",\n  \"max_r\":" << c.max_r
        << ",\n  \"rejected_r5_formula\":" << c.rejected_r5
        << ",\n  \"rejected_polynomial\":" << c.rejected_polynomial
        << ",\n  \"passed_local_factor_checks\":" << c.passed_local_factors
        << ",\n  \"errors_count\":" << c.errors
        << ",\n  \"candidates_count\":" << c.candidates
        << ",\n  \"r_histogram\":{";
    bool first = true;
    for (unsigned r = 0; r <= 100; ++r) if (c.r_hist[r]) {
        if (!first) out << ',';
        first = false;
        out << '"' << r << "\":" << c.r_hist[r];
    }
    out << "},\n  \"candidates\":[";
    for (std::size_t i = 0; i < candidate_rows.size(); ++i) {
        if (i) out << ',';
        out << candidate_rows[i];
    }
    out << "],\n  \"errors\":[";
    for (std::size_t i = 0; i < error_rows.size(); ++i) {
        if (i) out << ',';
        out << error_rows[i];
    }
    out << "]\n}\n";

    std::cerr << "DONE shard=" << shard << " processed=" << c.processed
              << " elapsed=" << elapsed << " candidates=" << c.candidates
              << " errors=" << c.errors << '\n';
    return 0;
}
