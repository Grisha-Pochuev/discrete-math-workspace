#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <tuple>
#include <utility>
#include <vector>

#include "ortools/base/init_google.h"
#include "ortools/sat/cp_model.h"
#include "ortools/sat/cp_model_solver.h"
#include "ortools/sat/model.h"
#include "ortools/sat/sat_parameters.pb.h"

namespace sat = operations_research::sat;

namespace {

constexpr int kVertices = 8;
constexpr int kColours = 3;

using Edge = std::pair<int, int>;
using Matching = std::vector<int>;
using State = std::array<int, kVertices>;
using Signature = std::vector<int>;

struct Arguments {
  std::string run_id;
  std::string graph;
  double seconds = 300.0;
  int rounds = 20;
  int workers = 4;
  int memory_mib = 6000;
  int shard_id = -1;
  int shard_count = 4;
  std::string output;
};

struct PairEvent {
  int state;
  int left;
  int right;
};

Edge CanonicalEdge(int a, int b) {
  return a < b ? Edge{a, b} : Edge{b, a};
}

State Decode(int value) {
  State result{};
  for (int vertex = 0; vertex < kVertices; ++vertex) {
    result[vertex] = value % kColours;
    value /= kColours;
  }
  return result;
}

bool Pure(const State& state) {
  return std::all_of(state.begin() + 1, state.end(),
                     [&](int colour) { return colour == state[0]; });
}

std::vector<std::vector<int>> MissingCycles(const std::string& graph) {
  if (graph == "C8") return {{0, 1, 2, 3, 4, 5, 6, 7}};
  if (graph == "C5+C3") return {{0, 1, 2, 3, 4}, {5, 6, 7}};
  if (graph == "C4+C4") return {{0, 1, 2, 3}, {4, 5, 6, 7}};
  throw std::invalid_argument("unknown graph type");
}

std::vector<Edge> GraphEdges(const std::string& graph) {
  std::set<Edge> missing;
  for (const auto& cycle : MissingCycles(graph)) {
    for (int index = 0; index < static_cast<int>(cycle.size()); ++index) {
      missing.insert(CanonicalEdge(cycle[index], cycle[(index + 1) % cycle.size()]));
    }
  }
  std::vector<Edge> edges;
  for (int a = 0; a < kVertices; ++a) {
    for (int b = a + 1; b < kVertices; ++b) {
      if (!missing.contains({a, b})) edges.push_back({a, b});
    }
  }
  if (edges.size() != 20) throw std::logic_error("edge count mismatch");
  for (int vertex = 0; vertex < kVertices; ++vertex) {
    const int degree = std::count_if(edges.begin(), edges.end(),
                                     [&](Edge edge) {
                                       return edge.first == vertex || edge.second == vertex;
                                     });
    if (degree != 5) throw std::logic_error("degree mismatch");
  }
  return edges;
}

void MatchingRec(const std::vector<int>& vertices,
                 const std::map<Edge, int>& edge_index,
                 Matching* current, std::vector<Matching>* result) {
  if (vertices.empty()) {
    result->push_back(*current);
    return;
  }
  const int first = vertices.front();
  for (int position = 1; position < static_cast<int>(vertices.size()); ++position) {
    const int other = vertices[position];
    const auto found = edge_index.find(CanonicalEdge(first, other));
    if (found == edge_index.end()) continue;
    std::vector<int> rest;
    for (int vertex : vertices) {
      if (vertex != first && vertex != other) rest.push_back(vertex);
    }
    current->push_back(found->second);
    MatchingRec(rest, edge_index, current, result);
    current->pop_back();
  }
}

std::vector<Matching> PerfectMatchings(const std::vector<Edge>& edges) {
  std::map<Edge, int> edge_index;
  for (int index = 0; index < static_cast<int>(edges.size()); ++index) {
    edge_index[edges[index]] = index;
  }
  std::vector<int> vertices(kVertices);
  for (int vertex = 0; vertex < kVertices; ++vertex) vertices[vertex] = vertex;
  Matching current;
  std::vector<Matching> result;
  MatchingRec(vertices, edge_index, &current, &result);
  return result;
}

Signature CanonicalRatio(const std::vector<int>& left,
                         const std::vector<int>& right) {
  std::map<int, int> counts;
  for (int key : left) ++counts[key];
  for (int key : right) --counts[key];
  Signature forward;
  Signature backward;
  for (const auto& [key, count] : counts) {
    if (count == 0) continue;
    forward.push_back(key);
    forward.push_back(count);
    backward.push_back(key);
    backward.push_back(-count);
  }
  return std::min(forward, backward);
}

sat::BoolVar Conjunction(sat::CpModelBuilder* model,
                         const std::vector<sat::BoolVar>& values) {
  if (values.empty()) throw std::invalid_argument("empty conjunction");
  const sat::BoolVar term = model->NewBoolVar();
  sat::LinearExpr sum;
  for (sat::BoolVar value : values) {
    model->AddLessOrEqual(term, value);
    sum += value;
  }
  model->AddGreaterOrEqual(term, sum - static_cast<int64_t>(values.size()) + 1);
  return term;
}

class AdaptiveScreen {
 public:
  explicit AdaptiveScreen(Arguments arguments)
      : args_(std::move(arguments)), edges_(GraphEdges(args_.graph)),
        matchings_(PerfectMatchings(edges_)) {
    const std::map<std::string, int> expected{{"C8", 31}, {"C5+C3", 30},
                                              {"C4+C4", 33}};
    if (matchings_.size() != expected.at(args_.graph)) {
      throw std::logic_error("matching count mismatch");
    }
    BuildIncidence();
    BuildModel();
    model_.AddEquality(support_[0][0][0], args_.shard_id & 1);
    model_.AddEquality(support_[0][0][1], (args_.shard_id >> 1) & 1);
  }

  int Run() {
    const auto started = std::chrono::steady_clock::now();
    for (int round = 0; round <= args_.rounds; ++round) {
      last_direct_ = 0;
      sat::SatParameters parameters;
      parameters.set_num_search_workers(args_.workers);
      parameters.set_max_time_in_seconds(args_.seconds);
      parameters.set_random_seed(1);
      parameters.set_max_memory_in_mb(args_.memory_mib);

      sat::Model solver_model;
      solver_model.Add(sat::NewSatParameters(parameters));
      last_response_ = sat::SolveCpModel(model_.Build(), &solver_model);
      ++solve_rounds_;
      total_branches_ += last_response_.num_branches();
      total_conflicts_ += last_response_.num_conflicts();
      round_statuses_.push_back(sat::CpSolverStatus_Name(last_response_.status()));
      round_wall_.push_back(last_response_.wall_time());

      if (!Feasible(last_response_)) break;
      const auto [binomials, trinomials] = CurrentEvents(last_response_);
      std::vector<Signature> conflicts;
      for (const auto& [signature, left_events] : binomials) {
        const auto found = trinomials.find(signature);
        if (found == trinomials.end()) continue;
        conflicts.push_back(signature);
        last_direct_ += static_cast<std::uint64_t>(left_events.size()) *
                        static_cast<std::uint64_t>(found->second.size());
      }
      if (conflicts.empty() || round == args_.rounds) break;
      int learned = 0;
      for (const Signature& signature : conflicts) {
        sat::BoolVar mode = RatioMode(signature);
        for (const PairEvent& event : binomials.at(signature)) {
          const auto key = std::tuple{event.state, event.left, event.right};
          if (!learned_binomials_.insert(key).second) continue;
          model_.AddBoolOr({RowCount(event.state, 2).Not(),
                            terms_.at(event.state)[event.left].Not(),
                            terms_.at(event.state)[event.right].Not(), mode});
          ++learned;
        }
        for (const PairEvent& event : trinomials.at(signature)) {
          const auto key = std::tuple{event.state, event.left, event.right};
          if (!learned_trinomials_.insert(key).second) continue;
          model_.AddBoolOr({RowCount(event.state, 3).Not(),
                            terms_.at(event.state)[event.left].Not(),
                            terms_.at(event.state)[event.right].Not(), mode.Not()});
          ++learned;
        }
      }
      if (learned == 0) throw std::logic_error("conflict round learned no clause");
    }
    total_wall_ = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    WriteOutput();
    std::cout << "{\"run_id\":\"" << args_.run_id << "\",\"graph\":\""
              << args_.graph << "\",\"status\":\""
              << sat::CpSolverStatus_Name(last_response_.status())
              << "\",\"rounds\":" << solve_rounds_
              << ",\"direct\":" << last_direct_ << "}\n";
    return last_response_.status() == sat::CpSolverStatus::UNKNOWN ? 2 : 0;
  }

 private:
  void BuildIncidence() {
    for (int edge = 0; edge < static_cast<int>(edges_.size()); ++edge) {
      incident_[edges_[edge].first].push_back(edge);
      incident_[edges_[edge].second].push_back(edge);
    }
  }

  int SupportId(int edge, int row, int column) const {
    return 9 * edge + 3 * row + column;
  }

  sat::BoolVar Entry(int edge, int root, int root_colour,
                     int neighbour_colour) const {
    if (edges_[edge].first == root) {
      return support_[edge][root_colour][neighbour_colour];
    }
    if (edges_[edge].second != root) throw std::logic_error("nonincident edge");
    return support_[edge][neighbour_colour][root_colour];
  }

  int EntryId(int edge, int root, int root_colour, int neighbour_colour) const {
    if (edges_[edge].first == root) {
      return SupportId(edge, root_colour, neighbour_colour);
    }
    if (edges_[edge].second != root) throw std::logic_error("nonincident edge");
    return SupportId(edge, neighbour_colour, root_colour);
  }

  sat::BoolVar Anchor(int vertex, int edge, int colour) const {
    return anchors_.at(std::tuple{vertex, edge, colour});
  }

  sat::BoolVar Assignment(int vertex, int colour, int edge) const {
    return assignments_.at(std::tuple{vertex, colour, edge});
  }

  void BuildModel() {
    support_.resize(edges_.size());
    for (int edge = 0; edge < static_cast<int>(edges_.size()); ++edge) {
      sat::LinearExpr nonzero;
      for (int row = 0; row < kColours; ++row) {
        for (int column = 0; column < kColours; ++column) {
          support_[edge][row][column] = model_.NewBoolVar();
          nonzero += support_[edge][row][column];
        }
      }
      model_.AddGreaterOrEqual(nonzero, 1);
    }

    for (int vertex = 0; vertex < kVertices; ++vertex) {
      for (int colour = 0; colour < kColours; ++colour) {
        noncoordinate_[vertex][colour] = model_.NewBoolVar();
        for (int row = 0; row < kColours; ++row) {
          anchor_support_[vertex][colour][row] = model_.NewBoolVar();
        }
      }
      for (int edge : incident_[vertex]) {
        for (int colour = 0; colour < kColours; ++colour) {
          anchors_.emplace(std::tuple{vertex, edge, colour}, model_.NewBoolVar());
        }
      }
    }

    for (int vertex = 0; vertex < kVertices; ++vertex) {
      for (int colour = 0; colour < kColours; ++colour) {
        sat::LinearExpr exactly_one;
        for (int edge : incident_[vertex]) exactly_one += Anchor(vertex, edge, colour);
        model_.AddEquality(exactly_one, 1);
      }
      for (int edge : incident_[vertex]) {
        sat::LinearExpr at_most_one;
        for (int colour = 0; colour < kColours; ++colour) {
          at_most_one += Anchor(vertex, edge, colour);
          const sat::BoolVar chosen = Anchor(vertex, edge, colour);
          for (int row = 0; row < kColours; ++row) {
            model_.AddEquality(anchor_support_[vertex][colour][row],
                               Entry(edge, vertex, row, colour))
                .OnlyEnforceIf(chosen);
            for (int column = 0; column < kColours; ++column) {
              if (column != colour) {
                model_.AddEquality(Entry(edge, vertex, row, column), 0)
                    .OnlyEnforceIf(chosen);
              }
            }
          }
        }
        model_.AddLessOrEqual(at_most_one, 1);
      }
      for (int colour = 0; colour < kColours; ++colour) {
        sat::LinearExpr size;
        for (int row = 0; row < kColours; ++row) {
          size += anchor_support_[vertex][colour][row];
        }
        model_.AddGreaterOrEqual(size, 2).OnlyEnforceIf(noncoordinate_[vertex][colour]);
        model_.AddLessOrEqual(size, 1).OnlyEnforceIf(noncoordinate_[vertex][colour].Not());
      }
    }
    sat::LinearExpr some_noncoordinate;
    for (int vertex = 0; vertex < kVertices; ++vertex) {
      for (int colour = 0; colour < kColours; ++colour) {
        some_noncoordinate += noncoordinate_[vertex][colour];
      }
    }
    model_.AddGreaterOrEqual(some_noncoordinate, 1);

    for (int vertex = 0; vertex < kVertices; ++vertex) {
      for (int colour = 0; colour < kColours; ++colour) {
        for (int edge : incident_[vertex]) {
          assignments_.emplace(std::tuple{vertex, colour, edge}, model_.NewBoolVar());
        }
        sat::LinearExpr assigned_once;
        for (int edge : incident_[vertex]) assigned_once += Assignment(vertex, colour, edge);
        model_.AddEquality(assigned_once, noncoordinate_[vertex][colour]);
      }
      for (int edge : incident_[vertex]) {
        sat::LinearExpr assignment_capacity;
        sat::LinearExpr rooted_anchor;
        for (int colour = 0; colour < kColours; ++colour) {
          assignment_capacity += Assignment(vertex, colour, edge);
          rooted_anchor += Anchor(vertex, edge, colour);
        }
        model_.AddLessOrEqual(assignment_capacity, 2);
        for (int colour = 0; colour < kColours; ++colour) {
          const sat::BoolVar assigned = Assignment(vertex, colour, edge);
          model_.AddLessOrEqual(assigned + rooted_anchor, 1);
          for (int column = 0; column < kColours; ++column) {
            if (column == colour) continue;
            const sat::BoolVar column_on = model_.NewBoolVar();
            ++assignment_column_variables_;
            for (int row = 0; row < kColours; ++row) {
              const sat::BoolVar value = Entry(edge, vertex, row, column);
              const sat::BoolVar p_value = anchor_support_[vertex][colour][row];
              model_.AddLessOrEqual(value, p_value).OnlyEnforceIf(assigned);
              model_.AddLessOrEqual(value, column_on).OnlyEnforceIf(assigned);
              model_.AddGreaterOrEqual(value, p_value + column_on - 1)
                  .OnlyEnforceIf(assigned);
            }
          }
        }
      }
    }

    for (int state_value = 0; state_value < 6561; ++state_value) {
      const State state = Decode(state_value);
      if (Pure(state)) continue;
      std::vector<sat::BoolVar> row_terms;
      std::vector<std::vector<int>> row_keys;
      for (const Matching& matching : matchings_) {
        std::vector<sat::BoolVar> values;
        std::vector<int> keys;
        for (int edge : matching) {
          const auto [a, b] = edges_[edge];
          values.push_back(support_[edge][state[a]][state[b]]);
          keys.push_back(SupportId(edge, state[a], state[b]));
        }
        row_terms.push_back(Conjunction(&model_, values));
        row_keys.push_back(std::move(keys));
        ++term_variables_;
      }
      sat::LinearExpr count;
      for (sat::BoolVar term : row_terms) count += term;
      model_.AddNotEqual(count, 1);
      terms_.emplace(state_value, std::move(row_terms));
      term_keys_.emplace(state_value, std::move(row_keys));
    }
  }

  bool Feasible(const sat::CpSolverResponse& response) const {
    return response.status() == sat::CpSolverStatus::OPTIMAL ||
           response.status() == sat::CpSolverStatus::FEASIBLE;
  }

  bool Value(const sat::CpSolverResponse& response, sat::BoolVar variable) const {
    return sat::SolutionBooleanValue(response, variable);
  }

  sat::BoolVar RowCount(int state, int count) {
    const auto key = std::pair{state, count};
    const auto found = row_count_.find(key);
    if (found != row_count_.end()) return found->second;
    const sat::BoolVar literal = model_.NewBoolVar();
    sat::LinearExpr sum;
    for (sat::BoolVar term : terms_.at(state)) sum += term;
    model_.AddEquality(sum, count).OnlyEnforceIf(literal);
    model_.AddNotEqual(sum, count).OnlyEnforceIf(literal.Not());
    row_count_.emplace(key, literal);
    return literal;
  }

  sat::BoolVar RatioMode(const Signature& signature) {
    const auto found = ratio_modes_.find(signature);
    if (found != ratio_modes_.end()) return found->second;
    const sat::BoolVar mode = model_.NewBoolVar();
    ratio_modes_.emplace(signature, mode);
    return mode;
  }

  std::pair<std::map<Signature, std::vector<PairEvent>>,
            std::map<Signature, std::vector<PairEvent>>>
  CurrentEvents(const sat::CpSolverResponse& response) const {
    std::map<Signature, std::vector<PairEvent>> binomials;
    std::map<Signature, std::vector<PairEvent>> trinomials;
    for (const auto& [state, row_terms] : terms_) {
      std::vector<int> supported;
      for (int index = 0; index < static_cast<int>(row_terms.size()); ++index) {
        if (Value(response, row_terms[index])) supported.push_back(index);
      }
      if (supported.size() == 2) {
        const int left = supported[0];
        const int right = supported[1];
        const Signature signature = CanonicalRatio(term_keys_.at(state)[left],
                                                   term_keys_.at(state)[right]);
        binomials[signature].push_back({state, left, right});
      } else if (supported.size() == 3) {
        for (int i = 0; i < 3; ++i) {
          for (int j = i + 1; j < 3; ++j) {
            const int left = supported[i];
            const int right = supported[j];
            const Signature signature = CanonicalRatio(term_keys_.at(state)[left],
                                                       term_keys_.at(state)[right]);
            trinomials[signature].push_back({state, left, right});
          }
        }
      }
    }
    return {std::move(binomials), std::move(trinomials)};
  }

  std::string ScreenState() const {
    if (last_response_.status() == sat::CpSolverStatus::INFEASIBLE) return "infeasible";
    if (last_response_.status() == sat::CpSolverStatus::UNKNOWN) return "unknown";
    if (Feasible(last_response_) && last_direct_ == 0) return "exchange_clean_candidate";
    if (Feasible(last_response_)) return "rejected_candidate";
    return "other";
  }

  static std::string JsonString(const std::string& value) {
    std::ostringstream out;
    out << '"';
    for (char ch : value) {
      if (ch == '"' || ch == '\\') out << '\\';
      out << ch;
    }
    out << '"';
    return out.str();
  }

  void WriteOutput() const {
    std::ostringstream out;
    out << "{\n";
    out << "  \"schema_version\": 1,\n";
    out << "  \"run_id\": " << JsonString(args_.run_id) << ",\n";
    out << "  \"graph\": " << JsonString(args_.graph) << ",\n";
    out << "  \"status\": "
        << JsonString(sat::CpSolverStatus_Name(last_response_.status())) << ",\n";
    out << "  \"screen_state\": " << JsonString(ScreenState()) << ",\n";
    out << "  \"solve_rounds\": " << solve_rounds_ << ",\n";
    out << "  \"requested_exchange_rounds\": " << args_.rounds << ",\n";
    out << "  \"seconds_per_round\": " << args_.seconds << ",\n";
    out << "  \"workers\": " << args_.workers << ",\n";
    out << "  \"memory_mib\": " << args_.memory_mib << ",\n";
    out << "  \"shard_id\": " << args_.shard_id << ",\n";
    out << "  \"shard_count\": " << args_.shard_count << ",\n";
    out << "  \"partition\": \"first-edge-bits-v1\",\n";
    out << "  \"wall_seconds\": " << total_wall_ << ",\n";
    out << "  \"branches\": " << total_branches_ << ",\n";
    out << "  \"conflicts\": " << total_conflicts_ << ",\n";
    out << "  \"perfect_matchings\": " << matchings_.size() << ",\n";
    out << "  \"mixed_rows\": 6558,\n";
    out << "  \"term_variables\": " << term_variables_ << ",\n";
    out << "  \"support_variables\": 180,\n";
    out << "  \"anchor_variables\": 120,\n";
    out << "  \"anchor_support_variables\": 72,\n";
    out << "  \"noncoordinate_variables\": 24,\n";
    out << "  \"assignment_variables\": 120,\n";
    out << "  \"assignment_column_variables\": " << assignment_column_variables_ << ",\n";
    out << "  \"learned_binomial_events\": " << learned_binomials_.size() << ",\n";
    out << "  \"learned_trinomial_events\": " << learned_trinomials_.size() << ",\n";
    out << "  \"learned_ratio_classes\": " << ratio_modes_.size() << ",\n";
    out << "  \"direct_exchange_contradictions\": " << last_direct_ << ",\n";
    out << "  \"round_statuses\": [";
    for (int i = 0; i < static_cast<int>(round_statuses_.size()); ++i) {
      if (i) out << ',';
      out << JsonString(round_statuses_[i]);
    }
    out << "],\n  \"round_wall_seconds\": [";
    for (int i = 0; i < static_cast<int>(round_wall_.size()); ++i) {
      if (i) out << ',';
      out << round_wall_[i];
    }
    out << ']';

    if (Feasible(last_response_)) {
      int active_entries = 0;
      int noncoordinate_count = 0;
      std::array<int, 32> histogram{};
      for (const auto& [state, row_terms] : terms_) {
        int count = 0;
        for (sat::BoolVar term : row_terms) count += Value(last_response_, term);
        ++histogram[count];
      }
      out << ",\n  \"support_masks\": [";
      for (int edge = 0; edge < static_cast<int>(edges_.size()); ++edge) {
        int mask = 0;
        for (int row = 0; row < kColours; ++row) {
          for (int column = 0; column < kColours; ++column) {
            if (Value(last_response_, support_[edge][row][column])) {
              mask |= 1 << (3 * row + column);
              ++active_entries;
            }
          }
        }
        if (edge) out << ',';
        out << mask;
      }
      out << "],\n  \"anchors\": [";
      bool first_anchor = true;
      for (int vertex = 0; vertex < kVertices; ++vertex) {
        for (int colour = 0; colour < kColours; ++colour) {
          int selected = -1;
          for (int edge : incident_[vertex]) {
            if (Value(last_response_, Anchor(vertex, edge, colour))) selected = edge;
          }
          if (selected < 0) throw std::logic_error("missing selected anchor");
          int column_size = 0;
          for (int row = 0; row < kColours; ++row) {
            column_size += Value(last_response_, Entry(selected, vertex, row, colour));
          }
          const bool nc = column_size >= 2;
          noncoordinate_count += nc;
          if (!first_anchor) out << ',';
          first_anchor = false;
          const int neighbour = edges_[selected].first == vertex
                                    ? edges_[selected].second : edges_[selected].first;
          out << "{\"vertex\":" << vertex << ",\"colour\":" << colour
              << ",\"neighbour\":" << neighbour << ",\"column_size\":"
              << column_size << ",\"noncoordinate\":" << (nc ? "true" : "false") << '}';
        }
      }
      out << "],\n  \"assignments\": [";
      bool first_assignment = true;
      for (int vertex = 0; vertex < kVertices; ++vertex) {
        for (int colour = 0; colour < kColours; ++colour) {
          for (int edge : incident_[vertex]) {
            if (!Value(last_response_, Assignment(vertex, colour, edge))) continue;
            if (!first_assignment) out << ',';
            first_assignment = false;
            const int neighbour = edges_[edge].first == vertex
                                      ? edges_[edge].second : edges_[edge].first;
            out << "{\"vertex\":" << vertex << ",\"colour\":" << colour
                << ",\"neighbour\":" << neighbour << '}';
          }
        }
      }
      out << "],\n  \"matching_histogram\": {";
      bool first_histogram = true;
      for (int count = 0; count < static_cast<int>(histogram.size()); ++count) {
        if (histogram[count] == 0) continue;
        if (!first_histogram) out << ',';
        first_histogram = false;
        out << JsonString(std::to_string(count)) << ':' << histogram[count];
      }
      out << "},\n  \"active_entries\": " << active_entries
          << ",\n  \"noncoordinate_anchors\": " << noncoordinate_count;
    }
    out << "\n}\n";

    const std::filesystem::path target(args_.output);
    const std::filesystem::path temporary = target.string() + ".tmp";
    {
      std::ofstream file(temporary, std::ios::binary | std::ios::trunc);
      if (!file) throw std::runtime_error("cannot open output");
      file << out.str();
      if (!file) throw std::runtime_error("cannot write output");
    }
    std::error_code error;
    std::filesystem::remove(target, error);
    error.clear();
    std::filesystem::rename(temporary, target, error);
    if (error) throw std::runtime_error("cannot install output: " + error.message());
  }

  Arguments args_;
  std::vector<Edge> edges_;
  std::vector<Matching> matchings_;
  std::array<std::vector<int>, kVertices> incident_;
  sat::CpModelBuilder model_;
  std::vector<std::array<std::array<sat::BoolVar, kColours>, kColours>> support_;
  std::map<std::tuple<int, int, int>, sat::BoolVar> anchors_;
  std::array<std::array<std::array<sat::BoolVar, kColours>, kColours>, kVertices>
      anchor_support_;
  std::array<std::array<sat::BoolVar, kColours>, kVertices> noncoordinate_;
  std::map<std::tuple<int, int, int>, sat::BoolVar> assignments_;
  std::map<int, std::vector<sat::BoolVar>> terms_;
  std::map<int, std::vector<std::vector<int>>> term_keys_;
  std::map<std::pair<int, int>, sat::BoolVar> row_count_;
  std::map<Signature, sat::BoolVar> ratio_modes_;
  std::set<std::tuple<int, int, int>> learned_binomials_;
  std::set<std::tuple<int, int, int>> learned_trinomials_;
  int assignment_column_variables_ = 0;
  int term_variables_ = 0;
  int solve_rounds_ = 0;
  std::int64_t total_branches_ = 0;
  std::int64_t total_conflicts_ = 0;
  std::uint64_t last_direct_ = 0;
  double total_wall_ = 0;
  std::vector<std::string> round_statuses_;
  std::vector<double> round_wall_;
  sat::CpSolverResponse last_response_;
};

Arguments ParseArguments(int argc, char** argv) {
  Arguments args;
  for (int index = 1; index < argc; index += 2) {
    if (index + 1 >= argc) throw std::invalid_argument("missing argument value");
    const std::string key = argv[index];
    const std::string value = argv[index + 1];
    if (key == "--run-id") args.run_id = value;
    else if (key == "--graph") args.graph = value;
    else if (key == "--seconds") args.seconds = std::stod(value);
    else if (key == "--rounds") args.rounds = std::stoi(value);
    else if (key == "--workers") args.workers = std::stoi(value);
    else if (key == "--memory-mib") args.memory_mib = std::stoi(value);
    else if (key == "--shard-id") args.shard_id = std::stoi(value);
    else if (key == "--shard-count") args.shard_count = std::stoi(value);
    else if (key == "--output") args.output = value;
    else throw std::invalid_argument("unknown argument: " + key);
  }
  if (args.run_id.empty() || args.output.empty() ||
      !std::set<std::string>{"C8", "C5+C3", "C4+C4"}.contains(args.graph) ||
      args.seconds <= 0 || args.rounds < 0 || args.workers < 1 ||
      args.workers > 4 || args.memory_mib < 512 || args.shard_count != 4 ||
      args.shard_id < 0 || args.shard_id >= args.shard_count) {
    throw std::invalid_argument("invalid or missing arguments");
  }
  return args;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const Arguments args = ParseArguments(argc, argv);
    int google_argc = 1;
    char* google_argv_storage[] = {argv[0], nullptr};
    char** google_argv = google_argv_storage;
    InitGoogle(google_argv[0], &google_argc, &google_argv, true);
    AdaptiveScreen screen(args);
    return screen.Run();
  } catch (const std::exception& error) {
    std::cerr << "run-052 worker error: " << error.what() << '\n';
    return 1;
  }
}
