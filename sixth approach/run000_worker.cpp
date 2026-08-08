#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

namespace fs = std::filesystem;

namespace {

using Clock = std::chrono::steady_clock;
using Edge = std::pair<int, int>;

std::atomic<bool> stop_requested{false};

void on_signal(int) { stop_requested.store(true); }

std::string hex64(std::uint64_t value) {
    std::ostringstream out;
    out << "0x" << std::hex << std::setw(16) << std::setfill('0') << value;
    return out.str();
}

std::uint64_t fnv_mix(std::uint64_t state, std::uint64_t value) {
    constexpr std::uint64_t prime = 1099511628211ULL;
    for (int shift = 0; shift < 64; shift += 8) {
        state ^= (value >> shift) & 0xffULL;
        state *= prime;
    }
    return state;
}

struct CompleteGraph {
    int n{};
    int edge_id[22][22]{};
    std::vector<Edge> edges;

    explicit CompleteGraph(int order) : n(order) {
        for (int u = 0; u < n; ++u) {
            for (int v = u + 1; v < n; ++v) {
                edge_id[u][v] = edge_id[v][u] = static_cast<int>(edges.size());
                edges.emplace_back(u, v);
            }
        }
    }

    std::uint64_t mask_of(int u, int v) const {
        return 1ULL << edge_id[u][v];
    }
};

void generate_complete_matchings_rec(
    const CompleteGraph& graph,
    std::uint32_t remaining,
    std::uint64_t mask,
    std::vector<std::uint64_t>& output) {
    if (remaining == 0) {
        output.push_back(mask);
        return;
    }
    const int u = std::countr_zero(remaining);
    const std::uint32_t without_u = remaining & ~(1U << u);
    for (int v = u + 1; v < graph.n; ++v) {
        if ((without_u & (1U << v)) == 0) continue;
        generate_complete_matchings_rec(
            graph,
            without_u & ~(1U << v),
            mask | graph.mask_of(u, v),
            output);
    }
}

std::vector<Edge> edges_from_complete_mask(const CompleteGraph& graph, std::uint64_t mask) {
    std::vector<Edge> result;
    for (std::size_t i = 0; i < graph.edges.size(); ++i) {
        if (mask & (1ULL << i)) result.push_back(graph.edges[i]);
    }
    return result;
}

struct OrbitCatalogue {
    CompleteGraph complete{10};
    std::vector<std::uint64_t> allowed;
    std::vector<std::array<std::uint64_t, 3>> representatives;
    std::uint64_t labelled_factor_triples{};
    std::uint64_t digest{};

    OrbitCatalogue() { build(); }

    void build() {
        std::vector<std::uint64_t> all;
        generate_complete_matchings_rec(complete, (1U << 10) - 1U, 0, all);
        std::uint64_t remainder = 0;
        for (int u = 0; u < 10; u += 2) remainder |= complete.mask_of(u, u + 1);
        for (std::uint64_t matching : all) {
            if ((matching & remainder) == 0) allowed.push_back(matching);
        }
        std::sort(allowed.begin(), allowed.end());
        if (allowed.size() != 544) throw std::runtime_error("allowed matching count mismatch");

        std::unordered_map<std::uint64_t, int> index;
        index.reserve(allowed.size() * 2);
        for (int i = 0; i < static_cast<int>(allowed.size()); ++i) index.emplace(allowed[i], i);

        const std::uint64_t a = allowed.size();
        const std::uint64_t space = a * a * a;
        std::vector<std::uint64_t> valid((space + 63) / 64, 0);
        auto set_valid = [&](std::uint64_t pos) { valid[pos >> 6] |= 1ULL << (pos & 63); };
        auto clear_valid = [&](std::uint64_t pos) { valid[pos >> 6] &= ~(1ULL << (pos & 63)); };

        for (std::uint64_t i = 0; i < a; ++i) {
            for (std::uint64_t j = 0; j < a; ++j) {
                if (allowed[i] & allowed[j]) continue;
                for (std::uint64_t k = 0; k < a; ++k) {
                    if ((allowed[i] & allowed[k]) || (allowed[j] & allowed[k])) continue;
                    set_valid((i * a + j) * a + k);
                    ++labelled_factor_triples;
                }
            }
        }
        if (labelled_factor_triples != 23019264ULL) {
            throw std::runtime_error("labelled factor triple count mismatch");
        }

        std::vector<std::vector<std::uint16_t>> transforms;
        transforms.reserve(3840);
        std::array<int, 5> pair_permutation{0, 1, 2, 3, 4};
        do {
            for (int flips = 0; flips < 32; ++flips) {
                std::array<int, 10> vertex_map{};
                for (int old_pair = 0; old_pair < 5; ++old_pair) {
                    const int target_pair = pair_permutation[old_pair];
                    const int flip = (flips >> old_pair) & 1;
                    vertex_map[2 * old_pair] = 2 * target_pair + flip;
                    vertex_map[2 * old_pair + 1] = 2 * target_pair + (flip ^ 1);
                }
                std::vector<std::uint16_t> map(allowed.size());
                for (std::size_t i = 0; i < allowed.size(); ++i) {
                    std::uint64_t transformed = 0;
                    for (const auto [u, v] : edges_from_complete_mask(complete, allowed[i])) {
                        transformed |= complete.mask_of(vertex_map[u], vertex_map[v]);
                    }
                    const auto found = index.find(transformed);
                    if (found == index.end()) throw std::runtime_error("symmetry image missing");
                    map[i] = static_cast<std::uint16_t>(found->second);
                }
                transforms.push_back(std::move(map));
            }
        } while (std::next_permutation(pair_permutation.begin(), pair_permutation.end()));
        if (transforms.size() != 3840) throw std::runtime_error("symmetry count mismatch");

        constexpr std::array<std::array<int, 3>, 6> color_permutations{{
            {{0, 1, 2}}, {{0, 2, 1}}, {{1, 0, 2}},
            {{1, 2, 0}}, {{2, 0, 1}}, {{2, 1, 0}}
        }};

        std::uint64_t remaining_valid = labelled_factor_triples;
        while (remaining_valid != 0) {
            std::uint64_t position = 0;
            bool found = false;
            for (std::size_t word = 0; word < valid.size(); ++word) {
                if (valid[word] == 0) continue;
                position = word * 64ULL + std::countr_zero(valid[word]);
                found = true;
                break;
            }
            if (!found) throw std::runtime_error("valid bitset lost entries");
            const int k = static_cast<int>(position % a);
            const int j = static_cast<int>((position / a) % a);
            const int i = static_cast<int>(position / (a * a));
            representatives.push_back({allowed[i], allowed[j], allowed[k]});

            for (const auto& transform : transforms) {
                const std::array<int, 3> image{transform[i], transform[j], transform[k]};
                for (const auto& permutation : color_permutations) {
                    const std::uint64_t image_position =
                        (static_cast<std::uint64_t>(image[permutation[0]]) * a + image[permutation[1]]) * a +
                        image[permutation[2]];
                    const std::uint64_t bit = 1ULL << (image_position & 63);
                    std::uint64_t& word = valid[image_position >> 6];
                    if (word & bit) {
                        word &= ~bit;
                        --remaining_valid;
                    }
                }
            }
        }
        if (representatives.size() != 1108) throw std::runtime_error("orbit count mismatch");

        digest = 1469598103934665603ULL;
        for (const auto& representative : representatives) {
            digest = fnv_mix(digest, representative[0]);
            digest = fnv_mix(digest, representative[1]);
            digest = fnv_mix(digest, representative[2]);
        }
    }
};

struct Evaluation {
    bool has_mixed_trap{};
    int trap_count{};
    int h_safe{};
    int full_safe{};
    std::vector<std::pair<std::uint64_t, std::uint64_t>> trap_halves;
};

struct GraphSystem {
    int n{};
    std::array<std::vector<Edge>, 3> factors;
    std::vector<Edge> remainder;
    std::vector<Edge> edges;
    std::vector<int> edge_color;
    std::vector<std::vector<std::pair<int, int>>> adjacency;
    std::uint64_t remainder_mask{};
    std::vector<std::uint64_t> mixed_full_matchings;
    std::vector<std::uint64_t> mixed_h_matchings;
    bool matching_overflow{};

    GraphSystem(int order, const std::array<std::vector<Edge>, 3>& input_factors)
        : n(order), factors(input_factors), adjacency(order) {
        for (int u = 0; u < n; u += 2) remainder.emplace_back(u, u + 1);
        std::unordered_set<int> seen;
        for (int color = 0; color < 3; ++color) {
            for (auto [u, v] : factors[color]) add_edge(u, v, color, seen);
        }
        for (auto [u, v] : remainder) add_edge(u, v, -1, seen);
        for (std::size_t i = 0; i < edges.size(); ++i) {
            if (edge_color[i] == -1) remainder_mask |= 1ULL << i;
        }
        enumerate_matchings((1U << n) - 1U, 0);
    }

    void add_edge(int u, int v, int color, std::unordered_set<int>& seen) {
        if (u > v) std::swap(u, v);
        const int code = u * 32 + v;
        if (!seen.insert(code).second) throw std::runtime_error("non-disjoint factor edges");
        const int id = static_cast<int>(edges.size());
        edges.emplace_back(u, v);
        edge_color.push_back(color);
        adjacency[u].emplace_back(v, id);
        adjacency[v].emplace_back(u, id);
    }

    void enumerate_matchings(std::uint32_t remaining_vertices, std::uint64_t mask) {
        constexpr std::size_t cap = 2000000;
        if (matching_overflow) return;
        if (remaining_vertices == 0) {
            int color_mask = 0;
            for (std::size_t id = 0; id < edges.size(); ++id) {
                if ((mask & (1ULL << id)) && edge_color[id] >= 0) color_mask |= 1 << edge_color[id];
            }
            if (std::popcount(static_cast<unsigned>(color_mask)) >= 2) {
                mixed_full_matchings.push_back(mask);
                if ((mask & remainder_mask) == 0) mixed_h_matchings.push_back(mask);
            }
            if (mixed_full_matchings.size() >= cap) matching_overflow = true;
            return;
        }
        const int u = std::countr_zero(remaining_vertices);
        for (const auto [v, edge_id] : adjacency[u]) {
            if ((remaining_vertices & (1U << v)) == 0) continue;
            enumerate_matchings(
                remaining_vertices & ~(1U << u) & ~(1U << v),
                mask | (1ULL << edge_id));
            if (matching_overflow) return;
        }
    }

    Evaluation evaluate(const std::vector<int>& assignment, bool retain_halves = false) const {
        Evaluation result;
        std::vector<std::vector<std::pair<int, int>>> selected(n);
        for (std::size_t id = 0; id < edges.size(); ++id) {
            const auto [u, v] = edges[id];
            const int color = edge_color[id];
            if (color == -1 || (assignment[u] == color && assignment[v] == color)) {
                selected[u].emplace_back(v, static_cast<int>(id));
                selected[v].emplace_back(u, static_cast<int>(id));
            }
        }

        std::vector<bool> visited(n, false);
        std::vector<std::pair<std::uint64_t, std::uint64_t>> halves;
        for (int start = 0; start < n; ++start) {
            if (visited[start]) continue;
            if (selected[start].size() != 2) {
                std::vector<int> stack{start};
                visited[start] = true;
                while (!stack.empty()) {
                    const int u = stack.back();
                    stack.pop_back();
                    for (const auto [v, unused] : selected[u]) {
                        (void)unused;
                        if (!visited[v]) { visited[v] = true; stack.push_back(v); }
                    }
                }
                continue;
            }

            int previous = -1;
            int current = start;
            std::uint64_t component_mask = 0;
            int color_mask = 0;
            bool cycle = true;
            do {
                if (visited[current] && current != start) { cycle = false; break; }
                visited[current] = true;
                if (selected[current].size() != 2) { cycle = false; break; }
                const auto first = selected[current][0];
                const auto second = selected[current][1];
                const auto chosen = first.first == previous ? second : first;
                component_mask |= 1ULL << chosen.second;
                if (edge_color[chosen.second] >= 0) color_mask |= 1 << edge_color[chosen.second];
                previous = current;
                current = chosen.first;
            } while (current != start);

            if (cycle && current == start && std::popcount(static_cast<unsigned>(color_mask)) >= 2) {
                halves.emplace_back(component_mask & ~remainder_mask, component_mask & remainder_mask);
            }
        }
        if (halves.empty()) return result;

        result.has_mixed_trap = true;
        result.trap_count = static_cast<int>(halves.size());
        auto is_safe = [&](std::uint64_t matching) {
            for (const auto [edge_half, remainder_half] : halves) {
                if ((matching & edge_half) == edge_half ||
                    (matching & remainder_half) == remainder_half) return false;
            }
            return true;
        };
        for (std::uint64_t matching : mixed_h_matchings) result.h_safe += is_safe(matching);
        for (std::uint64_t matching : mixed_full_matchings) result.full_safe += is_safe(matching);
        if (retain_halves) result.trap_halves = std::move(halves);
        return result;
    }
};

std::vector<int> decode_ternary(std::uint64_t code, int n) {
    std::vector<int> assignment(n);
    for (int i = 0; i < n; ++i) {
        assignment[i] = static_cast<int>(code % 3);
        code /= 3;
    }
    return assignment;
}

std::uint64_t power3(int n) {
    std::uint64_t value = 1;
    for (int i = 0; i < n; ++i) value *= 3;
    return value;
}

struct Record {
    int orbit_index{-1};
    int n{};
    std::array<std::vector<Edge>, 3> factors;
    std::vector<int> assignment;
    Evaluation evaluation;
};

struct WorkerState {
    int worker_id{};
    int worker_count{};
    std::string technical_status{"RUNNING"};
    std::uint64_t orbit_digest{};
    std::uint64_t labelled_factor_triples{};
    std::vector<int> assigned_orbits;
    std::vector<int> completed_orbits;
    std::uint64_t exact_assignments{};
    std::uint64_t exact_trap_cases{};
    std::uint64_t exact_h_zero{};
    std::uint64_t exact_threshold_violations{};
    int exact_min_full{std::numeric_limits<int>::max()};
    std::vector<Record>€ü-¢Gß≤⁄Óù∆≠yÿ
        << ",\"order\":" << record.n << ",\"factors\":[";
    for (int color = 0; color < 3; ++color) {
        if (color) out << ',';
        write_edge_array(out, record.factors[color]);
    }
    out << "],\"assignment\":[";
    for (std::size_t i = 0; i < record.assignment.size(); ++i) {
        if (i) out << ',';
        out << record.assignment[i];
    }
    out << "],\"trap_count\":" << record.evaluation.trap_count
        << ",\"h_safe\":" << record.evaluation.h_safe
        << ",\"full_safe\":" << record.evaluation.full_safe
        << ",\"trap_halves\":[";
    for (std::size_t i = 0; i < record.evaluation.trap_halves.size(); ++i) {
        if (i) out << ',';
        out << "{\"edge\":\"" << hex64(record.evaluation.trap_halves[i].first)
            << "\",\"remainder\":\"" << hex64(record.evaluation.trap_halves[i].second) << "\"}";
    }
    out << "]}";
}

void write_int_array(std::ostream& out, const std::vector<int>& values) {
    out << '[';
    for (std::size_t i = 0; i < values.size(); ++i) {
        if (i) out << ',';
        out << values[i];
    }
    out << ']';
}

void write_records(std::ostream& out, const std::vector<Record>& records) {
    out << '[';
    for (std::size_t i = 0; i < records.size(); ++i) {
        if (i) out << ',';
        write_record(out, records[i]);
    }
    out << ']';
}

void checkpoint(const fs::path& path, WorkerState& state, Clock::time_point started) {
    state.elapsed_seconds = std::chrono::duration<double>(Clock::now() - started).count();
    fs::create_directories(path.parent_path().empty() ? fs::path(".") : path.parent_path());
    const fs::path temporary = path.string() + ".tmp";
    {
        std::ofstream out(temporary, std::ios::binary | std::ios::trunc);
        if (!out) throw std::runtime_error("cannot open checkpoint");
        out << "{\"schema_version\":1,\"series\":\"run-000\",\"worker_id\":" << state.worker_id
            << ",\"worker_count\":" << state.worker_count
            << ",\"technical_status\":\"" << state.technical_status << "\""
            << ",\"elapsed_seconds\":" << std::fixed << std::setprecision(3) << state.elapsed_seconds
            << ",\"exact\":{\"order\":10,\"allowed_matchings\":544,\"orbit_count\":1108"
            << ",\"orbit_digest\":\"" << hex64(state.orbit_digest) << "\""
            << ",\"labelled_factor_triples\":" << state.labelled_factor_triples
            << ",\"assigned_orbits\":";
        write_int_array(out, state.assigned_orbits);
        out << ",\"completed_orbits\":";
        write_int_array(out, state.completed_orbits);
        out << ",\"assignments_checked\":" << state.exact_assignments
            << ",\"trap_cases\":" << state.exact_trap_cases
            << ",\"h_zero_cases\":" << state.exact_h_zero
            << ",\"threshold_violations\":" << state.exact_threshold_violations
            << ",\"minimum_full_safe\":" << (state.exact_min_full == std::numeric_limits<int>::max() ? -1 : state.exact_min_full)
            << ",\"h_zero_records\":";
        write_records(out, state.h_zero_records);
        out << ",\"equality_records\":";
        write_records(out, state.equality_records);
        out << "},\"frontier\":{\"order\":" << state.frontier_order
            << ",\"systems_checked\":" << state.frontier_systems
            << ",\"assignments_checked\":" << state.frontier_assignments
            << ",\"trap_cases\":" << state.frontier_trap_cases
            << ",\"threshold_violations\":" << state.frontier_threshold_violations
            << ",\"minimum_full_safe\":" << (state.frontier_min_full == std::numeric_limits<int>::max() ? -1 : state.frontier_min_full)
            << ",\"records\":";
        write_records(out, state.frontier_records);
        out << "}}\n";
        out.flush();
        if (!out) throw std::runtime_error("checkpoint write failed");
    }
    std::error_code error;
    fs::remove(path, error);
    error.clear();
    fs::rename(temporary, path, error);
    if (error) throw std::runtime_error("checkpoint rename failed: " + error.message());
}

Record make_record(int orbit_index, const GraphSystem& system, const std::vector<int>& assignment) {
    return Record{orbit_index, system.n, system.factors, assignment, system.evaluate(assignment, true)};
}

void retain_record(std::vector<Record>& records, Record record, std::size_t limit) {
    records.push_back(std::move(record));
    std::sort(records.begin(), records.end(), [](const Record& left, const Record& right) {
        if (left.evaluation.full_safe != right.evaluation.full_safe)
            return left.evaluation.full_safe < right.evaluation.full_safe;
        if (left.evaluation.h_safe != right.evaluation.h_safe)
            return left.evaluation.h_safe < right.evaluation.h_safe;
        return left.evaluation.trap_count > right.evaluation.trap_count;
    });
    if (records.size() > limit) records.resize(limit);
}

std::array<std::vector<Edge>, 3> factors_from_representative(
    const CompleteGraph& complete,
    const std::array<std::uint64_t, 3>& representative) {
    return {
        edges_from_complete_mask(complete, representative[0]),
        edges_from_complete_mask(complete, representative[1]),
        edges_from_complete_mask(complete, representative[2])
    };
}

bool connected_union(int n, const std::array<std::vector<Edge>, 3>& factors) {
    std::vector<std::vector<int>> adjacency(n);
    for (int u = 0; u < n; u += 2) {
        adjacency[u].push_back(u + 1);
        adjacency[u + 1].push_back(u);
    }
    for (const auto& factor : factors) {
        for (const auto [u, v] : factor) {
            adjacency[u].push_back(v);
            adjacency[v].push_back(u);
        }
    }
    std::vector<int> stack{0};
    std::vector<bool> seen(n, false);
    seen[0] = true;
    while (!stack.empty()) {
        const int u = stack.back(); stack.pop_back();
        for (int v : adjacency[u]) if (!seen[v]) { seen[v] = true; stack.push_back(v); }
    }
    return std::all_of(seen.begin(), seen.end(), [](bool value) { return value; });
}

std::array<std::vector<Edge>, 3> random_factors(int n, std::mt19937_64& random) {
    std::array<std::vector<Edge>, 3> factors;
    std::unordered_set<int> used;
    for (int u = 0; u < n; u += 2) used.insert(u * 32 + u + 1);
    std::vector<int> vertices(n);
    std::iota(vertices.begin(), vertices.end(), 0);
    for (int color = 0; color < 3; ++color) {
        bool accepted = false;
        for (int attempt = 0; attempt < 10000 && !accepted; ++attempt) {
            std::shuffle(vertices.begin(), vertices.end(), random);
            std::vector<Edge> candidate;
            std::unordered_set<int> local;
            bool valid = true;
            for (int i = 0; i < n; i += 2) {
                int u = vertices[i], v = vertices[i + 1];
                if (u > v) std::swap(u, v);
                const int code = u * 32 + v;
                if (used.count(code) || !local.insert(code).second) { valid = false; break; }
                candidate.emplace_back(u, v);
            }
            if (valid) {
                factors[color] = std::move(candidate);
                for (const auto [u, v] : factors[color]) used.insert(u * 32 + v);
                accepted = true;
            }
        }
        if (!accepted) throw std::runtime_error("could not generate random factor");
    }
    return factors;
}

void run_frontier(WorkerState& state, Clock::time_point deadline, std::mt19937_64& random) {
    const int n = 12 + 2 * (state.worker_id % 5);
    state.frontier_order = n;
    std::uniform_int_distribution<int> trit(0, 2);
    while (!stop_requested.load() && Clock::now() < deadline) {
        auto factors = random_factors(n, random);
        if (!connected_union(n, factors)) continue;
        GraphSystem system(n, factors);
        if (system.matching_overflow) continue;
        ++state.frontier_systems;

        std::vector<int> current(n);
        for (int& value : current) value = trit(random);
        Evaluation current_evaluation = system.evaluate(current);
        const int evaluations_per_system = n == 12 ? 4096 : 8192;
        for (int iteration = 0; iteration < evaluations_per_system; ++iteration) {
            if (stop_requested.load() || Clock::now() >= deadline) break;
            std::vector<int> candidate = current;
            const int vertex = static_cast<int>(random() % n);
            candidate[vertex] = (candidate[vertex] + 1 + static_cast<int>(random() & 1ULL)) % 3;
            Evaluation evaluation = system.evaluate(candidate);
            ++state.frontier_assignments;
            if (!evaluation.has_mixed_trap) {
                if ((random() & 15ULL) == 0) current = std::move(candidate);
                continue;
            }
            ++state.frontier_trap_cases;
            state.frontier_min_full = std::min(state.frontier_min_full, evaluation.full_safe);
            if (evaluation.full_safe < n - 3) ++state.frontier_threshold_violations;
            const bool interesting = evaluation.full_safe <= n - 3 ||
                state.frontier_records.empty() ||
                evaluation.full_safe < state.frontier_records.back().evaluation.full_safe;
            if (interesting) retain_record(state.frontier_records, make_record(-1, system, candidate), 12);

            const bool improve = !current_evaluation.has_mixed_trap ||
                evaluation.full_safe < current_evaluation.full_safe ||
                (evaluation.full_safe == current_evaluation.full_safe && evaluation.trap_count > current_evaluation.trap_count);
            if (improve || (random() & 63ULL) == 0) {
                current = std::move(candidate);
                current_evaluation = evaluation;
            }
            if ((iteration & 255) == 255 && (random() & 3ULL) == 0) {
                for (int& value : current) value = trit(random);
                current_evaluation = system.evaluate(current);
            }
        }
    }
}

int run_self_test() {
    const auto started = Clock::now();
    OrbitCatalogue catalogue;
    const auto factors = factors_from_representative(catalogue.complete, catalogue.representatives.front());
    GraphSystem system(10, factors);
    if (system.matching_overflow || system.mixed_full_matchings.empty()) {
        throw std::runtime_error("matching enumeration self-test failed");
    }
    std::uint64_t trap_cases = 0;
    for (std::uint64_t code = 0; code < power3(10); code += 97) {
        trap_cases += system.evaluate(decode_ternary(code, 10)).has_mixed_trap;
    }
    const double seconds = std::chrono::duration<double>(Clock::now() - started).count();
    std::cout << "{\"status\":\"SUCCESS\",\"allowed_matchings\":" << catalogue.allowed.size()
              << ",\"orbit_count\":" << catalogue.representatives.size()
              << ",\"labelled_factor_triples\":" << catalogue.labelled_factor_triples
              << ",\"orbit_digest\":\"" << hex64(catalogue.digest) << "\""
              << ",\"sampled_trap_cases\":" << trap_cases
              << ",\"elapsed_seconds\":" << std::fixed << std::setprecision(3) << seconds << "}\n";
    return 0;
}

std::string argument_value(int argc, char** argv, const std::string& name) {
    for (int i = 2; i + 1 < argc; ++i) if (argv[i] == name) return argv[i + 1];
    throw std::runtime_error("missing argument " + name);
}

int run_worker(int argc, char** argv) {
    WorkerState state;
    state.worker_id = std::stoi(argument_value(argc, argv, "--worker-id"));
    state.worker_count = std::stoi(argument_value(argc, argv, "--worker-count"));
    const int seconds = std::stoi(argument_value(argc, argv, "--seconds"));
    const fs::path output = argument_value(argc, argv, "--output");
    if (state.worker_count <= 0 || state.worker_id < 0 || state.worker_id >= state.worker_count)
        throw std::runtime_error("invalid worker partition");

    const auto started = Clock::now();
    OrbitCatalogue catalogue;
    state.orbit_digest = catalogue.digest;
    state.labelled_factor_triples = catalogue.labelled_factor_triples;
    for (int orbit = state.worker_id; orbit < static_cast<int>(catalogue.representatives.size()); orbit += state.worker_count)
        state.assigned_orbits.push_back(orbit);
    checkpoint(output, state, started);

    for (int orbit : state.assigned_orbits) {
        if (stop_requested.load()) break;
        const auto factors = factors_from_representative(catalogue.complete, catalogue.representatives[orbit]);
        GraphSystem system(10, factors);
        if (system.matching_overflow) throw std::runtime_error("unexpected exact matching overflow");
        bool orbit_complete = true;
        for (std::uint64_t code = 0; code < power3(10); ++code) {
            if ((code & 4095ULL) == 0 && stop_requested.load()) { orbit_complete = false; break; }
            const std::vector<int> assignment = decode_ternary(code, 10);
            const Evaluation evaluation = system.evaluate(assignment);
            ++state.exact_assignments;
            if (!evaluation.has_mixed_trap) continue;
            ++state.exact_trap_cases;
            state.exact_min_full = std::min(state.exact_min_full, evaluation.full_safe);
            if (evaluation.h_safe == 0) {
                ++state.exact_h_zero;
                if (state.h_zero_records.size() < 64)
                    state.h_zero_records.push_back(make_record(orbit, system, assignment));
            }
            if (evaluation.full_safe < 7) ++state.exact_threshold_violations;
            if (evaluation.full_safe == 7 && state.equality_records.size() < 32)
                state.equality_records.push_back(make_record(orbit, system, assignment));
        }
        if (orbit_complete) state.completed_orbits.push_back(orbit);
        checkpoint(output, state, started);
        if (!orbit_complete) break;
    }

    if (state.completed_orbits == state.assigned_orbits && !stop_requested.load()) {
        const auto deadline = Clock::now() + std::chrono::seconds(seconds);
        std::mt19937_64 random(
            0x6a09e667f3bcc909ULL ^ (static_cast<std::uint64_t>(state.worker_id) << 32) ^
            static_cast<std::uint64_t>(state.worker_count));
        run_frontier(state, deadline, random);
        state.technical_status = "SUCCESS";
    } else {
        state.technical_status = "INTERRUPTED";
    }
    checkpoint(output, state, started);
    return state.technical_status == "SUCCESS" ? 0 : 3;
}

}  // namespace

int main(int argc, char** argv) {
    std::signal(SIGTERM, on_signal);
    std::signal(SIGINT, on_signal);
    try {
        if (argc < 2) throw std::runtime_error("expected self-test or worker");
        const std::string command = argv[1];
        if (command == "self-test") return run_self_test();
        if (command == "worker") return run_worker(argc, argv);
        throw std::runtime_error("unknown command");
    } catch (const std::exception& error) {
        std::cerr << "ERROR: " << error.what() << '\n';
        return 2;
    }
}
