#define main chebyshev_scanner_main
#include "scan.cpp"
#undef main

#include <cstdlib>

static void require(bool condition, const char* message) {
    if (!condition) {
        std::cerr << "SELF-TEST FAILED: " << message << '\n';
        std::exit(1);
    }
}

int main() {
    const auto r_primes = sieve_primes(100000);

    const u128 a = u128(35626501);
    require(smallest_r(a, r_primes) == 11, "35626501 prescribed r");
    require(chebyshev_check128(a, a, 5), "35626501 fixed-r=5 pass");
    require(!chebyshev_check128(a, a, 11), "35626501 prescribed-r fail");
    for (u128 p : {u128(19), u128(59), u128(61), u128(521)})
        require(local_check_polynomial(a, p, 5), "35626501 local fixed-r=5 checks");

    const u128 b = u128(107357041);
    require(smallest_r(b, r_primes) == 19, "107357041 prescribed r");
    require(chebyshev_check128(b, b, 5), "107357041 fixed-r=5 pass");
    require(!chebyshev_check128(b, b, 19), "107357041 prescribed-r fail");

    for (u128 p : {u128(3),u128(5),u128(7),u128(11),u128(13),u128(17),u128(19),u128(101)}) {
        const unsigned r = smallest_r(p, r_primes);
        require(chebyshev_check128(p, p, r), "prime direct criterion");
        require(local_check_polynomial(p, p, r), "prime local criterion");
        require(is_prime128(p), "Miller-Rabin prime recognition");
    }
    require(!is_prime128(u128(35626501)), "Miller-Rabin composite recognition");

    for (u128 p : {u128(3),u128(7),u128(13),u128(17),u128(23),u128(37),u128(43),u128(47)}) {
        if (!(p % 5 == 2 || p % 5 == 3)) continue;
        for (u128 m = 1; m <= 1500; m += 2) {
            const u128 n = p * m;
            if (!(n % 5 == 2 || n % 5 == 3)) continue;
            const bool formula = local_check_r5_formula(n, p);
            const bool polynomial = local_check_polynomial(n, p, 5);
            require(formula == polynomial, "r=5 formula/polynomial consistency");
        }
    }

    std::cout << "All Chebyshev scanner self-tests passed.\n";
    return 0;
}
