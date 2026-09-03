// Native symmetry-quotient frontier enumerator with exact integer-lattice filtering.

#include <algorithm>
#include <array>
#include <atomic>
#include <bit>
#include <chrono>
#include <compare>
#include <csignal>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <numeric>
#include <optional>
#include <set>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include <flint/flint.h>
#include <flint/fmpz.h>
#include <flint/fmpz_mat.h>

namespace fs = std::filesystem;

namespace {

constexpr int kRows = 5;
constexpr int kTerminals = 8;
constexpr int kColours = 3;
constexpr int kBits = 120;
constexpr int kWordCount = 81;
constexpr int kMatchingCount = 24;
constexpr int kGroupSize = 72;

std::atomic<bool> g_signal_requested{false};

void HandleSignal(int) { g_signal_requested.store(true); }

struct Mask {
  std::uint64_t lo = 0;
  std::uint64_t hi = 0;

  auto operator<=>(const Mask&) const = default;
};

struct MaskHash {
  std::size_t operator()(const Mask& value) const noexcept {
    std::uint64_t x = value.lo ^ (value.hi + 0x9e3779b97f4a7c15ULL +
                                  (value.lo << 6) + (value.lo >> 2));
    x ^= x >> 30;
    x *= 0xbf58476d1ce4e5b9ULL;
    x ^= x >> 27;
    x *= 0x94d049bb133111ebULL;
    x ^= x >> 31;
    return static_cast<std::size_t>(x);
  }
};

Mask Bit(int bit) {
  if (bit < 0 || bit >= kBits) throw std::runtime_error("bit out of range");
  if (bit < 64) return Mask{std::uint64_t{1} << bit, 0};
  return Mask{0, std::uint64_t{1} << (bit - 64)};
}

Mask operator|(Mask left, Mask right) {
  return Mask{left.lo | right.lo, left.hi | right.hi};
}

Mask operator&(Mask left, Mask right) {
  return Mask{left.lo & right.lo, left.hi & right.hi};
}

Mask operator~(Mask value) { return Mask{~value.lo, ~value.hi}; }

Mask& operator|=(Mask& left, Mask right) {
  left.lo |= right.lo;
  left.hi |= right.hi;
  return left;
}

bool Empty(Mask value) { return value.lo == 0 && value.hi == 0; }

bool Subset(Mask part, Mask whole) { return Empty(part & ~whole); }

int Popcount(Mask value) {
  return std::popcount(value.lo) + std::popcount(value.hi);
}

bool HasBit(Mask value, int bit) {
  if (bit < 64) return ((value.lo >> bit) & 1U) != 0;
  return ((value.hi >> (bit - 64)) & 1U) != 0;
}

using CircuitKey = std::pair<Mask, Mask>;

CircuitKey UnorientedCircuit(Mask first, Mask second) {
  const Mask forward{first.lo & ~second.lo, first.hi & ~second.hi};
  const Mask backward{second.lo & ~first.lo, second.hi & ~first.hi};
  return std::min(CircuitKey{forward, backward},
                  CircuitKey{backward, forward});
}

std::vector<int> SetBits(Mask value) {
  std::vector<int> result;
  while (value.lo) {
    const int bit = std::countr_zero(value.lo);
    result.push_back(bit);
    value.lo &= value.lo - 1;
  }
  while (value.hi) {
    const int bit = std::countr_zero(value.hi);
    result.push_back(64 + bit);
    value.hi &= value.hi - 1;
  }
  return result;
}

std::string Decimal(Mask value) {
  unsigned __int128 number = static_cast<unsigned __int128>(value.hi) << 64;
  number |= value.lo;
  if (number == 0) return "0";
  std::string text;
  while (number) {
    text.push_back(static_cast<char>('0' + number % 10));
    number /= 10;
  }
  std::reverse(text.begin(), text.end());
  return text;
}

int EntryId(int row, int terminal, int colour) {
  return (row * kTerminals + terminal) * kColours + colour;
}

using Permutation = std::array<int, 4>;
using Word = std::array<int, 4>;
using Mapping = std::array<int, kBits>;

std::array<std::vector<Permutation>, kRows> BuildPermutations() {
  std::array<std::vector<Permutation>, kRows> result;
  for (int root = 0; root < kRows; ++root) {
    Permutation values{};
    int cursor = 0;
    for (int vertex = 0; vertex < kRows; ++vertex) {
      if (vertex != root) values[cursor++] = vertex;
    }
    do {
      result[root].push_back(values);
    } while (std::next_permutation(values.begin(), values.end()));
    if (result[root].size() != kMatchingCount) {
      throw std::runtime_error("permutation count mismatch");
    }
  }
  return result;
}

std::array<Word, kWordCount> BuildWords() {
  std::array<Word, kWordCount> words{};
  for (int index = 0; index < kWordCount; ++index) {
    int value = index;
    for (int position = 3; position >= 0; --position) {
      words[index][position] = value % kColours;
      value /= kColours;
    }
  }
  return words;
}

struct Model {
  std::array<std::vector<Permutation>, kRows> permutations = BuildPermutations();
  std::array<Word, kWordCount> words = BuildWords();
  std::array<std::array<std::array<Mask, kMatchingCount>, kWordCount>, kRows>
      match_masks{};
  std::vector<int> valid_bits;

  Model() {
    for (int root = 0; root < kRows; ++root) {
      const std::array<int, 4> terminals{root, 5, 6, 7};
      for (int word_index = 0; word_index < kWordCount; ++word_index) {
        for (int permutation_index = 0; permutation_index < kMatchingCount;
             ++permutation_index) {
          Mask matching;
          for (int position = 0; position < 4; ++position) {
            matching |= Bit(EntryId(
                permutations[root][permutation_index][position],
                terminals[position], words[word_index][position]));
          }
          match_masks[root][word_index][permutation_index] = matching;
        }
      }
    }
    for (int row = 0; row < kRows; ++row) {
      for (int terminal = 0; terminal < kTerminals; ++terminal) {
        if (terminal == row) continue;
        for (int colour = 0; colour < kColours; ++colour) {
          valid_bits.push_back(EntryId(row, terminal, colour));
        }
      }
    }
    if (valid_bits.size() != 105) throw std::runtime_error("valid-bit mismatch");
  }
};

enum class Pattern { k111, k21 };

std::string PatternName(Pattern pattern) {
  return pattern == Pattern::k111 ? "111" : "21";
}

Pattern ParsePattern(const std::string& text) {
  if (text == "111" || text == "1+1+1") return Pattern::k111;
  if (text == "21" || text == "2+1") return Pattern::k21;
  throw std::runtime_error("unknown pattern: " + text);
}

bool ExpectedWord(Pattern pattern, int root, const Word& word) {
  const bool uniform = std::all_of(
      word.begin() + 1, word.end(), [&](int value) { return value == word[0]; });
  if (!uniform) return false;
  if (pattern == Pattern::k111) return root < 3 && word[0] == root;
  return (root == 0 && (word[0] == 0 || word[0] == 1)) ||
         (root == 1 && word[0] == 2);
}

Mask SelectorMask(const Model& model, int root, int colour,
                  const Permutation& permutation) {
  const std::array<int, 4> terminals{root, 5, 6, 7};
  Mask result;
  for (int position = 0; position < 4; ++position) {
    result |= Bit(EntryId(permutation[position], terminals[position], colour));
  }
  return result;
}

std::vector<std::array<int, 3>> ColourPermutations() {
  std::array<int, 3> values{0, 1, 2};
  std::vector<std::array<int, 3>> result;
  do {
    result.push_back(values);
  } while (std::next_permutation(values.begin(), values.end()));
  return result;
}

std::vector<Mapping> BuildGroup(Pattern pattern) {
  std::vector<Mapping> result;
  const auto colour_permutations = ColourPermutations();
  if (pattern == Pattern::k111) {
    for (const auto& owner_colour : colour_permutations) {
      for (const std::array<int, 2> unowned :
           {std::array<int, 2>{3, 4}, std::array<int, 2>{4, 3}}) {
        for (const auto& outside : colour_permutations) {
          std::array<int, kTerminals> terminal{};
          terminal[0] = owner_colour[0];
          terminal[1] = owner_colour[1];
          terminal[2] = owner_colour[2];
          terminal[3] = unowned[0];
          terminal[4] = unowned[1];
          terminal[5] = 5 + outside[0];
          terminal[6] = 5 + outside[1];
          terminal[7] = 5 + outside[2];
          std::array<int, kRows> blocker{
              owner_colour[0], owner_colour[1], owner_colour[2],
              unowned[0], unowned[1]};
          Mapping mapping;
          mapping.fill(-1);
          for (int row = 0; row < kRows; ++row) {
            for (int endpoint = 0; endpoint < kTerminals; ++endpoint) {
              if (endpoint == row) continue;
              for (int colour = 0; colour < kColours; ++colour) {
                mapping[EntryId(row, endpoint, colour)] = EntryId(
                    blocker[row], terminal[endpoint], owner_colour[colour]);
              }
            }
          }
          result.push_back(mapping);
        }
      }
    }
  } else {
    const std::array<std::array<int, 3>, 2> swaps{
        std::array<int, 3>{0, 1, 2}, std::array<int, 3>{1, 0, 2}};
    std::array<int, 3> unowned{2, 3, 4};
    for (const auto& colour_map : swaps) {
      std::sort(unowned.begin(), unowned.end());
      do {
        for (const auto& outside : colour_permutations) {
          std::array<int, kRows> blocker{0, 1, unowned[0], unowned[1],
                                         unowned[2]};
          std::array<int, kTerminals> terminal{};
          for (int index = 0; index < kRows; ++index) terminal[index] = blocker[index];
          terminal[5] = 5 + outside[0];
          terminal[6] = 5 + outside[1];
          terminal[7] = 5 + outside[2];
          Mapping mapping;
          mapping.fill(-1);
          for (int row = 0; row < kRows; ++row) {
            for (int endpoint = 0; endpoint < kTerminals; ++endpoint) {
              if (endpoint == row) continue;
              for (int colour = 0; colour < kColours; ++colour) {
                mapping[EntryId(row, endpoint, colour)] = EntryId(
                    blocker[row], terminal[endpoint], colour_map[colour]);
              }
            }
          }
          result.push_back(mapping);
        }
      } while (std::next_permutation(unowned.begin(), unowned.end()));
    }
  }
  if (result.size() != kGroupSize) throw std::runtime_error("group-size mismatch");
  return result;
}

Mask Transform(Mask source, const Mapping& mapping) {
  Mask result;
  for (int bit : SetBits(source)) {
    if (mapping[bit] < 0) throw std::runtime_error("invalid symmetry image");
    result |= Bit(mapping[bit]);
  }
  return result;
}

Mask Canonical(Mask source, const std::vector<Mapping>& group) {
  Mask result = Transform(source, group.front());
  for (std::size_t index = 1; index < group.size(); ++index) {
    result = std::min(result, Transform(source, group[index]));
  }
  return result;
}

std::vector<Mask> InitialBases(const Model& model, Pattern pattern,
                               const std::vector<Mapping>& group) {
  std::set<Mask> bases;
  if (pattern == Pattern::k111) {
    for (const auto& first : model.permutations[0]) {
      for (const auto& second : model.permutations[1]) {
        for (const auto& third : model.permutations[2]) {
          const Mask support = SelectorMask(model, 0, 0, first) |
                               SelectorMask(model, 1, 1, second) |
                               SelectorMask(model, 2, 2, third);
          bases.insert(Canonical(support, group));
        }
      }
    }
  } else {
    for (std::size_t first = 0; first < model.permutations[0].size(); ++first) {
      for (std::size_t second = 0; second < model.permutations[0].size(); ++second) {
        if (first == second) continue;
        for (const auto& third : model.permutations[1]) {
          const Mask support = SelectorMask(model, 0, 0, model.permutations[0][first]) |
                               SelectorMask(model, 0, 1, model.permutations[0][second]) |
                               SelectorMask(model, 1, 2, third);
          bases.insert(Canonical(support, group));
        }
      }
    }
  }
  const std::size_t expected = pattern == Pattern::k111 ? 209 : 201;
  if (bases.size() != expected) throw std::runtime_error("base-orbit regression mismatch");
  return std::vector<Mask>(bases.begin(), bases.end());
}

class RowLattice {
 public:
  explicit RowLattice(const std::vector<std::vector<long>>& generators)
      : columns_(generators.front().size()) {
    fmpz_mat_init(hnf_, generators.size(), columns_);
    fmpz_mat_t source;
    fmpz_mat_init(source, generators.size(), columns_);
    for (slong row = 0; row < static_cast<slong>(generators.size()); ++row) {
      if (generators[row].size() != static_cast<std::size_t>(columns_)) {
        throw std::runtime_error("lattice dimension mismatch");
      }
      for (slong column = 0; column < columns_; ++column) {
        fmpz_set_si(fmpz_mat_entry(source, row, column), generators[row][column]);
      }
    }
    fmpz_mat_hnf(hnf_, source);
    fmpz_mat_clear(source);
    for (slong row = 0; row < fmpz_mat_nrows(hnf_); ++row) {
      if (!ZeroRow(hnf_, row)) nonzero_rows_.push_back(row);
    }
  }

  RowLattice(const RowLattice&) = delete;
  RowLattice& operator=(const RowLattice&) = delete;

  ~RowLattice() { fmpz_mat_clear(hnf_); }

  std::size_t rank() const { return nonzero_rows_.size(); }

  bool Contains(const std::vector<long>& target) const {
    if (target.size() != static_cast<std::size_t>(columns_)) {
      throw std::runtime_error("target dimension mismatch");
    }
    fmpz_mat_t augmented;
    fmpz_mat_t reduced;
    const slong rows = static_cast<slong>(nonzero_rows_.size()) + 1;
    fmpz_mat_init(augmented, rows, columns_);
    fmpz_mat_init(reduced, rows, columns_);
    for (slong index = 0; index < static_cast<slong>(nonzero_rows_.size()); ++index) {
      for (slong column = 0; column < columns_; ++column) {
        fmpz_set(fmpz_mat_entry(augmented, index, column),
                 fmpz_mat_entry(hnf_, nonzero_rows_[index], column));
      }
    }
    for (slong column = 0; column < columns_; ++column) {
      fmpz_set_si(fmpz_mat_entry(augmented, rows - 1, column), target[column]);
    }
    fmpz_mat_hnf(reduced, augmented);
    std::vector<slong> reduced_nonzero;
    for (slong row = 0; row < rows; ++row) {
      if (!ZeroRow(reduced, row)) reduced_nonzero.push_back(row);
    }
    bool equal = reduced_nonzero.size() == nonzero_rows_.size();
    if (equal) {
      for (std::size_t row = 0; row < nonzero_rows_.size() && equal; ++row) {
        for (slong column = 0; column < columns_; ++column) {
          if (!fmpz_equal(fmpz_mat_entry(reduced, reduced_nonzero[row], column),
                          fmpz_mat_entry(hnf_, nonzero_rows_[row], column))) {
            equal = false;
            break;
          }
        }
      }
    }
    fmpz_mat_clear(reduced);
    fmpz_mat_clear(augmented);
    return equal;
  }

 private:
  static bool ZeroRow(const fmpz_mat_t matrix, slong row) {
    for (slong column = 0; column < fmpz_mat_ncols(matrix); ++column) {
      if (!fmpz_is_zero(fmpz_mat_entry(matrix, row, column))) return false;
    }
    return true;
  }

  slong columns_;
  fmpz_mat_t hnf_;
  std::vector<slong> nonzero_rows_;
};

std::vector<long> ExponentDifference(Mask first, Mask second,
                                     const std::vector<int>& active,
                                     long sign) {
  std::vector<long> result;
  result.reserve(active.size() + 1);
  for (int bit : active) {
    result.push_back(static_cast<long>(HasBit(first, bit)) -
                     static_cast<long>(HasBit(second, bit)));
  }
  result.push_back(sign);
  return result;
}

struct LongVectorHash {
  std::size_t operator()(const std::vector<long>& values) const noexcept {
    std::size_t result = 1469598103934665603ULL;
    for (long value : values) {
      result ^= static_cast<std::size_t>(value + 7);
      result *= 1099511628211ULL;
    }
    return result;
  }
};

struct SignedPair {
  int first = -1;
  int first_sign = 0;
  int second = -1;
  int second_sign = 0;
  std::vector<long> sum;
};

bool UnitParityCoefficient(long mixed_sign_sum) {
  const long numerator = 1 - mixed_sign_sum;
  return numerator % 2 == 0 && std::abs(numerator / 2) <= 1;
}

std::vector<long> CoordinatePart(const std::vector<long>& augmented) {
  if (augmented.empty()) throw std::runtime_error("empty augmented vector");
  return std::vector<long>(augmented.begin(), augmented.end() - 1);
}

std::vector<long> SubtractScaled(const std::vector<long>& target,
                                 const std::vector<long>& first,
                                 long first_scale,
                                 const std::vector<long>* second = nullptr) {
  if (target.size() != first.size() ||
      (second != nullptr && second->size() != target.size())) {
    throw std::runtime_error("signed-path dimension mismatch");
  }
  std::vector<long> result(target.size());
  for (std::size_t index = 0; index < target.size(); ++index) {
    result[index] = target[index] - first_scale * first[index] -
                    (second == nullptr ? 0 : (*second)[index]);
  }
  return result;
}

int UnitSignedPathLength(const std::vector<std::vector<long>>& augmented_rows,
                         int row_count,
                         const std::vector<long>& augmented_target) {
  if (row_count < 0 || row_count > static_cast<int>(augmented_rows.size()) ||
      augmented_target.empty() || augmented_target.back() != 1) {
    throw std::runtime_error("invalid signed-path contract");
  }
  const std::vector<long> target = CoordinatePart(augmented_target);
  std::vector<std::vector<long>> rows;
  rows.reserve(row_count);
  for (int index = 0; index < row_count; ++index) {
    rows.push_back(CoordinatePart(augmented_rows[index]));
  }
  for (int index = 0; index < row_count; ++index) {
    for (long sign : {-1L, 1L}) {
      bool equal = true;
      for (std::size_t coordinate = 0; coordinate < target.size(); ++coordinate) {
        if (sign * rows[index][coordinate] != target[coordinate]) {
          equal = false;
          break;
        }
      }
      if (equal) return 1;
    }
  }

  std::vector<SignedPair> pairs;
  std::unordered_map<std::vector<long>, std::vector<std::size_t>, LongVectorHash>
      pair_lookup;
  for (int first = 0; first < row_count; ++first) {
    for (int second = first + 1; second < row_count; ++second) {
      for (long first_sign : {-1L, 1L}) {
        for (long second_sign : {-1L, 1L}) {
          std::vector<long> sum(target.size());
          for (std::size_t coordinate = 0; coordinate < target.size(); ++coordinate) {
            sum[coordinate] = first_sign * rows[first][coordinate] +
                              second_sign * rows[second][coordinate];
          }
          const std::size_t pair_index = pairs.size();
          pairs.push_back(SignedPair{first, static_cast<int>(first_sign), second,
                                     static_cast<int>(second_sign), sum});
          pair_lookup[sum].push_back(pair_index);
        }
      }
    }
  }

  for (int single = 0; single < row_count; ++single) {
    for (long single_sign : {-1L, 1L}) {
      const std::vector<long> needed =
          SubtractScaled(target, rows[single], single_sign);
      const auto found = pair_lookup.find(needed);
      if (found == pair_lookup.end()) continue;
      for (std::size_t pair_index : found->second) {
        const SignedPair& pair = pairs[pair_index];
        if (pair.first != single && pair.second != single &&
            UnitParityCoefficient(single_sign + pair.first_sign +
                                  pair.second_sign)) {
          return 3;
        }
      }
    }
  }

  for (int single = 0; single < row_count; ++single) {
    for (long single_sign : {-1L, 1L}) {
      for (const SignedPair& first_pair : pairs) {
        if (first_pair.first == single || first_pair.second == single) continue;
        const std::vector<long> needed =
            SubtractScaled(target, rows[single], single_sign, &first_pair.sum);
        const auto found = pair_lookup.find(needed);
        if (found == pair_lookup.end()) continue;
        for (std::size_t pair_index : found->second) {
          const SignedPair& second_pair = pairs[pair_index];
          if (second_pair.first == single || second_pair.second == single ||
              second_pair.first == first_pair.first ||
              second_pair.first == first_pair.second ||
              second_pair.second == first_pair.first ||
              second_pair.second == first_pair.second) {
            continue;
          }
          if (UnitParityCoefficient(
                  single_sign + first_pair.first_sign + first_pair.second_sign +
                  second_pair.first_sign + second_pair.second_sign)) {
            return 5;
          }
        }
      }
    }
  }
  return 0;
}

void RunSignedPathContractTests() {
  const Mask first = Bit(0) | Bit(1) | Bit(2) | Bit(3);
  const Mask second = Bit(0) | Bit(1) | Bit(4) | Bit(5);
  const Mask different = Bit(0) | Bit(1) | Bit(4) | Bit(6);
  if (UnorientedCircuit(first, second) != UnorientedCircuit(second, first) ||
      UnorientedCircuit(first, second) == UnorientedCircuit(first, different)) {
    throw std::runtime_error("global direct-collision key regression");
  }
  const std::vector<std::vector<long>> rows = {
      {1, 0, 0, 0, 0, 1}, {0, 1, 0, 0, 0, 1},
      {0, 0, 1, 0, 0, 1}, {0, 0, 0, 1, 0, 1},
      {0, 0, 0, 0, 1, 1},
  };
  if (UnitSignedPathLength(rows, 5, {1, 0, 0, 0, 0, 1}) != 1 ||
      UnitSignedPathLength(rows, 5, {1, 1, 1, 0, 0, 1}) != 3 ||
      UnitSignedPathLength(rows, 5, {1, 1, 1, 1, -1, 1}) != 5 ||
      UnitSignedPathLength(rows, 5, {1, 1, 1, 1, 1, 1}) != 0 ||
      UnitSignedPathLength(rows, 1, {2, 0, 0, 0, 0, 1}) != 0) {
    throw std::runtime_error("signed-path contract regression");
  }
}

std::vector<int> QuotientCoefficients(const std::vector<Mask>& terms,
                                      const std::vector<int>& active,
                                      const RowLattice& lattice) {
  struct Group {
    Mask representative;
    int coefficient;
  };
  std::vector<Group> groups;
  for (Mask term : terms) {
    bool placed = false;
    for (Group& group : groups) {
      if (lattice.Contains(ExponentDifference(term, group.representative, active, 0))) {
        ++group.coefficient;
        placed = true;
        break;
      }
      if (lattice.Contains(ExponentDifference(term, group.representative, active, 1))) {
        --group.coefficient;
        placed = true;
        break;
      }
    }
    if (!placed) groups.push_back(Group{term, 1});
  }
  std::vector<int> result;
  for (const Group& group : groups) {
    if (group.coefficient != 0) result.push_back(group.coefficient);
  }
  return result;
}

struct Classification {
  std::string outcome;
  std::map<int, int> term_histogram;
  int binomial_rows = 0;
  std::size_t lattice_rank = 0;
  std::string portable_kind = "none";
  int portable_path_length = 0;
};

struct ExceptionalSupport {
  Mask support;
  std::string outcome;
  int binomial_rows = 0;
  std::size_t lattice_rank = 0;
};

Classification Classify(const Model& model, Pattern pattern, Mask support) {
  const std::vector<int> active = SetBits(support);
  std::vector<std::vector<long>> generators;
  std::vector<std::vector<Mask>> targets;
  std::vector<std::vector<Mask>> longer;
  std::set<CircuitKey> mixed_circuits;
  std::map<int, int> histogram;
  for (int root = 0; root < kRows; ++root) {
    for (int word_index = 0; word_index < kWordCount; ++word_index) {
      std::vector<Mask> terms;
      for (Mask matching : model.match_masks[root][word_index]) {
        if (Subset(matching, support)) terms.push_back(matching);
      }
      if (ExpectedWord(pattern, root, model.words[word_index])) {
        targets.push_back(std::move(terms));
      } else if (!terms.empty()) {
        ++histogram[static_cast<int>(terms.size())];
        if (terms.size() == 2) {
          mixed_circuits.insert(UnorientedCircuit(terms[0], terms[1]));
          generators.push_back(ExponentDifference(terms[0], terms[1], active, 1));
        } else {
          longer.push_back(std::move(terms));
        }
      }
    }
  }
  const int binomial_rows = generators.size();
  for (const auto& terms : targets) {
    if (terms.size() == 2 &&
        mixed_circuits.contains(UnorientedCircuit(terms[0], terms[1]))) {
      return Classification{"required_amplitude_zero", histogram, binomial_rows,
                            0, "global_direct_collision", 1};
    }
  }
  std::vector<long> parity(active.size() + 1, 0);
  parity.back() = 2;
  generators.push_back(parity);
  RowLattice lattice(generators);
  std::vector<long> sign_target(active.size() + 1, 0);
  sign_target.back() = 1;
  if (lattice.Contains(sign_target)) {
    const int path_length =
        UnitSignedPathLength(generators, binomial_rows, sign_target);
    return Classification{"sign_inconsistency", histogram, binomial_rows,
                          lattice.rank(),
                          path_length ? "sign_cycle_" + std::to_string(path_length)
                                      : "none",
                          path_length};
  }
  bool required_amplitude_zero = false;
  for (const auto& terms : targets) {
    if (!QuotientCoefficients(terms, active, lattice).empty()) continue;
    required_amplitude_zero = true;
    if (terms.empty()) {
      return Classification{"required_amplitude_zero", histogram, binomial_rows,
                            lattice.rank(), "missing_required_amplitude", 0};
    }
    if (terms.size() != 2) continue;
    const int path_length = UnitSignedPathLength(
        generators, binomial_rows,
        ExponentDifference(terms[1], terms[0], active, 1));
    if (path_length) {
      return Classification{"required_amplitude_zero", histogram, binomial_rows,
                            lattice.rank(),
                            "required_path_" + std::to_string(path_length),
                            path_length};
    }
  }
  if (required_amplitude_zero) {
    return Classification{"required_amplitude_zero", histogram, binomial_rows,
                          lattice.rank(), "none", 0};
  }
  for (const auto& terms : longer) {
    if (QuotientCoefficients(terms, active, lattice).size() == 1) {
      return Classification{"quotient_unit", histogram, binomial_rows,
                            lattice.rank(), "none", 0};
    }
  }
  return Classification{"open", histogram, binomial_rows, lattice.rank(),
                        "none", 0};
}

struct Arguments {
  std::string run_id;
  std::string spec_sha256;
  Pattern pattern = Pattern::k111;
  int target_size = 19;
  int shard_id = 0;
  int shard_count = 1;
  double seconds = 900.0;
  std::uint64_t max_states = 0;
  double checkpoint_seconds = 120.0;
  fs::path output;
};

Arguments ParseArguments(int argc, char** argv) {
  Arguments args;
  for (int index = 1; index < argc; ++index) {
    const std::string key = argv[index];
    if (index + 1 >= argc) throw std::runtime_error("missing value for " + key);
    const std::string value = argv[++index];
    if (key == "--run-id") args.run_id = value;
    else if (key == "--spec-sha256") args.spec_sha256 = value;
    else if (key == "--pattern") args.pattern = ParsePattern(value);
    else if (key == "--target-size") args.target_size = std::stoi(value);
    else if (key == "--shard-id") args.shard_id = std::stoi(value);
    else if (key == "--shard-count") args.shard_count = std::stoi(value);
    else if (key == "--seconds") args.seconds = std::stod(value);
    else if (key == "--max-states") args.max_states = std::stoull(value);
    else if (key == "--checkpoint-seconds") args.checkpoint_seconds = std::stod(value);
    else if (key == "--output") args.output = value;
    else throw std::runtime_error("unknown argument: " + key);
  }
  if (args.run_id.empty() || args.spec_sha256.empty() || args.output.empty()) {
    throw std::runtime_error("run-id, spec-sha256, and output are required");
  }
  if (args.target_size < 12 || args.target_size > 24) {
    throw std::runtime_error("unsupported target size");
  }
  if (args.shard_count <= 0 || args.shard_id < 0 || args.shard_id >= args.shard_count) {
    throw std::runtime_error("invalid shard contract");
  }
  return args;
}

class Enumerator {
 public:
  explicit Enumerator(Arguments args)
      : args_(std::move(args)),
        group_(BuildGroup(args_.pattern)),
        bases_(InitialBases(model_, args_.pattern, group_)),
        started_(std::chrono::steady_clock::now()),
        last_checkpoint_(started_) {
    for (int bit = 0; bit < kBits; ++bit) {
      for (int group_index = 0; group_index < kGroupSize; ++group_index) {
        if (group_[group_index][bit] >= 0) {
          bit_images_[group_index][bit] = Bit(group_[group_index][bit]);
        }
      }
    }
    for (std::size_t index = 0; index < bases_.size(); ++index) {
      if (static_cast<int>(index % args_.shard_count) == args_.shard_id) {
        assigned_bases_.push_back(bases_[index]);
      }
    }
  }

  void Run() {
    for (Mask support : assigned_bases_) {
      if (StopRequested()) break;
      Recurse(support, args_.target_size - Popcount(support));
      if (stopped_reason_.empty()) ++processed_bases_;
    }
    if (stopped_reason_.empty()) stopped_reason_ = "complete";
    WriteSnapshot(stopped_reason_ == "complete");
  }

 private:
  bool StopRequested() {
    if (!stopped_reason_.empty()) return true;
    if (g_signal_requested.load()) {
      stopped_reason_ = "signal";
      return true;
    }
    if (args_.max_states && seen_.size() >= args_.max_states) {
      stopped_reason_ = "state_cap";
      return true;
    }
    const auto now = std::chrono::steady_clock::now();
    const double elapsed = std::chrono::duration<double>(now - started_).count();
    if (elapsed >= args_.seconds) {
      stopped_reason_ = "deadline";
      return true;
    }
    if (std::chrono::duration<double>(now - last_checkpoint_).count() >=
        args_.checkpoint_seconds) {
      WriteSnapshot(false);
      last_checkpoint_ = now;
    }
    return false;
  }

  std::array<Mask, kGroupSize> Images(Mask support) const {
    std::array<Mask, kGroupSize> result{};
    for (int group_index = 0; group_index < kGroupSize; ++group_index) {
      result[group_index] = Transform(support, group_[group_index]);
    }
    return result;
  }

  Mask CanonicalExtension(const std::array<Mask, kGroupSize>& parent_images,
                          Mask missing) const {
    Mask result;
    bool initialized = false;
    const std::vector<int> bits = SetBits(missing);
    for (int group_index = 0; group_index < kGroupSize; ++group_index) {
      Mask image = parent_images[group_index];
      for (int bit : bits) image |= bit_images_[group_index][bit];
      if (!initialized || image < result) {
        result = image;
        initialized = true;
      }
    }
    return result;
  }

  int BadOrthogonalityGroups(Mask support) const {
    int bad = 0;
    for (int row = 0; row < kRows; ++row) {
      for (int terminal = 0; terminal < kRows; ++terminal) {
        if (row == terminal) continue;
        int count = 0;
        for (int colour = 0; colour < kColours; ++colour) {
          bool excluded = false;
          if (args_.pattern == Pattern::k111) {
            excluded = terminal < 3 && colour == terminal;
          } else {
            excluded = (terminal == 0 && (colour == 0 || colour == 1)) ||
                       (terminal == 1 && colour == 2);
          }
          if (!excluded && HasBit(support, EntryId(row, terminal, colour))) ++count;
        }
        if (count == 1) ++bad;
      }
    }
    return bad;
  }

  struct Singleton {
    bool found = false;
    int root = -1;
    int word = -1;
    Mask only;
  };

  Singleton FirstSingleton(Mask support) const {
    for (int root = 0; root < kRows; ++root) {
      for (int word = 0; word < kWordCount; ++word) {
        if (ExpectedWord(args_.pattern, root, model_.words[word])) continue;
        int count = 0;
        Mask only;
        for (Mask matching : model_.match_masks[root][word]) {
          if (Subset(matching, support)) {
            ++count;
            only = matching;
            if (count > 1) break;
          }
        }
        if (count == 1) return Singleton{true, root, word, only};
      }
    }
    return Singleton{};
  }

  void Recurse(Mask support, int remaining) {
    if ((seen_.size() & 1023U) == 0 && StopRequested()) return;
    const auto [_, inserted] = seen_.insert(support);
    if (!inserted) {
      ++branches_["duplicate_state"];
      return;
    }
    ++states_by_remaining_[remaining];
    const int bad = BadOrthogonalityGroups(support);
    if (bad > remaining) {
      ++branches_["orthogonality_lower_bound_prune"];
      return;
    }
    const Singleton singleton = FirstSingleton(support);
    if (remaining == 0) {
      if (!singleton.found && bad == 0) {
        if (Popcount(support) != args_.target_size) {
          throw std::runtime_error("frontier support-size mismatch");
        }
        ++frontier_count_;
        const Classification classification = Classify(model_, args_.pattern, support);
        ++outcome_counts_[classification.outcome];
        if (classification.portable_kind != "none") {
          ++portable_certificate_counts_[classification.portable_kind];
        } else {
          exceptional_supports_.push_back(ExceptionalSupport{
              support, classification.outcome, classification.binomial_rows,
              classification.lattice_rank});
        }
        if (classification.outcome == "open") open_supports_.insert(support);
      }
      return;
    }

    const auto parent_images = Images(support);
    std::vector<Mask> children;
    if (!singleton.found) {
      ++branches_["free_states"];
      for (int bit : model_.valid_bits) {
        if (!HasBit(support, bit)) {
          children.push_back(CanonicalExtension(parent_images, Bit(bit)));
        }
      }
      branches_["free_child_orbits"] += children.size();
    } else {
      for (Mask alternative : model_.match_masks[singleton.root][singleton.word]) {
        if (alternative == singleton.only) continue;
        const Mask missing = alternative & ~support;
        const int used = Popcount(missing);
        if (used > 0 && used <= remaining) {
          children.push_back(CanonicalExtension(parent_images, missing));
        }
      }
      std::sort(children.begin(), children.end());
      children.erase(std::unique(children.begin(), children.end()), children.end());
      branches_["matching_child_orbits"] += children.size();
    }
    std::sort(children.begin(), children.end());
    children.erase(std::unique(children.begin(), children.end()), children.end());
    for (Mask child : children) {
      const int used = Popcount(child) - Popcount(support);
      if (used <= 0 || used > remaining) {
        throw std::runtime_error("canonical child increment mismatch");
      }
      Recurse(child, remaining - used);
      if (!stopped_reason_.empty()) return;
    }
  }

  static void WriteMap(std::ostream& output, const std::map<std::string, std::uint64_t>& map) {
    bool first = true;
    output << '{';
    for (const auto& [key, value] : map) {
      if (!first) output << ',';
      first = false;
      output << '\"' << key << "\":" << value;
    }
    output << '}';
  }

  void WriteSnapshot(bool complete) const {
    const fs::path temporary = args_.output.string() + ".tmp";
    fs::create_directories(args_.output.parent_path());
    std::ofstream output(temporary, std::ios::binary | std::ios::trunc);
    if (!output) throw std::runtime_error("cannot open output");
    output << "{\n";
    output << "  \"schema\": \"run083-native-frontier-v2\",\n";
    output << "  \"run_id\": \"" << args_.run_id << "\",\n";
    output << "  \"spec_sha256\": \"" << args_.spec_sha256 << "\",\n";
    output << "  \"pattern\": \"" << PatternName(args_.pattern) << "\",\n";
    output << "  \"target_size\": " << args_.target_size << ",\n";
    output << "  \"shard_id\": " << args_.shard_id << ",\n";
    output << "  \"shard_count\": " << args_.shard_count << ",\n";
    output << "  \"base_orbit_count\": " << bases_.size() << ",\n";
    output << "  \"assigned_base_orbits\": " << assigned_bases_.size() << ",\n";
    output << "  \"processed_base_orbits\": " << processed_bases_ << ",\n";
    output << "  \"complete\": " << (complete ? "true" : "false") << ",\n";
    output << "  \"stopped_reason\": \""
           << (complete ? "complete" : (stopped_reason_.empty() ? "checkpoint" : stopped_reason_))
           << "\",\n";
    output << "  \"visited_states\": " << seen_.size() << ",\n";
    output << "  \"frontier_count\": " << frontier_count_ << ",\n";
    output << "  \"states_by_remaining\": {";
    bool first = true;
    for (const auto& [key, value] : states_by_remaining_) {
      if (!first) output << ',';
      first = false;
      output << '\"' << key << "\":" << value;
    }
    output << "},\n";
    output << "  \"branch_counts\": ";
    WriteMap(output, branches_);
    output << ",\n  \"outcome_counts\": ";
    WriteMap(output, outcome_counts_);
    output << ",\n  \"portable_certificate_counts\": ";
    WriteMap(output, portable_certificate_counts_);
    output << ",\n  \"exceptional_supports\": [";
    first = true;
    for (const ExceptionalSupport& item : exceptional_supports_) {
      if (!first) output << ',';
      first = false;
      output << "{\"support_mask\":\"" << Decimal(item.support)
             << "\",\"outcome\":\"" << item.outcome
             << "\",\"binomial_rows\":" << item.binomial_rows
             << ",\"lattice_rank\":" << item.lattice_rank << '}';
    }
    output << "],\n  \"open_support_masks\": [";
    first = true;
    for (Mask support : open_supports_) {
      if (!first) output << ',';
      first = false;
      output << '\"' << Decimal(support) << '\"';
    }
    output << "]\n}\n";
    output.close();
    if (!output) throw std::runtime_error("failed writing output");
    std::error_code error;
    fs::rename(temporary, args_.output, error);
    if (error) {
      fs::remove(args_.output, error);
      error.clear();
      fs::rename(temporary, args_.output, error);
      if (error) throw std::runtime_error("atomic output replacement failed");
    }
  }

  Arguments args_;
  Model model_;
  std::vector<Mapping> group_;
  std::vector<Mask> bases_;
  std::vector<Mask> assigned_bases_;
  std::array<std::array<Mask, kBits>, kGroupSize> bit_images_{};
  std::unordered_set<Mask, MaskHash> seen_;
  std::map<int, std::uint64_t> states_by_remaining_;
  std::map<std::string, std::uint64_t> branches_;
  std::map<std::string, std::uint64_t> outcome_counts_;
  std::map<std::string, std::uint64_t> portable_certificate_counts_;
  std::vector<ExceptionalSupport> exceptional_supports_;
  std::set<Mask> open_supports_;
  std::uint64_t frontier_count_ = 0;
  std::uint64_t processed_bases_ = 0;
  std::string stopped_reason_;
  std::chrono::steady_clock::time_point started_;
  std::chrono::steady_clock::time_point last_checkpoint_;
};

}  // namespace

int main(int argc, char** argv) {
  try {
    std::signal(SIGTERM, HandleSignal);
    std::signal(SIGINT, HandleSignal);
    RunSignedPathContractTests();
    Arguments args = ParseArguments(argc, argv);
    Enumerator enumerator(std::move(args));
    enumerator.Run();
    flint_cleanup();
    return 0;
  } catch (const std::exception& error) {
    std::cerr << "error: " << error.what() << '\n';
    flint_cleanup();
    return 1;
  }
}
