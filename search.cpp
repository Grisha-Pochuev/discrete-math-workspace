#include <algorithm>
#include <array>
#include <bit>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <limits>
#include <numeric>
#include <stdexcept>
#include <string>
#include <tuple>
#include <unordered_set>
#include <vector>

namespace {

constexpr int N = 6;
constexpr int D = 3;
constexpr int NV = 135;
constexpr int NC = 729;
constexpr int NM = 15;
constexpr int NT = NC * NM;
constexpr int WORDS = 3;
constexpr int SINGLE_WORDS = (NC + 63) / 64;

volatile std::sig_atomic_t stop_requested = 0;

void request_stop(int) { stop_requested = 1; }

struct Mask {
    std::array<std::uint64_t, WORDS> w{};
    bool operator==(const Mask& other) const noexcept { return w == other.w; }
};

struct MaskHash {
    std::size_t operator()(const Mask& m) const noexcept {
        std::uint64_t x = m.w[0] ^ std::rotl(m.w[1], 21) ^ std::rotl(m.w[2], 43);
        x ^= x >> 30;
        x *= 0xbf58476d1ce4e5b9ULL;
        x ^= x >> 27;
        x *= 0x94d049bb133111ebULL;
        x ^= x >> 31;
        return static_cast<std::size_t>(x);
    }
};

bool less_mask(const Mask& a, const Mask& b) {
    for (int k = WORDS - 1; k >= 0; --k) {
        if (a.w[k] != b.w[k]) return a.w[k] < b.w[k];
    }
    return false;
}

Mask mask_or(const Mask& a, const Mask& b) {
    Mask result;
    for (int k = 0; k < WORDS; ++k) result.w[k] = a.w[k] | b.w[k];
    return result;
}

Mask mask_andnot(const Mask& a, const Mask& b) {
    Mask result;
    for (int k = 0; k < WORDS; ++k) result.w[k] = a.w[k] & ~b.w[k];
    return result;
}

bool subset(const Mask& a, const Mask& b) {
    for (int k = 0; k < WORDS; ++k) {
        if ((a.w[k] & ~b.w[k]) != 0) return false;
    }
    return true;
}

int popcount(const Mask& a) {
    int result = 0;
    for (auto word : a.w) result += std::popcount(word);
    return result;
}

void setbit(Mask& a, int bit) { a.w[bit >> 6] |= 1ULL << (bit & 63); }

template <class Function>
void each_bit(const Mask& a, Function&& function) {
    for (int word_index = 0; word_index < WORDS; ++word_index) {
        std::uint64_t word = a.w[word_index];
        while (word) {
            int bit = std::countr_zero(word);
            int value = 64 * word_index + bit;
            if (value < NV) function(value);
            word &= word - 1;
        }
    }
}

std::string hex_mask(const Mask& a) {
    static const char* digits = "0123456789abcdef";
    std::string result;
    bool started = false;
    for (int word_index = WORDS - 1; word_index >= 0; --word_index) {
        for (int shift = 60; shift >= 0; shift -= 4) {
            int digit = static_cast<int>((a.w[word_index] >> shift) & 15ULL);
            if (digit || started) {
                result.push_back(digits[digit]);
                started = true;
            }
        }
    }
    return started ? result : "0";
}

using Edge = std::pair<int, int>;
using Matching = std::array<Edge, 3>;

struct Solver {
    int orbit = 0;
    int limit = 26;
    double time_limit = 3600.0;
    std::uint64_t report_every = 0;
    std::uint64_t max_seen = 8'000'000;
    std::string output_path;
    int shard_count = 1;
    int shard_index = 0;
    int split_size = 15;

    std::vector<Edge> edges;
    std::array<std::array<int, N>, N> edge_pos{};
    std::vector<Matching> matchings;
    std::array<std::array<std::array<int, 3>, NM>, NC> term_vars{};
    std::array<Mask, NT> term_masks{};
    std::array<std::vector<int>, NV> var_terms;
    std::vector<std::array<int, NV>> symmaps;

    Mask mask{};
    std::array<std::uint8_t, NT> missing{};
    std::array<std::uint8_t, NC> active{};
    std::array<std::uint64_t, SINGLE_WORDS> singles{};
    std::unordered_set<Mask, MaskHash> seen;
    std::vector<Mask> solutions;
    std::uint64_t nodes = 0;
    std::string status = "complete";
    bool halted = false;
    std::chrono::steady_clock::time_point start;

    static constexpr std::array<std::array<int, 3>, 8> reps{{
        {{0, 0, 0}}, {{0, 0, 1}}, {{0, 0, 4}}, {{0, 1, 2}},
        {{0, 1, 3}}, {{0, 1, 5}}, {{0, 4, 8}}, {{0, 4, 13}}
    }};

    bool mixed(int row) const { return row != 0 && row != 364 && row != 728; }

    void generate_matchings(const std::vector<int>& vertices, std::vector<Edge>& current) {
        if (vertices.empty()) {
            Matching matching{};
            std::copy(current.begin(), current.end(), matching.begin());
            matchings.push_back(matching);
            return;
        }
        int left = vertices.front();
        for (std::size_t position = 1; position < vertices.size(); ++position) {
            int right = vertices[position];
            std::vector<int> rest;
            for (std::size_t q = 1; q < vertices.size(); ++q) {
                if (q != position) rest.push_back(vertices[q]);
            }
            current.push_back({left, right});
            generate_matchings(rest, current);
            current.pop_back();
        }
    }

    int var_index(int i, int j, int a, int b) const {
        if (i > j) {
            std::swap(i, j);
            std::swap(a, b);
        }
        return (edge_pos[i][j] * D + a) * D + b;
    }

    void build_system() {
        for (auto& row : edge_pos) row.fill(-1);
        for (int i = 0; i < N; ++i) {
            for (int j = i + 1; j < N; ++j) {
                edge_pos[i][j] = static_cast<int>(edges.size());
                edges.push_back({i, j});
            }
        }
        std::vector<int> vertices(N);
        std::iota(vertices.begin(), vertices.end(), 0);
        std::vector<Edge> current;
        generate_matchings(vertices, current);
        if (matchings.size() != NM) throw std::runtime_error("matching count");

        constexpr std::array<int, N> powers{{243, 81, 27, 9, 3, 1}};
        for (int row = 0; row < NC; ++row) {
            std::array<int, N> colours{};
            for (int i = 0; i < N; ++i) colours[i] = (row / powers[i]) % D;
            for (int matching_index = 0; matching_index < NM; ++matching_index) {
                int term = row * NM + matching_index;
                for (int k = 0; k < 3; ++k) {
                    auto [i, j] = matchings[matching_index][k];
                    int variable = var_index(i, j, colours[i], colours[j]);
                    term_vars[row][matching_index][k] = variable;
                    setbit(term_masks[term], variable);
                    var_terms[variable].push_back(term);
                }
            }
        }
    }

    Mask seed_mask() const {
        Mask seed;
        for (int colour = 0; colour < D; ++colour) {
            int matching_index = reps[orbit][colour];
            for (auto [i, j] : matchings[matching_index]) {
                setbit(seed, var_index(i, j, colour, colour));
            }
        }
        return seed;
    }

    std::array<int, NV> variable_permutation(const std::array<int, N>& vertex_permutation,
                                             const std::array<int, D>& colour_permutation) const {
        std::array<int, NV> result{};
        for (int variable = 0; variable < NV; ++variable) {
            int edge_index = variable / 9;
            int remainder = variable % 9;
            int a = remainder / 3;
            int b = remainder % 3;
            auto [i, j] = edges[edge_index];
            result[variable] = var_index(vertex_permutation[i], vertex_permutation[j],
                                         colour_permutation[a], colour_permutation[b]);
        }
        return result;
    }

    Mask move_mask(const Mask& source, const std::array<int, NV>& permutation) const {
        Mask result;
        each_bit(source, [&](int variable) { setbit(result, permutation[variable]); });
        return result;
    }

    void build_stabilizer() {
        Mask seed = seed_mask();
        std::array<int, N> vertex_permutation{{0, 1, 2, 3, 4, 5}};
        do {
            std::array<int, D> colour_permutation{{0, 1, 2}};
            do {
                auto permutation = variable_permutation(vertex_permutation, colour_permutation);
                if (move_mask(seed, permutation) == seed) symmaps.push_back(permutation);
            } while (std::next_permutation(colour_permutation.begin(), colour_permutation.end()));
        } while (std::next_permutation(vertex_permutation.begin(), vertex_permutation.end()));
        constexpr std::array<int, 8> expected{{288, 16, 12, 48, 4, 4, 12, 36}};
        if (static_cast<int>(symmaps.size()) != expected[orbit]) {
            throw std::runtime_error("stabilizer count");
        }
    }

    void set_single(int row, bool value) {
        auto bit = 1ULL << (row & 63);
        if (value) singles[row >> 6] |= bit;
        else singles[row >> 6] &= ~bit;
    }

    void change_active(int row, int delta) {
        int old = active[row];
        int now = old + delta;
        active[row] = static_cast<std::uint8_t>(now);
        if (!mixed(row)) return;
        if (old == 0 && now == 1) set_single(row, true);
        else if (old == 1 && now == 2) set_single(row, false);
        else if (old == 2 && now == 1) set_single(row, true);
        else if (old == 1 && now == 0) set_single(row, false);
    }

    void apply(const Mask& addition) {
        each_bit(addition, [&](int variable) {
            for (int term : var_terms[variable]) {
                if (missing[term] == 0) throw std::runtime_error("duplicate variable");
                --missing[term];
                if (missing[term] == 0) change_active(term / NM, +1);
            }
        });
        mask = mask_or(mask, addition);
    }

    void undo(const Mask& addition) {
        each_bit(addition, [&](int variable) {
            for (int term : var_terms[variable]) {
                if (missing[term] == 0) change_active(term / NM, -1);
                ++missing[term];
            }
        });
        for (int k = 0; k < WORDS; ++k) mask.w[k] &= ~addition.w[k];
    }

    int singleton_count() const {
        int result = 0;
        for (auto word : singles) result += std::popcount(word);
        return result;
    }

    std::vector<int> singleton_rows() const {
        std::vector<int> rows;
        for (int word_index = 0; word_index < SINGLE_WORDS; ++word_index) {
            std::uint64_t word = singles[word_index];
            while (word) {
                int bit = std::countr_zero(word);
                int row = 64 * word_index + bit;
                if (row < NC) rows.push_back(row);
                word &= word - 1;
            }
        }
        return rows;
    }

    Mask canonical() const {
        Mask best = mask;
        for (const auto& permutation : symmaps) {
            Mask moved = move_mask(mask, permutation);
            if (less_mask(moved, best)) best = moved;
        }
        return best;
    }

    std::vector<Mask> minimal_additions(int row, int room) const {
        std::vector<Mask> additions;
        for (int matching_index = 0; matching_index < NM; ++matching_index) {
            const Mask& term = term_masks[row * NM + matching_index];
            if (subset(term, mask)) continue;
            Mask addition = mask_andnot(term, mask);
            if (popcount(addition) > room) continue;
            if (std::find(additions.begin(), additions.end(), addition) == additions.end()) {
                additions.push_back(addition);
            }
        }
        std::vector<Mask> minimal;
        for (std::size_t i = 0; i < additions.size(); ++i) {
            bool dominated = false;
            for (std::size_t j = 0; j < additions.size(); ++j) {
                if (i != j && subset(additions[j], additions[i])) {
                    dominated = true;
                    break;
                }
            }
            if (!dominated) minimal.push_back(additions[i]);
        }
        return minimal;
    }

    bool should_halt() {
        if ((nodes & 65535ULL) != 0) return false;
        if (stop_requested) {
            status = "stopped";
            return true;
        }
        if (seen.size() >= max_seen) {
            status = "capacity";
            return true;
        }
        double elapsed = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start).count();
        if (elapsed > time_limit) {
            status = "timeout";
            return true;
        }
        return false;
    }

    void dfs(bool shard_assigned) {
        if (halted) return;
        ++nodes;
        if (should_halt()) {
            halted = true;
            return;
        }
        if (report_every && nodes % report_every == 0) {
            double elapsed = std::chrono::duration<double>(
                std::chrono::steady_clock::now() - start).count();
            std::cerr << "nodes " << nodes << " seen " << seen.size()
                      << " size " << popcount(mask) << " solutions " << solutions.size()
                      << " seconds " << elapsed << '\n';
        }

        Mask key = canonical();
        if (shard_count > 1 && !shard_assigned && popcount(mask) >= split_size) {
            if (static_cast<int>(MaskHash{}(key) % shard_count) != shard_index) return;
            shard_assigned = true;
        }
        if (!seen.insert(key).second) return;

        auto rows = singleton_rows();
        if (rows.empty()) {
            solutions.push_back(shard_count > 1 ? key : mask);
            return;
        }
        int room = limit - popcount(mask);
        if (room <= 0) return;

        std::vector<Mask> best;
        std::pair<int, int> best_score{std::numeric_limits<int>::max(),
                                      std::numeric_limits<int>::max()};
        for (int row : rows) {
            auto additions = minimal_additions(row, room);
            int minimum_size = std::numeric_limits<int>::max();
            for (const auto& addition : additions) {
                minimum_size = std::min(minimum_size, popcount(addition));
            }
            std::pair<int, int> score{static_cast<int>(additions.size()), -minimum_size};
            if (score < best_score) {
                best_score = score;
                best = std::move(additions);
            }
        }
        if (best.empty()) return;

        std::vector<std::tuple<int, int, Mask>> ordered;
        for (const auto& addition : best) {
            apply(addition);
            int score = singleton_count();
            undo(addition);
            ordered.emplace_back(score, popcount(addition), addition);
        }
        std::sort(ordered.begin(), ordered.end(), [](const auto& left, const auto& right) {
            return std::get<0>(left) < std::get<0>(right)
                || (std::get<0>(left) == std::get<0>(right)
                    && std::get<1>(left) < std::get<1>(right));
        });
        for (const auto& item : ordered) {
            const Mask& addition = std::get<2>(item);
            apply(addition);
            dfs(shard_assigned);
            undo(addition);
            if (halted) return;
        }
    }

    void write_result(double elapsed) const {
        if (output_path.empty()) return;
        std::ofstream output(output_path);
        if (!output) throw std::runtime_error("cannot open output");
        output << "# orbit " << orbit << " limit " << limit << " status " << status
               << " nodes " << nodes << " seen " << seen.size()
               << " seconds " << elapsed << " shard " << shard_index << "/" << shard_count
               << " split_size " << split_size << " max_seen " << max_seen << '\n';
        for (const auto& solution : solutions) {
            output << popcount(solution) << " " << hex_mask(solution) << '\n';
        }
    }

    void run() {
        build_system();
        build_stabilizer();
        missing.fill(3);
        seen.reserve(static_cast<std::size_t>(
            std::min<std::uint64_t>(max_seen + max_seen / 8, 20'000'000)));
        apply(seed_mask());
        start = std::chrono::steady_clock::now();
        try {
            dfs(shard_count == 1);
        } catch (const std::bad_alloc&) {
            halted = true;
            status = "memory";
        }
        double elapsed = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - start).count();
        write_result(elapsed);
        std::cout << "status " << status << " orbit " << orbit << " limit " << limit
                  << " shard " << shard_index << "/" << shard_count
                  << " nodes " << nodes << " seen " << seen.size()
                  << " seconds " << elapsed << " solutions " << solutions.size() << '\n';
    }
};

}  // namespace

int main(int argc, char** argv) {
    std::signal(SIGTERM, request_stop);
    std::signal(SIGINT, request_stop);
    Solver solver;
    for (int i = 1; i < argc; ++i) {
        std::string argument = argv[i];
        auto value = [&]() -> std::string {
            if (++i >= argc) throw std::runtime_error("missing value for " + argument);
            return argv[i];
        };
        if (argument == "--orbit") solver.orbit = std::stoi(value());
        else if (argument == "--limit") solver.limit = std::stoi(value());
        else if (argument == "--time-limit") solver.time_limit = std::stod(value());
        else if (argument == "--report-every") solver.report_every = std::stoull(value());
        else if (argument == "--max-seen") solver.max_seen = std::stoull(value());
        else if (argument == "--output") solver.output_path = value();
        else if (argument == "--shard-count") solver.shard_count = std::stoi(value());
        else if (argument == "--shard-index") solver.shard_index = std::stoi(value());
        else if (argument == "--split-size") solver.split_size = std::stoi(value());
        else throw std::runtime_error("unknown argument: " + argument);
    }
    if (solver.orbit < 0 || solver.orbit >= 8) throw std::runtime_error("orbit out of range");
    if (solver.shard_count < 1) throw std::runtime_error("invalid shard count");
    if (solver.shard_index < 0 || solver.shard_index >= solver.shard_count) {
        throw std::runtime_error("invalid shard index");
    }
    if (solver.split_size < 9 || solver.split_size > solver.limit) {
        throw std::runtime_error("invalid split size");
    }
    if (solver.max_seen < 1000) throw std::runtime_error("max-seen is too small");
    solver.run();
}
