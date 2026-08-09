// Exact four-way support-layer enumerator using the native OR-Tools C++ API.

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include "ortools/base/init_google.h"
#include "ortools/sat/cp_model.h"
#include "ortools/sat/cp_model.pb.h"
#include "ortools/sat/cp_model_solver.h"
#include "ortools/sat/model.h"
#include "ortools/sat/sat_parameters.pb.h"
#include "ortools/util/sorted_interval_list.h"

namespace fs = std::filesystem;
namespace sat = operations_research::sat;

namespace {

constexpr char kRunId[] = "run-033";
constexpr char kPartitionVersion[] = "parity2-v1";
constexpr int kVertexCount = 8;
constexpr int kColourCount = 3;
constexpr int kResidualEdgeCount = 8;
constexpr int kSupportVariableCount = 72;

using Edge = std::array<int, 2>;
using Matching = std::vector<Edge>;
using Masks = std::array<std::uint16_t, kResidualEdgeCount>;

struct Config {
  int case_id;
  int orbit_id;
  std::array<Matching, 3> factors;
  Matching residual;
  std::array<std::array<int, 4>, 2> cycle_orders;
};

struct Symmetry {
  std::array<int, kVertexCount> permutation;
  std::array<int, kColourCount> colour_image;
};

struct Arguments {
  std::string run_id = kRunId;
  int case_id = -1;
  int support = -1;
  int shard_id = -1;
  int shard_count = 4;
  double seconds = 3240.0;
  std::uint64_t cap = 2'000'000;
  std::uint64_t checkpoint_every = 5000;
  double checkpoint_seconds = 60.0;
  fs::path output;
};

std::atomic<bool> g_signal_requested{false};

void HandleSignal(int) { g_signal_requested.store(true); }

Edge MakeEdge(int a, int b) {
  return a < b ? Edge{a, b} : Edge{b, a};
}

int EdgeCode(const Edge& edge) { return 8 * edge[0] + edge[1]; }

std::uint64_t EdgeMask(const Matching& edges) {
  std::uint64_t mask = 0;
  for (const Edge& edge : edges) mask |= std::uint64_t{1} << EdgeCode(edge);
  return mask;
}

Config GetConfig(int case_id) {
  if (case_id == 3) {
    return {
        3,
        8,
        std::array<Matching, 3>{
            Matching{{0, 2}, {1, 3}, {4, 6}, {5, 7}},
            Matching{{0, 3}, {1, 6}, {2, 5}, {4, 7}},
            Matching{{0, 5}, {1, 4}, {2, 7}, {3, 6}},
        },
        Matching{{0, 4}, {0, 6}, {1, 5}, {1, 7},
                 {2, 4}, {2, 6}, {3, 5}, {3, 7}},
        std::array<std::array<int, 4>, 2>{
            std::array<int, 4>{0, 4, 2, 6},
            std::array<int, 4>{1, 5, 3, 7},
        },
    };
  }
  if (case_id == 9) {
    return {
        9,
        51,
        std::array<Matching, 3>{
            Matching{{0, 2}, {1, 5}, {3, 7}, {4, 6}},
            Matching{{0, 3}, {1, 6}, {2, 5}, {4, 7}},
            Matching{{0, 5}, {1, 4}, {2, 7}, {3, 6}},
        },
        Matching{{0, 4}, {0, 6}, {1, 3}, {1, 7},
                 {2, 4}, {2, 6}, {3, 5}, {5, 7}},
        std::array<std::array<int, 4>, 2>{
            std::array<int, 4>{0, 4, 2, 6},
            std::array<int, 4>{1, 3, 5, 7},
        },
    };
  }
  if (case_id == 10) {
    return {
        10,
        52,
        std::array<Matching, 3>{
            Matching{{0, 3}, {1, 5}, {2, 6}, {4, 7}},
            Matching{{0, 4}, {1, 6}, {2, 5}, {3, 7}},
            Matching{{0, 5}, {1, 4}, {2, 7}, {3, 6}},
        },
        Matching{{0, 2}, {0, 6}, {1, 3}, {1, 7},
                 {2, 4}, {3, 5}, {4, 6}, {5, 7}},
        std::array<std::array<int, 4>, 2>{
            std::array<int, 4>{0, 2, 4, 6},
            std::array<int, 4>{1, 3, 5, 7},
        },
    };
  }
  if (case_id == 11) {
    return {
        11,
        53,
        std::array<Matching, 3>{
            Matching{{0, 3}, {1, 6}, {2, 5}, {4, 7}},
            Matching{{0, 4}, {1, 5}, {2, 6}, {3, 7}},
            Matching{{0, 5}, {1, 4}, {2, 7}, {3, 6}},
        },
        Matching{{0, 2}, {0, 6}, {1, 3}, {1, 7},
                 {2, 4}, {3, 5}, {4, 6}, {5, 7}},
        std::array<std::array<int, 4>, 2>{
            std::array<int, 4>{0, 2, 4, 6},
            std::array<int, 4>{1, 3, 5, 7},
        },
    };
  }
  if (case_id == 14) {
    return {
        14,
        3,
        std::array<Matching, 3>{
            Matching{{0, 2}, {1, 3}, {4, 6}, {5, 7}},
            Matching{{0, 4}, {1, 5}, {2, 6}, {3, 7}},
            Matching{{0, 6}, {1, 7}, {2, 4}, {3, 5}},
        },
        Matching{{0, 5}, {0, 7}, {1, 4}, {1, 6},
                 {2, 5}, {2, 7}, {3, 4}, {3, 6}},
        std::array<std::array<int, 4>, 2>{
            std::array<int, 4>{0, 5, 2, 7},
            std::array<int, 4>{1, 4, 3, 6},
        },
    };
  }
  throw std::invalid_argument("unsupported case id");
}

void PerfectMatchingsRecursive(const std::vector<int>& vertices,
                               std::uint64_t allowed,
                               Matching* prefix,
                               std::vector<Matching>* output) {
  if (vertices.empty()) {
    output->push_back(*prefix);
    return;
  }
  const int first = vertices.front();
  for (std::size_t position = 1; position < vertices.size(); ++position) {
    const int other = vertices[position];
    const Edge edge = MakeEdge(first, other);
    if ((allowed & (std::uint64_t{1} << EdgeCode(edge))) == 0) continue;
    std::vector<int> rest;
    rest.reserve(vertices.size() - 2);
    for (std::size_t index = 1; index < vertices.size(); ++index) {
      if (index != position) rest.push_back(vertices[index]);
    }
    prefix->push_back(edge);
    PerfectMatchingsRecursive(rest, allowed, prefix, output);
    prefix->pop_back();
  }
}

std::vector<Matching> PerfectMatchings(const std::vector<int>& vertices,
                                       std::uint64_t allowed) {
  Matching prefix;
  std::vector<Matching> result;
  PerfectMatchingsRecursive(vertices, allowed, &prefix, &result);
  return result;
}

std::array<int, kVertexCount> GlobalColours(int index) {
  std::array<int, kVertexCount> colours{};
  for (int vertex = 0; vertex < kVertexCount; ++vertex) {
    colours[vertex] = index % kColourCount;
    index /= kColourCount;
  }
  return colours;
}

bool Mixed(const std::array<int, kVertexCount>& colours) {
  return std::any_of(colours.begin() + 1, colours.end(),
                     [&](int value) { return value != colours[0]; });
}

std::array<std::array<int, kVertexCount>, 81> LocalStates(
    const std::array<int, 4>& order) {
  std::array<std::array<int, kVertexCount>, 81> result{};
  for (auto& state : result) state.fill(-1);
  for (int index = 0; index < 81; ++index) {
    int value = index;
    for (const int vertex : order) {
      result[index][vertex] = value % kColourCount;
      value /= kColourCount;
    }
  }
  return result;
}

std::vector<Symmetry> Stabilizer(const Config& config) {
  std::uint64_t graph = EdgeMask(config.residual);
  std::array<std::uint64_t, 3> factor_masks{};
  for (int colour = 0; colour < 3; ++colour) {
    factor_masks[colour] = EdgeMask(config.factors[colour]);
    graph |= factor_masks[colour];
  }
  std::vector<Symmetry> result;
  std::array<int, kVertexCount> permutation{0, 1, 2, 3, 4, 5, 6, 7};
  do {
    std::uint64_t image_graph = 0;
    for (int u = 0; u < kVertexCount; ++u) {
      for (int v = u + 1; v < kVertexCount; ++v) {
        const Edge source{u, v};
        if ((graph & (std::uint64_t{1} << EdgeCode(source))) == 0) continue;
        image_graph |= std::uint64_t{1} << EdgeCode(MakeEdge(permutation[u], permutation[v]));
      }
    }
    if (image_graph != graph) continue;
    std::array<int, 3> colour_image{};
    bool valid = true;
    for (int colour = 0; colour < 3 && valid; ++colour) {
      std::uint64_t image = 0;
      for (const Edge& edge : config.factors[colour]) {
        image |= std::uint64_t{1}
                 << EdgeCode(MakeEdge(permutation[edge[0]], permutation[edge[1]]));
      }
      const auto found = std::find(factor_masks.begin(), factor_masks.end(), image);
      if (found == factor_masks.end()) {
        valid = false;
      } else {
        colour_image[colour] = static_cast<int>(found - factor_masks.begin());
      }
    }
    if (!valid || colour_image[0] == colour_image[1] ||
        colour_image[0] == colour_image[2] || colour_image[1] == colour_image[2]) {
      continue;
    }
    result.push_back({permutation, colour_image});
  } while (std::next_permutation(permutation.begin(), permutation.end()));
  return result;
}

Masks TransformMasks(const Masks& masks, const Config& config,
                     const Symmetry& symmetry) {
  std::array<int, 64> residual_index{};
  residual_index.fill(-1);
  for (int index = 0; index < kResidualEdgeCount; ++index) {
    residual_index[EdgeCode(config.residual[index])] = index;
  }
  Masks output{};
  for (int source_index = 0; source_index < kResidualEdgeCount; ++source_index) {
    const Edge source = config.residual[source_index];
    const int target_u = symmetry.permutation[source[0]];
    const int target_v = symmetry.permutation[source[1]];
    const int target_index = residual_index[EdgeCode(MakeEdge(target_u, target_v))];
    if (target_index < 0) throw std::logic_error("stabilizer left residual edge set");
    for (int row = 0; row < 3; ++row) {
      for (int column = 0; column < 3; ++column) {
        if ((masks[source_index] & (std::uint16_t{1} << (3 * row + column))) == 0) continue;
        int new_row = symmetry.colour_image[row];
        int new_column = symmetry.colour_image[column];
        if (target_u > target_v) std::swap(new_row, new_column);
        output[target_index] |= std::uint16_t{1} << (3 * new_row + new_column);
      }
    }
  }
  return output;
}

Masks Canonical(const Masks& masks, const Config& config,
                const std::vector<Symmetry>& symmetries) {
  Masks best = masks;
  for (const Symmetry& symmetry : symmetries) {
    best = std::min(best, TransformMasks(masks, config, symmetry));
  }
  return best;
}

std::uint64_t SplitMix64(std::uint64_t value) {
  value += 0x9E3779B97F4A7C15ULL;
  value = (value ^ (value >> 30)) * 0xBF58476D1CE4E5B9ULL;
  value = (value ^ (value >> 27)) * 0x94D049BB133111EBULL;
  return value ^ (value >> 31);
}

std::array<std::vector<int>, 2> PartitionGroups(int size) {
  const std::array<std::uint64_t, 2> seeds{
      0x243F6A8885A308D3ULL, 0x13198A2E03707344ULL};
  std::array<std::vector<int>, 2> groups;
  for (int bit = 0; bit < 2; ++bit) {
    for (int index = 0; index < size; ++index) {
      if ((SplitMix64(static_cast<std::uint64_t>(index) ^ seeds[bit]) & 1) != 0) {
        groups[bit].push_back(index);
      }
    }
    if (groups[bit].empty() || groups[bit].size() == static_cast<std::size_t>(size)) {
      throw std::logic_error("degenerate parity partition");
    }
  }
  return groups;
}

sat::BoolVar Conjunction(sat::CpModelBuilder* model,
                         const std::vector<sat::BoolVar>& values) {
  if (values.empty()) throw std::invalid_argument("empty conjunction");
  const sat::BoolVar term = model->NewBoolVar();
  sat::LinearExpr sum;
  for (const sat::BoolVar value : values) {
    model->AddLessOrEqual(term, value);
    sum += value;
  }
  model->AddGreaterOrEqual(term, sum - static_cast<int64_t>(values.size()) + 1);
  return term;
}

struct Prepared {
  std::array<int, 64> anchor_colour;
  std::array<int, 64> residual_index;
  std::vector<Matching> matchings;
  std::vector<Matching> cross_matchings;
  std::array<std::vector<Matching>, 2> cycle_matchings;
  std::array<std::array<std::array<int, kVertexCount>, 81>, 2> states;
};

Prepared Prepare(const Config& config) {
  Prepared data;
  data.anchor_colour.fill(-1);
  data.residual_index.fill(-1);
  std::uint64_t graph = EdgeMask(config.residual);
  for (int colour = 0; colour < 3; ++colour) {
    for (const Edge& edge : config.factors[colour]) {
      data.anchor_colour[EdgeCode(edge)] = colour;
    }
    graph |= EdgeMask(config.factors[colour]);
  }
  for (int index = 0; index < kResidualEdgeCount; ++index) {
    data.residual_index[EdgeCode(config.residual[index])] = index;
  }
  data.matchings = PerfectMatchings({0, 1, 2, 3, 4, 5, 6, 7}, graph);
  for (const Matching& matching : data.matchings) {
    if (std::any_of(matching.begin(), matching.end(), [&](const Edge& edge) {
          return data.anchor_colour[EdgeCode(edge)] >= 0;
        })) {
      data.cross_matchings.push_back(matching);
    }
  }
  for (int cycle = 0; cycle < 2; ++cycle) {
    std::uint64_t allowed = 0;
    std::set<int> vertices(config.cycle_orders[cycle].begin(),
                           config.cycle_orders[cycle].end());
    for (const Edge& edge : config.residual) {
      if (vertices.count(edge[0]) && vertices.count(edge[1])) {
        allowed |= std::uint64_t{1} << EdgeCode(edge);
      }
    }
    data.cycle_matchings[cycle] = PerfectMatchings(
        std::vector<int>(config.cycle_orders[cycle].begin(),
                         config.cycle_orders[cycle].end()),
        allowed);
    if (data.cycle_matchings[cycle].size() != 2) {
      throw std::logic_error("component is not a four-cycle");
    }
    data.states[cycle] = LocalStates(config.cycle_orders[cycle]);
  }
  return data;
}

bool CompatibleKeys(const Matching& matching,
                    const std::array<int, kVertexCount>& colours,
                    const Prepared& data,
                    std::vector<std::tuple<int, int, int>>* keys) {
  keys->clear();
  for (const Edge& edge : matching) {
    const int code = EdgeCode(edge);
    const int anchor = data.anchor_colour[code];
    if (anchor >= 0) {
      if (colours[edge[0]] != anchor || colours[edge[1]] != anchor) return false;
    } else {
      const int residual = data.residual_index[code];
      if (residual < 0) throw std::logic_error("matching edge has no source");
      keys->emplace_back(residual, colours[edge[0]], colours[edge[1]]);
    }
  }
  return true;
}

struct BuiltModel {
  sat::CpModelBuilder model;
  std::array<sat::BoolVar, kSupportVariableCount> support;
  int term_variables = 0;
  int escape_variables = 0;
  std::array<int, 2> partition_group_sizes{};
};

void BuildModel(const Config& config, const Prepared& data,
                const Arguments& args, BuiltModel* built) {
  for (int index = 0; index < kSupportVariableCount; ++index) {
    built->support[index] = built->model.NewBoolVar();
  }
  auto variable = [&](int edge_index, int row, int column) {
    return built->support[9 * edge_index + 3 * row + column];
  };
  for (int edge_index = 0; edge_index < kResidualEdgeCount; ++edge_index) {
    sat::LinearExpr sum;
    for (int row = 0; row < 3; ++row) {
      for (int column = 0; column < 3; ++column) sum += variable(edge_index, row, column);
    }
    built->model.AddGreaterOrEqual(sum, 1);
  }

  std::vector<std::tuple<int, int, int>> keys;
  for (int colouring_index = 0; colouring_index < 6561; ++colouring_index) {
    const auto colours = GlobalColours(colouring_index);
    if (!Mixed(colours)) continue;
    std::vector<sat::BoolVar> terms;
    int fixed = 0;
    for (const Matching& matching : data.matchings) {
      if (!CompatibleKeys(matching, colours, data, &keys)) continue;
      if (keys.empty()) {
        ++fixed;
        continue;
      }
      std::vector<sat::BoolVar> values;
      values.reserve(keys.size());
      for (const auto& [edge_index, row, column] : keys) {
        values.push_back(variable(edge_index, row, column));
      }
      terms.push_back(Conjunction(&built->model, values));
      ++built->term_variables;
    }
    if (fixed >= 2) continue;
    sat::LinearExpr sum;
    for (const sat::BoolVar term : terms) sum += term;
    if (fixed == 1) {
      built->model.AddGreaterOrEqual(sum, 1);
    } else if (!terms.empty()) {
      built->model.AddNotEqual(sum, 1);
    }
  }

  std::array<std::array<sat::BoolVar, 81>, 2> cycle_one;
  for (int cycle = 0; cycle < 2; ++cycle) {
    for (int state_index = 0; state_index < 81; ++state_index) {
      const auto& state = data.states[cycle][state_index];
      std::array<sat::BoolVar, 2> terms;
      for (int matching_index = 0; matching_index < 2; ++matching_index) {
        std::vector<sat::BoolVar> values;
        for (const Edge& edge : data.cycle_matchings[cycle][matching_index]) {
          const int edge_index = data.residual_index[EdgeCode(edge)];
          values.push_back(variable(edge_index, state[edge[0]], state[edge[1]]));
        }
        terms[matching_index] = Conjunction(&built->model, values);
      }
      const sat::BoolVar one = built->model.NewBoolVar();
      built->model.AddLessOrEqual(one, sat::LinearExpr(terms[0]) + terms[1]);
      built->model.AddLessOrEqual(sat::LinearExpr(one) + terms[0] + terms[1], 2);
      built->model.AddGreaterOrEqual(one, sat::LinearExpr(terms[0]) - terms[1]);
      built->model.AddGreaterOrEqual(one, sat::LinearExpr(terms[1]) - terms[0]);
      cycle_one[cycle][state_index] = one;
    }
  }

  std::array<std::array<bool, 81>, 81> forbidden{};
  for (int first_index = 0; first_index < 81; ++first_index) {
    for (int second_index = 0; second_index < 81; ++second_index) {
      std::array<int, kVertexCount> colours{};
      for (int vertex = 0; vertex < kVertexCount; ++vertex) {
        const int first = data.states[0][first_index][vertex];
        colours[vertex] = first >= 0 ? first : data.states[1][second_index][vertex];
      }
      if (!Mixed(colours)) continue;
      bool has_cross = false;
      for (const Matching& matching : data.cross_matchings) {
        if (CompatibleKeys(matching, colours, data, &keys)) {
          has_cross = true;
          break;
        }
      }
      forbidden[first_index][second_index] = !has_cross;
    }
  }

  for (int source_cycle = 0; source_cycle < 2; ++source_cycle) {
    std::vector<sat::BoolVar> escapes;
    for (int target_state = 0; target_state < 81; ++target_state) {
      const sat::BoolVar escape = built->model.NewBoolVar();
      escapes.push_back(escape);
      ++built->escape_variables;
      sat::LinearExpr blocked_sum;
      for (int source_state = 0; source_state < 81; ++source_state) {
        const bool blocked = source_cycle == 0
                                 ? forbidden[source_state][target_state]
                                 : forbidden[target_state][source_state];
        if (!blocked) continue;
        built->model.AddLessOrEqual(
            sat::LinearExpr(escape) + cycle_one[source_cycle][source_state], 1);
        blocked_sum += cycle_one[source_cycle][source_state];
      }
      built->model.AddGreaterOrEqual(escape, 1 - blocked_sum);
    }
    built->model.AddBoolOr(escapes);
  }

  sat::LinearExpr support_sum;
  for (const sat::BoolVar value : built->support) support_sum += value;
  built->model.AddEquality(support_sum, args.support);

  const auto groups = PartitionGroups(kSupportVariableCount);
  for (int bit = 0; bit < 2; ++bit) {
    sat::LinearExpr group_sum;
    for (const int index : groups[bit]) group_sum += built->support[index];
    const sat::IntVar remainder = built->model.NewIntVar(operations_research::Domain(0, 1));
    built->model.AddModuloEquality(remainder, group_sum, 2);
    built->model.AddEquality(remainder, (args.shard_id >> bit) & 1);
    built->partition_group_sizes[bit] = static_cast<int>(groups[bit].size());
  }
}

Arguments ParseArguments(int argc, char** argv) {
  Arguments args;
  for (int index = 1; index < argc; ++index) {
    const std::string key = argv[index];
    if (index + 1 >= argc) throw std::invalid_argument("missing value for " + key);
    const std::string value = argv[++index];
    if (key == "--run-id") args.run_id = value;
    else if (key == "--case") args.case_id = std::stoi(value);
    else if (key == "--support") args.support = std::stoi(value);
    else if (key == "--shard-id") args.shard_id = std::stoi(value);
    else if (key == "--shard-count") args.shard_count = std::stoi(value);
    else if (key == "--seconds") args.seconds = std::stod(value);
    else if (key == "--cap") args.cap = std::stoull(value);
    else if (key == "--checkpoint-every") args.checkpoint_every = std::stoull(value);
    else if (key == "--checkpoint-seconds") args.checkpoint_seconds = std::stod(value);
    else if (key == "--output") args.output = value;
    else throw std::invalid_argument("unknown argument: " + key);
  }
  if (args.run_id.empty() || args.case_id < 0 || args.support < 0 || args.support > 72 ||
      args.shard_count != 4 || args.shard_id < 0 || args.shard_id >= 4 ||
      args.seconds <= 0 || args.cap == 0 || args.output.empty()) {
    throw std::invalid_argument("invalid or missing arguments");
  }
  return args;
}

class Collector {
 public:
  Collector(const Config& config, const std::vector<Symmetry>& symmetries,
            const Arguments& args, const BuiltModel& built)
      : config_(config),
        symmetries_(symmetries),
        args_(args),
        support_(built.support),
        term_variables_(built.term_variables),
        escape_variables_(built.escape_variables),
        partition_group_sizes_(built.partition_group_sizes),
        started_(std::chrono::steady_clock::now()),
        next_checkpoint_(
            started_ + std::chrono::duration_cast<std::chrono::steady_clock::duration>(
                           std::chrono::duration<double>(args.checkpoint_seconds))) {}

  void Observe(const sat::CpSolverResponse& response, sat::Model* model) {
    ++raw_;
    Masks masks{};
    for (int edge_index = 0; edge_index < kResidualEdgeCount; ++edge_index) {
      for (int row = 0; row < 3; ++row) {
        for (int column = 0; column < 3; ++column) {
          const int index = 9 * edge_index + 3 * row + column;
          if (sat::SolutionBooleanValue(response, support_[index])) {
            masks[edge_index] |= std::uint16_t{1} << (3 * row + column);
          }
        }
      }
    }
    ++orbits_[Canonical(masks, config_, symmetries_)];
    const auto now = std::chrono::steady_clock::now();
    if (raw_ >= args_.cap) {
      hit_cap_ = true;
      Write("CAP_REACHED", false, response);
      sat::StopSearch(model);
    } else if (Elapsed(now) >= args_.seconds) {
      hit_deadline_ = true;
      Write("DEADLINE_REACHED", false, response);
      sat::StopSearch(model);
    } else if (g_signal_requested.load()) {
      hit_signal_ = true;
      Write("SIGNAL_RECEIVED", false, response);
      sat::StopSearch(model);
    } else if ((args_.checkpoint_every > 0 && raw_ % args_.checkpoint_every == 0) ||
               now >= next_checkpoint_) {
      Write("RUNNING", false, response);
      next_checkpoint_ =
          now + std::chrono::duration_cast<std::chrono::steady_clock::duration>(
                    std::chrono::duration<double>(args_.checkpoint_seconds));
    }
  }

  void InitialCheckpoint() {
    sat::CpSolverResponse empty;
    Write("STARTING", false, empty);
  }

  void Finalize(const sat::CpSolverResponse& response) {
    const bool complete =
        (response.status() == sat::CpSolverStatus::OPTIMAL ||
         response.status() == sat::CpSolverStatus::INFEASIBLE) &&
        !hit_cap_ && !hit_deadline_ && !hit_signal_;
    if (!complete && !hit_cap_ && !hit_signal_) hit_deadline_ = true;
    Write(sat::CpSolverStatus_Name(response.status()), complete, response);
  }

  bool Complete(const sat::CpSolverResponse& response) const {
    return (response.status() == sat::CpSolverStatus::OPTIMAL ||
            response.status() == sat::CpSolverStatus::INFEASIBLE) &&
           !hit_cap_ && !hit_deadline_ && !hit_signal_;
  }

 private:
  double Elapsed(std::chrono::steady_clock::time_point now) const {
    return std::chrono::duration<double>(now - started_).count();
  }

  void Write(const std::string& status, bool complete,
             const sat::CpSolverResponse& response) const {
    fs::create_directories(args_.output.parent_path());
    fs::path temporary = args_.output;
    temporary += ".tmp";
    std::ofstream stream(temporary, std::ios::binary | std::ios::trunc);
    if (!stream) throw std::runtime_error("cannot open checkpoint");
    stream << "{\n"
           << "  \"schema_version\": 1,\n"
           << "  \"run_id\": \"" << args_.run_id << "\",\n"
           << "  \"mode\": \"exact_support_layer\",\n"
           << "  \"case\": " << config_.case_id << ",\n"
           << "  \"orbit\": " << config_.orbit_id << ",\n"
           << "  \"support\": " << args_.support << ",\n"
           << "  \"shard_id\": " << args_.shard_id << ",\n"
           << "  \"shard_count\": " << args_.shard_count << ",\n"
           << "  \"partition_version\": \"" << kPartitionVersion << "\",\n"
           << "  \"partition_group_sizes\": [" << partition_group_sizes_[0]
           << ", " << partition_group_sizes_[1] << "],\n"
           << "  \"stabilizer_size\": " << symmetries_.size() << ",\n"
           << "  \"term_variables\": " << term_variables_ << ",\n"
           << "  \"escape_variables\": " << escape_variables_ << ",\n"
           << "  \"status\": \"" << status << "\",\n"
           << "  \"complete_enumeration\": " << (complete ? "true" : "false") << ",\n"
           << "  \"hit_cap\": " << (hit_cap_ ? "true" : "false") << ",\n"
           << "  \"hit_deadline\": " << (hit_deadline_ ? "true" : "false") << ",\n"
           << "  \"hit_signal\": " << (hit_signal_ ? "true" : "false") << ",\n"
           << "  \"wall_seconds\": " << Elapsed(std::chrono::steady_clock::now()) << ",\n"
           << "  \"raw_supports\": " << raw_ << ",\n"
           << "  \"support_orbits\": " << orbits_.size() << ",\n"
           << "  \"branches\": " << response.num_branches() << ",\n"
           << "  \"conflicts\": " << response.num_conflicts() << ",\n"
           << "  \"orbits\": [\n";
    std::size_t orbit_index = 0;
    for (const auto& [masks, multiplicity] : orbits_) {
      stream << "    {\"masks\": [";
      for (int index = 0; index < kResidualEdgeCount; ++index) {
        if (index) stream << ", ";
        stream << masks[index];
      }
      stream << "], \"edge_sizes\": [";
      for (int index = 0; index < kResidualEdgeCount; ++index) {
        if (index) stream << ", ";
        stream << std::popcount(masks[index]);
      }
      stream << "], \"labelled_multiplicity\": " << multiplicity << "}";
      if (++orbit_index != orbits_.size()) stream << ',';
      stream << '\n';
    }
    stream << "  ]\n}\n";
    stream.close();
    if (!stream) throw std::runtime_error("checkpoint write failed");
    std::error_code error;
    fs::remove(args_.output, error);
    error.clear();
    fs::rename(temporary, args_.output, error);
    if (error) throw std::runtime_error("atomic checkpoint rename failed: " + error.message());
  }

  const Config& config_;
  const std::vector<Symmetry>& symmetries_;
  const Arguments& args_;
  const std::array<sat::BoolVar, kSupportVariableCount>& support_;
  int term_variables_;
  int escape_variables_;
  std::array<int, 2> partition_group_sizes_;
  std::chrono::steady_clock::time_point started_;
  std::chrono::steady_clock::time_point next_checkpoint_;
  std::uint64_t raw_ = 0;
  std::map<Masks, std::uint64_t> orbits_;
  bool hit_cap_ = false;
  bool hit_deadline_ = false;
  bool hit_signal_ = false;
};

}  // namespace

int main(int argc, char** argv) {
  try {
    const Arguments args = ParseArguments(argc, argv);
    int google_argc = 1;
    char* google_argv_storage[] = {argv[0], nullptr};
    char** google_argv = google_argv_storage;
    InitGoogle(google_argv[0], &google_argc, &google_argv, true);
    const Config config = GetConfig(args.case_id);
    const Prepared prepared = Prepare(config);
    const std::vector<Symmetry> symmetries = Stabilizer(config);
    BuiltModel built;
    BuildModel(config, prepared, args, &built);
    Collector collector(config, symmetries, args, built);
    collector.InitialCheckpoint();

    std::signal(SIGTERM, HandleSignal);
    std::signal(SIGINT, HandleSignal);

    sat::SatParameters parameters;
    parameters.set_enumerate_all_solutions(true);
    parameters.set_num_search_workers(1);
    parameters.set_max_time_in_seconds(args.seconds);
    parameters.set_random_seed(1);

    sat::Model model;
    model.Add(sat::NewSatParameters(parameters));
    model.Add(sat::NewFeasibleSolutionObserver(
        [&](const sat::CpSolverResponse& response) { collector.Observe(response, &model); }));
    const sat::CpSolverResponse response = sat::SolveCpModel(built.model.Build(), &model);
    collector.Finalize(response);
    std::cout << "{\"case\":" << config.case_id << ",\"support\":" << args.support
              << ",\"shard\":" << args.shard_id << ",\"status\":\""
              << sat::CpSolverStatus_Name(response.status()) << "\",\"complete\":"
              << (collector.Complete(response) ? "true" : "false") << "}\n";
    return collector.Complete(response) ? 0 : 2;
  } catch (const std::exception& error) {
    std::cerr << "run-033 worker error: " << error.what() << '\n';
    return 1;
  }
}
