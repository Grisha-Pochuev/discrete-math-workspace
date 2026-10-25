#include "run075_input.hpp"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

using Edge = std::pair<int, int>;
using Matching = std::array<Edge, 4>;

constexpr std::array<Edge, 4> kR{{{0, 2}, {1, 3}, {4, 6}, {5, 7}}};

std::array<Edge, 16> cross_edges() {
  std::array<Edge, 16> result{};
  int index = 0;
  for (int left = 0; left < 4; ++left) {
    for (int right = 4; right < 8; ++right) result[index++] = {left, right};
  }
  return result;
}

const std::array<Edge, 16> kCross = cross_edges();

bool is_r(const Edge &edge) {
  return std::find(kR.begin(), kR.end(), edge) != kR.end();
}

int r_index(const Edge &edge) {
  const auto it = std::find(kR.begin(), kR.end(), edge);
  if (it == kR.end()) throw std::runtime_error("edge is not in R");
  return static_cast<int>(it - kR.begin());
}

int cross_index(const Edge &edge) {
  const auto it = std::find(kCross.begin(), kCross.end(), edge);
  if (it == kCross.end()) throw std::runtime_error("edge is not cross");
  return static_cast<int>(it - kCross.begin());
}

std::vector<Matching> matching_catalogue() {
  std::vector<Edge> edges(kR.begin(), kR.end());
  edges.insert(edges.end(), kCross.begin(), kCross.end());
  std::sort(edges.begin(), edges.end());
  std::vector<Matching> output;
  const int size = static_cast<int>(edges.size());
  for (int a = 0; a < size; ++a) {
    for (int b = a + 1; b < size; ++b) {
      for (int c = b + 1; c < size; ++c) {
        for (int d = c + 1; d < size; ++d) {
          Matching candidate{{edges[a], edges[b], edges[c], edges[d]}};
          int mask = 0;
          bool valid = true;
          for (const auto &[u, v] : candidate) {
            const int endpoints = (1 << u) | (1 << v);
            if (mask & endpoints) valid = false;
            mask |= endpoints;
          }
          if (valid && mask == 255) output.push_back(candidate);
        }
      }
    }
  }
  std::sort(output.begin(), output.end());
  if (output.size() != 33) throw std::runtime_error("unexpected matching count");
  return output;
}

struct Formula {
  int variables = 0;
  std::vector<std::vector<int>> clauses;

  int fresh() { return ++variables; }

  void add(std::vector<int> clause) {
    if (clause.empty()) throw std::runtime_error("empty input clause");
    std::set<int> seen;
    for (const int literal : clause) {
      if (literal == 0 || std::abs(literal) > variables) {
        throw std::runtime_error("literal outside allocated range");
      }
      if (seen.count(literal) || seen.count(-literal)) {
        throw std::runtime_error("noncanonical input clause");
      }
      seen.insert(literal);
    }
    clauses.push_back(std::move(clause));
  }
};

using RSupport = std::array<std::array<std::array<bool, 3>, 3>, 4>;

RSupport r_support_for(int orbit_id) {
  if (orbit_id < 0 || orbit_id >= static_cast<int>(neutral075::kOrbits.size())) {
    throw std::runtime_error("orbit id outside immutable input");
  }
  RSupport support{};
  for (int edge = 0; edge < 4; ++edge) {
    for (int colour = 0; colour < 3; ++colour) support[edge][colour][colour] = true;
  }
  for (const auto &entry : neutral075::kOrbits[orbit_id].entries) {
    if (entry.edge >= 4 || entry.a >= 3 || entry.b >= 3 || entry.a == entry.b) {
      throw std::runtime_error("invalid immutable representative entry");
    }
    support[entry.edge][entry.a][entry.b] = true;
  }
  return support;
}

std::array<int, 8> decode_state(int state) {
  std::array<int, 8> colours{};
  for (int vertex = 0; vertex < 8; ++vertex) {
    colours[vertex] = state % 3;
    state /= 3;
  }
  return colours;
}

bool all_equal(const std::array<int, 8> &colours) {
  return std::all_of(colours.begin() + 1, colours.end(), [&](int q) { return q == colours[0]; });
}

bool automatic_r_star(int root, int colour, const RSupport &support) {
  Edge edge{};
  for (const auto &candidate : kR) {
    if (candidate.first == root || candidate.second == root) {
      edge = candidate;
      break;
    }
  }
  const int index = r_index(edge);
  int row_size = 0;
  bool diagonal = false;
  for (int a = 0; a < 3; ++a) {
    for (int b = 0; b < 3; ++b) {
      if (!support[index][a][b]) continue;
      const bool selected = edge.first == root ? a == colour : b == colour;
      if (selected) {
        ++row_size;
        diagonal = diagonal || (a == colour && b == colour);
      }
    }
  }
  return row_size == 1 && diagonal;
}

struct BuiltFormula {
  Formula formula;
  int x[16][3][3]{};
};

BuiltFormula build_formula(int orbit_id) {
  const auto support = r_support_for(orbit_id);
  const auto matchings = matching_catalogue();
  BuiltFormula built;
  Formula &formula = built.formula;

  for (int edge = 0; edge < 16; ++edge) {
    for (int a = 0; a < 3; ++a) {
      for (int b = 0; b < 3; ++b) built.x[edge][a][b] = formula.fresh();
    }
  }
  for (int edge = 0; edge < 16; ++edge) {
    std::vector<int> clause;
    for (int a = 0; a < 3; ++a) {
      for (int b = 0; b < 3; ++b) clause.push_back(built.x[edge][a][b]);
    }
    formula.add(std::move(clause));
  }

  const Matching pure{{kR[0], kR[1], kR[2], kR[3]}};
  for (int q = 0; q < 3; ++q) {
    for (const auto &matching : matchings) {
      if (matching == pure) continue;
      std::vector<int> clause;
      for (const auto &edge : matching) {
        if (!is_r(edge)) clause.push_back(-built.x[cross_index(edge)][q][q]);
      }
      formula.add(std::move(clause));
    }
  }

  for (int root = 0; root < 8; ++root) {
    for (int q = 0; q < 3; ++q) {
      std::vector<int> witnesses;
      for (int edge_index = 0; edge_index < 16; ++edge_index) {
        const auto &edge = kCross[edge_index];
        if (edge.first != root && edge.second != root) continue;
        const int h = formula.fresh();
        witnesses.push_back(h);
        std::vector<int> inside;
        std::vector<int> outside;
        if (root < 4) {
          for (int a = 0; a < 3; ++a) inside.push_back(built.x[edge_index][a][q]);
          for (int a = 0; a < 3; ++a) {
            for (int b = 0; b < 3; ++b) if (b != q) outside.push_back(built.x[edge_index][a][b]);
          }
        } else {
          for (int b = 0; b < 3; ++b) inside.push_back(built.x[edge_index][q][b]);
          for (int a = 0; a < 3; ++a) {
            for (int b = 0; b < 3; ++b) if (a != q) outside.push_back(built.x[edge_index][a][b]);
          }
        }
        std::vector<int> clause{-h};
        clause.insert(clause.end(), inside.begin(), inside.end());
        formula.add(std::move(clause));
        for (const int value : outside) formula.add({-h, -value});
        for (const int value : inside) {
          std::vector<int> reverse{-value};
          reverse.insert(reverse.end(), outside.begin(), outside.end());
          reverse.push_back(h);
          formula.add(std::move(reverse));
        }
      }
      if (witnesses.size() != 4) throw std::runtime_error("bad full-column incidence");
      formula.add(std::move(witnesses));
    }
  }

  for (int root = 0; root < 8; ++root) {
    for (int q = 0; q < 3; ++q) {
      if (automatic_r_star(root, q, support)) continue;
      std::vector<int> witnesses;
      for (int edge_index = 0; edge_index < 16; ++edge_index) {
        const auto &edge = kCross[edge_index];
        if (edge.first != root && edge.second != root) continue;
        const int s = formula.fresh();
        witnesses.push_back(s);
        const int same = built.x[edge_index][q][q];
        std::vector<int> other;
        if (root < 4) {
          for (int b = 0; b < 3; ++b) if (b != q) other.push_back(built.x[edge_index][q][b]);
        } else {
          for (int a = 0; a < 3; ++a) if (a != q) other.push_back(built.x[edge_index][a][q]);
        }
        formula.add({-s, same});
        for (const int value : other) formula.add({-s, -value});
        std::vector<int> reverse{-same};
        reverse.insert(reverse.end(), other.begin(), other.end());
        reverse.push_back(s);
        formula.add(std::move(reverse));
      }
      if (witnesses.size() != 4) throw std::runtime_error("bad star incidence");
      formula.add(std::move(witnesses));
    }
  }

  for (int state = 0; state < 6561; ++state) {
    const auto colours = decode_state(state);
    if (all_equal(colours)) continue;
    std::vector<int> terms;
    bool constant = false;
    for (const auto &matching : matchings) {
      bool possible = true;
      std::vector<int> required;
      for (const auto &edge : matching) {
        const int a = colours[edge.first];
        const int b = colours[edge.second];
        if (is_r(edge)) {
          if (!support[r_index(edge)][a][b]) {
            possible = false;
            break;
          }
        } else {
          required.push_back(built.x[cross_index(edge)][a][b]);
        }
      }
      if (!possible) continue;
      if (required.empty()) {
        if (constant) throw std::runtime_error("two constant mixed terms");
        constant = true;
        continue;
      }
      const int term = formula.fresh();
      for (const int value : required) formula.add({-term, value});
      std::vector<int> reverse{term};
      for (const int value : required) reverse.push_back(-value);
      formula.add(std::move(reverse));
      terms.push_back(term);
    }
    if (constant) {
      if (terms.empty()) throw std::runtime_error("unconditional mixed singleton");
      formula.add(std::move(terms));
    } else {
      for (std::size_t index = 0; index < terms.size(); ++index) {
        std::vector<int> clause{-terms[index]};
        for (std::size_t other = 0; other < terms.size(); ++other) {
          if (other != index) clause.push_back(terms[other]);
        }
        formula.add(std::move(clause));
      }
    }
  }
  return built;
}

void write_formula(const BuiltFormula &built, int orbit_id, const std::string &cnf_path,
                   const std::string &metadata_path) {
  std::ofstream cnf(cnf_path, std::ios::binary);
  if (!cnf) throw std::runtime_error("cannot open CNF output");
  cnf << "p cnf " << built.formula.variables << ' ' << built.formula.clauses.size() << '\n';
  for (const auto &clause : built.formula.clauses) {
    for (const int literal : clause) cnf << literal << ' ';
    cnf << "0\n";
  }
  cnf.close();
  if (!cnf) throw std::runtime_error("failed to finish CNF output");

  const auto &orbit = neutral075::kOrbits[orbit_id];
  std::ofstream metadata(metadata_path, std::ios::binary);
  if (!metadata) throw std::runtime_error("cannot open metadata output");
  metadata << "{\n"
           << "  \"schema\": \"neutral-cnf-metadata-v1\",\n"
           << "  \"orbit_id\": " << orbit_id << ",\n"
           << "  \"orbit_size\": " << orbit.size << ",\n"
           << "  \"catalogue_sha256\": \"" << neutral075::kCatalogueSha256 << "\",\n"
           << "  \"variable_count\": " << built.formula.variables << ",\n"
           << "  \"clause_count\": " << built.formula.clauses.size() << "\n"
           << "}\n";
}

std::vector<bool> parse_model(const std::string &path) {
  std::ifstream input(path);
  if (!input) throw std::runtime_error("cannot open SAT model");
  std::vector<bool> assignment(145, false);
  std::string line;
  bool saw_sat = false;
  while (std::getline(input, line)) {
    if (line.rfind("s SATISFIABLE", 0) == 0) saw_sat = true;
    if (line.empty() || line[0] != 'v') continue;
    std::istringstream values(line.substr(1));
    int literal = 0;
    while (values >> literal) {
      if (literal > 0 && literal <= 144) assignment[literal] = true;
    }
  }
  if (!saw_sat) throw std::runtime_error("model file is not SATISFIABLE");
  return assignment;
}

std::array<int, 16> masks_from_assignment(const std::vector<bool> &assignment) {
  std::array<int, 16> masks{};
  int variable = 1;
  for (int edge = 0; edge < 16; ++edge) {
    for (int a = 0; a < 3; ++a) {
      for (int b = 0; b < 3; ++b, ++variable) {
        if (assignment[variable]) masks[edge] |= 1 << (3 * a + b);
      }
    }
    if (masks[edge] == 0) throw std::runtime_error("positive model has an empty edge");
  }
  return masks;
}

bool cross_supported(const std::array<int, 16> &masks, const Edge &edge, int a, int b) {
  return masks[cross_index(edge)] & (1 << (3 * a + b));
}

void validate_positive(int orbit_id, const std::array<int, 16> &masks) {
  const auto support = r_support_for(orbit_id);
  const auto matchings = matching_catalogue();
  for (int q = 0; q < 3; ++q) {
    int count = 0;
    for (const auto &matching : matchings) {
      bool valid = true;
      for (const auto &edge : matching) {
        valid &= is_r(edge) ? support[r_index(edge)][q][q]
                            : cross_supported(masks, edge, q, q);
      }
      count += valid;
    }
    if (count != 1) throw std::runtime_error("positive model has nonunique pure matching");
  }
  for (int root = 0; root < 8; ++root) {
    for (int q = 0; q < 3; ++q) {
      bool star = false;
      for (const auto &edge : kR) {
        if (edge.first != root && edge.second != root) continue;
        int row_size = 0;
        bool diagonal = false;
        for (int a = 0; a < 3; ++a) for (int b = 0; b < 3; ++b) {
          if (!support[r_index(edge)][a][b]) continue;
          const bool selected = edge.first == root ? a == q : b == q;
          if (selected) { ++row_size; diagonal |= (a == q && b == q); }
        }
        star |= row_size == 1 && diagonal;
      }
      bool full = false;
      for (int edge_index = 0; edge_index < 16; ++edge_index) {
        const auto &edge = kCross[edge_index];
        if (edge.first != root && edge.second != root) continue;
        int selected = 0;
        int total = 0;
        for (int a = 0; a < 3; ++a) for (int b = 0; b < 3; ++b) {
          if (!(masks[edge_index] & (1 << (3 * a + b)))) continue;
          ++total;
          if ((root < 4 ? b : a) == q) ++selected;
          if ((root < 4 ? a : b) == q && a == b) {
            int row_size = 0;
            for (int aa = 0; aa < 3; ++aa) for (int bb = 0; bb < 3; ++bb) {
              if (!(masks[edge_index] & (1 << (3 * aa + bb)))) continue;
              if ((root < 4 ? aa : bb) == q) ++row_size;
            }
            star |= row_size == 1;
          }
        }
        full |= total > 0 && selected == total;
      }
      if (!star || !full) throw std::runtime_error("positive model misses an anchor");
    }
  }
  for (int state = 0; state < 6561; ++state) {
    const auto colours = decode_state(state);
    if (all_equal(colours)) continue;
    int count = 0;
    for (const auto &matching : matchings) {
      bool valid = true;
      for (const auto &edge : matching) {
        const int a = colours[edge.first];
        const int b = colours[edge.second];
        valid &= is_r(edge) ? support[r_index(edge)][a][b]
                            : cross_supported(masks, edge, a, b);
      }
      count += valid;
    }
    if (count == 1) throw std::runtime_error("positive model has a mixed singleton");
  }
}

void write_positive(int orbit_id, const std::array<int, 16> &masks, const std::string &path) {
  std::ofstream output(path, std::ios::binary);
  if (!output) throw std::runtime_error("cannot open positive output");
  output << "{\n  \"schema\": \"neutral-positive-support-v1\",\n"
         << "  \"orbit_id\": " << orbit_id << ",\n"
         << "  \"catalogue_sha256\": \"" << neutral075::kCatalogueSha256 << "\",\n"
         << "  \"cross_edge_masks\": [\n";
  for (int index = 0; index < 16; ++index) {
    output << "    {\"edge\": [" << kCross[index].first << ", " << kCross[index].second
           << "], \"mask\": " << masks[index] << "}" << (index == 15 ? "\n" : ",\n");
  }
  output << "  ],\n  \"direct_replay_accepted\": true\n}\n";
}

int parse_orbit(const std::string &value) {
  std::size_t used = 0;
  const int orbit = std::stoi(value, &used);
  if (used != value.size()) throw std::runtime_error("bad orbit id");
  return orbit;
}

}  // namespace

int main(int argc, char **argv) {
  try {
    if (argc == 6 && std::string(argv[1]) == "emit" && std::string(argv[2]) == "--orbit") {
      const int orbit_id = parse_orbit(argv[3]);
      const auto built = build_formula(orbit_id);
      write_formula(built, orbit_id, argv[4], argv[5]);
      return 0;
    }
    if (argc == 6 && std::string(argv[1]) == "replay" && std::string(argv[2]) == "--orbit") {
      const int orbit_id = parse_orbit(argv[3]);
      const auto masks = masks_from_assignment(parse_model(argv[4]));
      validate_positive(orbit_id, masks);
      write_positive(orbit_id, masks, argv[5]);
      return 0;
    }
    std::cerr << "usage: run075_worker emit|replay --orbit N INPUT OUTPUT\n";
    return 2;
  } catch (const std::exception &error) {
    std::cerr << "run075_worker: " << error.what() << '\n';
    return 2;
  }
}
