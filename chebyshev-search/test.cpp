#define main chebyshev_scanner_main
#include "scan.cpp"
#undef main

#include <cstdlib>

static void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "SELF-TEST FAILED: " << message << "\n";
        std::exit(1);
    }
}

int main() {
    const auto r_primes = sieve_primes(100000);

    const u128 a = u128(35626501);
    require(smallest_r(a, r_primes) == 11, "35626501 must have prescribed r=11");
    require(cheb_check_poly128(a, a, 5), "35626501 must be a fixed-r=5 false positive");
    require(!cheb_check_poly128(a, a, 11), "35626501 must fail for prescribed r=11");
    for (u64 p : {19ULL, 59ULL, 61ULL, 521ULL}) {
        require(local_check_poly(a, p, 5), "all prime factors of 35626501 must pass locally at r=5");
    }

    const u128 b = u128(107357041);
    require(smallest_r(b, r_primes) == 19, "107357041 must have prescribed r=19");
    require(cheb_check_poly128(b, b, 5), "107357041 must be a fixed-r=5 false positive");
    require(!cheb_check_poly128(b, b, 19), "107357041 must fail for prescribed r=19");

    for (u64 p : {3ULL, 5ULL, 7ULL, 11ULL, 13ULL, 17ULL, 19ULL, 101ULL}) {
        unsigned r = smallest_r(p, r_primes);
        require(cheb_check_poly128(p, p, r), "a prime must pass the direct criterion");
        require(local_check_poly(p, p, r), "a prime must pass the local implementation");
    }

    std::vector<u128> fs;
    factor_rec(u128(35626501), fs, 1234567);
    std::sort(fs.begin(), fs.end());
    require(fs.size() == 4 && fs[0] == 19 && fs[1] == 59 && fs[2] == 61 && fs[3] == 521,
            "Pollard-Brent factorization of 35626501");

    std::cout << "All Chebyshev scanner self-tests passed.\n";
    return 0;
}
