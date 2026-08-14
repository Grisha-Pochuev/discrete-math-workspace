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

std::vector<long> ß^y¶‰žËkºwµçI…¬¡Á…É¥Ñä¤ì(€I½Ý1…ÑÑ¥”±…ÑÑ¥”¡•¹•É…Ñ½ÉÌ¤ì(€ÍÑèéÙ•Ñ½Èñ±½¹œøÍ¥¹}Ñ…É•Ð¡…Ñ¥Ù”¹Í¥é” ¤€¬€Ä°€À¤ì(€Í¥¹}Ñ…É•Ð¹‰…¬ ¤€ô€Äì(€¥˜€¡±…ÑÑ¥”¹½¹Ñ…¥¹Ì¡Í¥¹}Ñ…É•Ð¤¤ì(€€€½¹ÍÐ¥¹ÐÁ…Ñ¡}±•¹Ñ €ô(€€€€€€€U¹¥ÑM¥¹•‘A…Ñ¡1•¹Ñ ¡•¹•É…Ñ½ÉÌ°‰¥¹½µ¥…±}É½ÝÌ°Í¥¹}Ñ…É•Ð¤ì(€€€É•ÑÕÉ¸±…ÍÍ¥™¥…Ñ¥½¹ì‰Í¥¹}¥¹½¹Í¥ÍÑ•¹äˆ°¡¥ÍÑ½É…´°‰¥¹½µ¥…±}É½ÝÌ°(€€€€€€€€€€€€€€€€€€€€€€€€€±…ÑÑ¥”¹É…¹¬ ¤°(€€€€€€€€€€€€€€€€€€€€€€€€€Á…Ñ¡}±•¹Ñ €ü€‰Í¥¹}å±•|ˆ€¬ÍÑèéÑ½}ÍÑÉ¥¹œ¡Á…Ñ¡}±•¹Ñ ¤(€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€€è€‰¹½¹”ˆ°(€€€€€€€€€€€€€€€€€€€€€€€€€Á…Ñ¡}±•¹Ñ¡ôì(€ô(€‰½½°É•ÅÕ¥É•‘}…µÁ±¥ÑÕ‘•}é•É¼€ô™…±Í”ì(€™½È€¡½¹ÍÐ…ÕÑ¼˜Ñ•ÉµÌ€èÑ…É•ÑÌ¤ì(€€€¥˜€ …EÕ½Ñ¥•¹Ñ½•™™¥¥•¹ÑÌ¡Ñ•ÉµÌ°…Ñ¥Ù”°±…ÑÑ¥”¤¹•µÁÑä ¤¤½¹Ñ¥¹Õ”ì(€€€É•ÅÕ¥É•‘}…µÁ±¥ÑÕ‘•}é•É¼€ôÑÉÕ”ì(€€€¥˜€¡Ñ•ÉµÌ¹•µÁÑä ¤¤ì(€€€€€É•ÑÕÉ¸±…ÍÍ¥™¥…Ñ¥½¹ì‰É•ÅÕ¥É•‘}…µÁ±¥ÑÕ‘•}é•É¼ˆ°¡¥ÍÑ½É…´°‰¥¹½µ¥…±}É½ÝÌ°(€€€€€€€€€€€€€€€€€€€€€€€€€€€±…ÑÑ¥”¹É…¹¬ ¤°€‰µ¥ÍÍ¥¹}É•ÅÕ¥É•‘}…µÁ±¥ÑÕ‘”ˆ°€Áôì(€€€ô(€€€¥˜€¡Ñ•ÉµÌ¹Í¥é” ¤€„ô€È¤½¹Ñ¥¹Õ”ì(€€€½¹ÍÐ¥¹ÐÁ…Ñ¡}±•¹Ñ €ôU¹¥ÑM¥¹•‘A…Ñ¡1•¹Ñ  (€€€€€€€•¹•É…Ñ½ÉÌ°‰¥¹½µ¥…±}É½ÝÌ°(€€€€€€€áÁ½¹•¹Ñ¥™™•É•¹”¡Ñ•ÉµÍlÅt°Ñ•ÉµÍlÁt°…Ñ¥Ù”°€Ä¤¤ì(€€€¥˜€¡Á…Ñ¡}±•¹Ñ ¤ì(€€€€€É•ÑÕÉ¸±…ÍÍ¥™¥…Ñ¥½¹ì‰É•ÅÕ¥É•‘}…µÁ±¥ÑÕ‘•}é•É¼ˆ°¡¥ÍÑ½É…´°‰¥¹½µ¥…±}É½ÝÌ°(€€€€€€€€€€€€€€€€€€€€€€€€€€€±…ÑÑ¥”¹É…¹¬ ¤°(€€€€€€€€€€€€€€€€€€€€€€€€€€€€‰É•ÅÕ¥É•‘}Á…Ñ¡|ˆ€¬ÍÑèéÑ½}ÍÑÉ¥¹œ¡Á…Ñ¡}±•¹Ñ ¤°(€€€€€€€€€€€€€€€€€€€€€€€€€€€Á…Ñ¡}±•¹Ñ¡ôì(€€€ô(€ô(€¥˜€¡É•ÅÕ¥É•‘}…µÁ±¥ÑÕ‘•}é•É¼¤ì(€€€É•ÑÕÉ¸±…ÍÍ¥™¥…Ñ¥½¹ì‰É•ÅÕ¥É•‘}…µÁ±¥ÑÕ‘•}é•É¼ˆ°¡¥ÍÑ½É…´°‰¥¹½µ¥…±}É½ÝÌ°(€€€€€€€€€€€€€€€€€€€€€€€€€±…ÑÑ¥”¹É…¹¬ ¤°€‰¹½¹”ˆ°€Áôì(€ô(€™½È€¡½¹ÍÐ…ÕÑ¼˜Ñ•ÉµÌ€è±½¹•È¤ì(€€€¥˜€¡EÕ½Ñ¥•¹Ñ½•™™¥¥•¹ÑÌ¡Ñ•ÉµÌ°…Ñ¥Ù”°±…ÑÑ¥”¤¹Í¥é” ¤€ôô€Ä¤ì(€€€€€É•ÑÕÉ¸±…ÍÍ¥™¥…Ñ¥½¹ì‰ÅÕ½Ñ¥•¹Ñ}Õ¹¥Ðˆ°¡¥ÍÑ½É…´°‰¥¹½µ¥…±}É½ÝÌ°(€€€€€€€€€€€€€€€€€€€€€€€€€€€±…ÑÑ¥”¹É…¹¬ ¤°€‰¹½¹”ˆ°€Áôì(€€€ô(€ô(€É•ÑÕÉ¸±…ÍÍ¥™¥…Ñ¥½¹ì‰½Á•¸ˆ°¡¥ÍÑ½É…´°‰¥¹½µ¥…±}É½ÝÌ°±…ÑÑ¥”¹É…¹¬ ¤°(€€€€€€€€€€€€€€€€€€€€€€€€‰¹½¹”ˆ°€Áôì)ô()ÍÑÉÕÐÉÕµ•¹ÑÌì(€ÍÑèéÍÑÉ¥¹œÉÕ¹}¥ì(€ÍÑèéÍÑÉ¥¹œÍÁ•}Í¡„ÈÔØì(€A…ÑÑ•É¸Á…ÑÑ•É¸€ôA…ÑÑ•É¸èé¬ÄÄÄì(€¥¹ÐÑ…É•Ñ}Í¥é”€ô€Ääì(€¥¹ÐÍ¡…É‘}¥€ô€Àì(€¥¹ÐÍ¡…É‘}½Õ¹Ð€ô€Äì(€‘½Õ‰±”Í•½¹‘Ì€ô€äÀÀ¸Àì(€ÍÑèéÕ¥¹ÐØÑ}Ðµ…á}ÍÑ…Ñ•Ì€ô€Àì(€‘½Õ‰±”¡•­Á½¥¹Ñ}Í•½¹‘Ì€ô€ÄÈÀ¸Àì(€™ÌèéÁ…Ñ ½ÕÑÁÕÐì)ôì()ÉÕµ•¹ÑÌA…ÉÍ•ÉÕµ•¹ÑÌ¡¥¹Ð…ÉŒ°¡…È¨¨…ÉØ¤ì(€ÉÕµ•¹ÑÌ…ÉÌì(€™½È€¡¥¹Ð¥¹‘•à€ô€Äì¥¹‘•à€ð…ÉŒì€¬­¥¹‘•à¤ì(€€€½¹ÍÐÍÑèéÍÑÉ¥¹œ­•ä€ô…ÉÙm¥¹‘•átì(€€€¥˜€¡¥¹‘•à€¬€Ä€øô…ÉŒ¤Ñ¡É½ÜÍÑèéÉÕ¹Ñ¥µ•}•ÉÉ½È ‰µ¥ÍÍ¥¹œÙ…±Õ”™½È€ˆ€¬­•ä¤ì(€€€½¹ÍÐÍÑèéÍÑÉ¥¹œÙ…±Õ”€ô…ÉÙl¬­¥¹‘•átì(€€€¥˜€¡­•ä€ôô€ˆ´µÉÕ¸µ¥ˆ¤…ÉÌ¹ÉÕ¹}¥€ôÙ…±Õ”ì(€€€•±Í”¥˜€¡­•ä€ôô€ˆ´µÍÁ•ŒµÍ¡„ÈÔØˆ¤…ÉÌ¹ÍÁ•}Í¡„ÈÔØ€ôÙ…±Õ”ì(€€€•±Í”¥˜€¡­•ä€ôô€ˆ´µÁ…ÑÑ•É¸ˆ¤…ÉÌ¹Á…ÑÑ•É¸€ôA…ÉÍ•A…ÑÑ•É¸¡Ù…±Õ”¤ì(€€€•±Í”¥˜€¡­•ä€ôô€ˆ´µÑ…É•ÐµÍ¥é”ˆ¤…ÉÌ¹Ñ…É•Ñ}Í¥é”€ôÍÑèéÍÑ½¤¡Ù…±Õ”¤ì(€€€•±Í”¥˜€¡­•ä€ôô€ˆ´µÍ¡…Éµ¥ˆ¤…ÉÌ¹Í¡…É‘}¥€ôÍÑèéÍÑ½¤¡Ù…±Õ”¤ì(€€€•±Í”¥˜€¡­•ä€ôô€ˆ´µÍ¡…Éµ½Õ¹Ðˆ¤…ÉÌ¹Í¡…É‘}½Õ¹Ð€ôÍÑèéÍÑ½¤¡Ù…±Õ”¤ì(€€€•±Í”¥˜€¡­•ä€ôô€ˆ´µÍ•½¹‘Ìˆ¤…ÉÌ¹Í•½¹‘Ì€ôÍÑèéÍÑ½¡Ù…±Õ”¤ì(€€€•±Í”¥˜€¡­•ä€ôô€ˆ´µµ…àµÍÑ…Ñ•Ìˆ¤…ÉÌ¹µ…á}ÍÑ…Ñ•Ì€ôÍÑèéÍÑ½Õ±°¡Ù…±Õ”¤ì(€€€•±Í”¥˜€¡­•ä€ôô€ˆ´µ¡•­Á½¥¹ÐµÍ•½¹‘Ìˆ¤…ÉÌ¹¡•­Á½¥¹Ñ}Í•½¹‘Ì€ôÍÑèéÍÑ½¡Ù…±Õ”¤ì(€€€•±Í”¥˜€¡­•ä€ôô€ˆ´µ½ÕÑÁÕÐˆ¤…ÉÌ¹½ÕÑÁÕÐ€ôÙ…±Õ”ì(€€€•±Í”Ñ¡É½ÜÍÑèéÉÕ¹Ñ¥µ•}•ÉÉ½È ‰Õ¹­¹½Ý¸…ÉÕµ•¹Ðè€ˆ€¬­•ä¤ì(€ô(€¥˜€¡…ÉÌ¹ÉÕ¹}¥¹•µÁÑä ¤ñð…ÉÌ¹ÍÁ•}Í¡„ÈÔØ¹•µÁÑä ¤ñð…ÉÌ¹½ÕÑÁÕÐ¹•µÁÑä ¤¤ì(€€€Ñ¡É½ÜÍÑèéÉÕ¹Ñ¥µ•}•ÉÉ½È ‰ÉÕ¸µ¥°ÍÁ•ŒµÍ¡„ÈÔØ°…¹½ÕÑÁÕÐ…É”É•ÅÕ¥É•ˆ¤ì(€ô(€¥˜€¡…ÉÌ¹Ñ…É•Ñ}Í¥é”€ð€ÄÈñð…ÉÌ¹Ñ…É•Ñ}Í¥é”€ø€ÈÐ¤ì(€€€Ñ¡É½ÜÍÑèéÉÕ¹Ñ¥µ•}•ÉÉ½È ‰Õ¹ÍÕÁÁ½ÉÑ•Ñ…É•ÐÍ¥é”ˆ¤ì(€ô(€¥˜€¡…ÉÌ¹Í¡…É‘}½Õ¹Ð€ðô€Àñð…ÉÌ¹Í¡…É‘}¥€ð€Àñð…ÉÌ¹Í¡…É‘}¥€øô…ÉÌ¹Í¡…É‘}½Õ¹Ð¤ì(€€€Ñ¡É½ÜÍÑèéÉÕ¹Ñ¥µ•}•ÉÉ½È ‰¥¹Ù…±¥Í¡…É½¹ÑÉ…Ðˆ¤ì(€ô(€É•ÑÕÉ¸…ÉÌì)ô()±…ÍÌ¹Õµ•É…Ñ½Èì(ÁÕ‰±¥Œè(€•áÁ±¥¥Ð¹Õµ•É…Ñ½È¡ÉÕµ•¹ÑÌ…ÉÌ¤(€€€€€€è…ÉÍ|¡ÍÑèéµ½Ù”¡…ÉÌ¤¤°(€€€€€€€É½ÕÁ|¡	Õ¥±‘É½ÕÀ¡…ÉÍ|¹Á…ÑÑ•É¸¤¤°(€€€€€€€‰…Í•Í|¡%¹¥Ñ¥…±	…Í•Ì¡µ½‘•±|°…ÉÍ|¹Á…ÑÑ•É¸°É½ÕÁ|¤¤°(€€€€€€€ÍÑ…ÉÑ•‘|¡ÍÑèé¡É½¹¼èéÍÑ•…‘å}±½¬èé¹½Ü ¤¤°(€€€€€€€±…ÍÑ}¡•­Á½¥¹Ñ|¡ÍÑ…ÉÑ•‘|¤ì(€€€™½È€¡¥¹Ð‰¥Ð€ô€Àì‰¥Ð€ð­	¥ÑÌì€¬­‰¥Ð¤ì(€€€€€™½È€¡¥¹ÐÉ½ÕÁ}¥¹‘•à€ô€ÀìÉ½ÕÁ}¥¹‘•à€ð­É½ÕÁM¥é”ì€¬­É½ÕÁ}¥¹‘•à¤ì(€€€€€€€¥˜€¡É½ÕÁ}mÉ½ÕÁ}¥¹‘•áum‰¥Ñt€øô€À¤ì(€€€€€€€€€‰¥Ñ}¥µ…•Í}mÉ½ÕÁ}¥¹‘•áum‰¥Ñt€ô	¥Ð¡É½ÕÁ}mÉ½ÕÁ}¥¹‘•áum‰¥Ñt¤ì(€€€€€€€ô(€€€€€ô(€€€ô(€€€™½È€¡ÍÑèéÍ¥é•}Ð¥¹‘•à€ô€Àì¥¹‘•à€ð‰…Í•Í|¹Í¥é” ¤ì€¬­¥¹‘•à¤ì(€€€€€¥˜€¡ÍÑ…Ñ¥}…ÍÐñ¥¹Ðø¡¥¹‘•à€”…ÉÍ|¹Í¡…É‘}½Õ¹Ð¤€ôô…ÉÍ|¹Í¡…É‘}¥¤ì(€€€€€€€…ÍÍ¥¹•‘}‰…Í•Í|¹ÁÕÍ¡}‰…¬¡‰…Í•Í}m¥¹‘•át¤ì(€€€€€ô(€€€ô(€ô((€Ù½¥IÕ¸ ¤ì(€€€™½È€¡5…Í¬ÍÕÁÁ½ÉÐ€è…ÍÍ¥¹•‘}‰…Í•Í|¤ì(€€€€€¥˜€¡MÑ½ÁI•ÅÕ•ÍÑ• ¤¤‰É•…¬ì(€€€€€I•ÕÉÍ”¡ÍÕÁÁ½ÉÐ°…ÉÍ|¹Ñ…É•Ñ}Í¥é”€´A½Á½Õ¹Ð¡ÍÕÁÁ½ÉÐ¤¤ì(€€€€€¥˜€¡ÍÑ½ÁÁ•‘}É•…Í½¹|¹•µÁÑä ¤¤€¬­ÁÉ½•ÍÍ•‘}‰…Í•Í|ì(€€€ô(€€€¥˜€¡ÍÑ½ÁÁ•‘}É•…Í½¹|¹•µÁÑä ¤¤ÍÑ½ÁÁ•‘}É•…Í½¹|€ô€‰½µÁ±•Ñ”ˆì(€€€]É¥Ñ•M¹…ÁÍ¡½Ð¡ÍÑ½ÁÁ•‘}É•…Í½¹|€ôô€‰½µÁ±•Ñ”ˆ¤ì(€ô((ÁÉ¥Ù…Ñ”è(€‰½½°MÑ½ÁI•ÅÕ•ÍÑ• ¤ì(€€€¥˜€ …ÍÑ½ÁÁ•‘}É•…Í½¹|¹•µÁÑä ¤¤É•ÑÕÉ¸ÑÉÕ”ì(€€€¥˜€¡}Í¥¹…±}É•ÅÕ•ÍÑ•¹±½… ¤¤ì(€€€€€ÍÑ½ÁÁ•‘}É•…Í½¹|€ô€‰Í¥¹…°ˆì(€€€€€É•ÑÕÉ¸ÑÉÕ”ì(€€€ô(€€€¥˜€¡…ÉÍ|¹µ…á}ÍÑ…Ñ•Ì€˜˜Í••¹|¹Í¥é” ¤€øô…ÉÍ|¹µ…á}ÍÑ…Ñ•Ì¤ì(€€€€€ÍÑ½ÁÁ•‘}É•…Í½¹|€ô€‰ÍÑ…Ñ•}…Àˆì(€€€€€É•ÑÕÉ¸ÑÉÕ”ì(€€€ô(€€€½¹ÍÐ…ÕÑ¼¹½Ü€ôÍÑèé¡É½¹¼èéÍÑ•…‘å}±½¬èé¹½Ü ¤ì(€€€½¹ÍÐ‘½Õ‰±”•±…ÁÍ•€ôÍÑèé¡É½¹¼èé‘ÕÉ…Ñ¥½¸ñ‘½Õ‰±”ø¡¹½Ü€´ÍÑ…ÉÑ•‘|¤¹½Õ¹Ð ¤ì(€€€¥˜€¡•±…ÁÍ•€øô…ÉÍ|¹Í•½¹‘Ì¤ì(€€€€€ÍÑ½ÁÁ•‘}É•…Í½¹|€ô€‰‘•…‘±¥¹”ˆì(€€€€€É•ÑÕÉ¸ÑÉÕ”ì(€€€ô(€€€¥˜€¡ÍÑèé¡É½¹¼èé‘ÕÉ…Ñ¥½¸ñ‘½Õ‰±”ø¡¹½Ü€´±…ÍÑ}¡•­Á½¥¹Ñ|¤¹½Õ¹Ð ¤€øô(€€€€€€€…ÉÍ|¹¡•­Á½¥¹Ñ}Í•½¹‘Ì¤ì(€€€€€]É¥Ñ•M¹…ÁÍ¡½Ð¡™…±Í”¤ì(€€€€€±…ÍÑ}¡•­Á½¥¹Ñ|€ô¹½Üì(€€€ô(€€€É•ÑÕÉ¸™…±Í”ì(€ô((€ÍÑèé…ÉÉ…äñ5…Í¬°­É½ÕÁM¥é”ø%µ…•Ì¡5…Í¬ÍÕÁÁ½ÉÐ¤½¹ÍÐì(€€€ÍÑèé…ÉÉ…äñ5…Í¬°­É½ÕÁM¥é”øÉ•ÍÕ±Ñíôì(€€€™½È€¡¥¹ÐÉ½ÕÁ}¥¹‘•à€ô€ÀìÉ½ÕÁ}¥¹‘•à€ð­É½ÕÁM¥é”ì€¬­É½ÕÁ}¥¹‘•à¤ì(€€€€€É•ÍÕ±ÑmÉ½ÕÁ}¥¹‘•át€ôQÉ…¹Í™½É´¡ÍÕÁÁ½ÉÐ°É½ÕÁ}mÉ½ÕÁ}¥¹‘•át¤ì(€€€ô(€€€É•ÑÕÉ¸É•ÍÕ±Ðì(€ô((€5…Í¬…¹½¹¥…±áÑ•¹Í¥½¸¡½¹ÍÐÍÑèé…ÉÉ…äñ5…Í¬°­É½ÕÁM¥é”ø˜Á…É•¹Ñ}¥µ…•Ì°(€€€€€€€€€€€€€€€€€€€€€€€€€5…Í¬µ¥ÍÍ¥¹œ¤½¹ÍÐì(€€€5…Í¬É•ÍÕ±Ðì(€€€‰½½°¥¹¥Ñ¥…±¥é•€ô™…±Í”ì(€€€½¹ÍÐÍÑèéÙ•Ñ½Èñ¥¹Ðø‰¥ÑÌ€ôM•Ñ	¥ÑÌ¡µ¥ÍÍ¥¹œ¤ì(€€€™½È€¡¥¹ÐÉ½ÕÁ}¥¹‘•à€ô€ÀìÉ½ÕÁ}¥¹‘•à€ð­É½ÕÁM¥é”ì€¬­É½ÕÁ}¥¹‘•à¤ì(€€€€€5…Í¬¥µ…”€ôÁ…É•¹Ñ}¥µ…•ÍmÉ½ÕÁ}¥¹‘•átì(€€€€€™½È€¡¥¹Ð‰¥Ð€è‰¥ÑÌ¤¥µ…”ðô‰¥Ñ}¥µ…•Í}mÉ½ÕÁ}¥¹‘•áum‰¥Ñtì(€€€€€¥˜€ …¥¹¥Ñ¥…±¥é•ñð¥µ…”€ðÉ•ÍÕ±Ð¤ì(€€€€€€€É•ÍÕ±Ð€ô¥µ…”ì(€€€€€€€¥¹¥Ñ¥…±¥é•€ôÑÉÕ”ì(€€€€€ô(€€€ô(€€€É•ÑÕÉ¸É•ÍÕ±Ðì(€ô((€¥¹Ð	…‘=ÉÑ¡½½¹…±¥ÑåÉ½ÕÁÌ¡5…Í¬ÍÕÁÁ½ÉÐ¤½¹ÍÐì(€€€¥¹Ð‰…€ô€Àì(€€€™½È€¡¥¹ÐÉ½Ü€ô€ÀìÉ½Ü€ð­I½ÝÌì€¬­É½Ü¤ì(€€€€€™½È€¡¥¹ÐÑ•Éµ¥¹…°€ô€ÀìÑ•Éµ¥¹…°€ð­I½ÝÌì€¬­Ñ•Éµ¥¹…°¤ì(€€€€€€€¥˜€¡É½Ü€ôôÑ•Éµ¥¹…°¤½¹Ñ¥¹Õ”ì(€€€€€€€¥¹Ð½Õ¹Ð€ô€Àì(€€€€€€€™½È€¡¥¹Ð½±½ÕÈ€ô€Àì½±½ÕÈ€ð­½±½ÕÉÌì€¬­½±½ÕÈ¤ì(€€€€€€€€€‰½½°•á±Õ‘•€ô™…±Í”ì(€€€€€€€€€¥˜€¡…ÉÍ|¹Á…ÑÑ•É¸€ôôA…ÑÑ•É¸èé¬ÄÄÄ¤ì(€€€€€€€€€€€•á±Õ‘•€ôÑ•Éµ¥¹…°€ð€Ì€˜˜½±½ÕÈ€ôôÑ•Éµ¥¹…°ì(€€€€€€€€€ô•±Í”ì(€€€€€€€€€€€•á±Õ‘•€ô€¡Ñ•Éµ¥¹…°€ôô€À€˜˜€¡½±½ÕÈ€ôô€Àñð½±½ÕÈ€ôô€Ä¤¤ñð(€€€€€€€€€€€€€€€€€€€€€€€¡Ñ•Éµ¥¹…°€ôô€Ä€˜˜½±½ÕÈ€ôô€È¤ì(€€€€€€€€€ô(€€€€€€€€€¥˜€ …•á±Õ‘•€˜˜!…Í	¥Ð¡ÍÕÁÁ½ÉÐ°¹ÑÉå%¡É½Ü°Ñ•Éµ¥¹…°°½±½ÕÈ¤¤¤€¬­½Õ¹Ðì(€€€€€€€ô(€€€€€€€¥˜€¡½Õ¹Ð€ôô€Ä¤€¬­‰…ì(€€€€€ô(€€€ô(€€€É•ÑÕÉ¸‰…ì(€ô((€ÍÑÉÕÐM¥¹±•Ñ½¸ì(€€€‰½½°™½Õ¹€ô™…±Í”ì(€€€¥¹ÐÉ½½Ð€ô€´Äì(€€€¥¹ÐÝ½É€ô€´Äì(€€€5…Í¬½¹±äì(€ôì((€M¥¹±•Ñ½¸¥ÉÍÑM¥¹±•Ñ½¸¡5…Í¬ÍÕÁÁ½ÉÐ¤½¹ÍÐì(€€€™½È€¡¥¹ÐÉ½½Ð€ô€ÀìÉ½½Ð€ð­I½ÝÌì€¬­É½½Ð¤ì(€€€€€™½È€¡¥¹ÐÝ½É€ô€ÀìÝ½É€ð­]½É‘½Õ¹Ðì€¬­Ý½É¤ì(€€€€€€€¥˜€¡áÁ•Ñ•‘]½É¡…ÉÍ|¹Á…ÑÑ•É¸°É½½Ð°µ½‘•±|¹Ý½É‘ÍmÝ½É‘t¤¤½¹Ñ¥¹Õ”ì(€€€€€€€¥¹Ð½Õ¹Ð€ô€Àì(€€€€€€€5…Í¬½¹±äì(€€€€€€€™½È€¡5…Í¬µ…Ñ¡¥¹œ€èµ½‘•±|¹µ…Ñ¡}µ…Í­ÍmÉ½½ÑumÝ½É‘t¤ì(€€€€€€€€€¥˜€¡MÕ‰Í•Ð¡µ…Ñ¡¥¹œ°ÍÕÁÁ½ÉÐ¤¤ì(€€€€€€€€€€€€¬­½Õ¹Ðì(€€€€€€€€€€€½¹±ä€ôµ…Ñ¡¥¹œì(€€€€€€€€€€€¥˜€¡½Õ¹Ð€ø€Ä¤‰É•…¬ì(€€€€€€€€€ô(€€€€€€€ô(€€€€€€€¥˜€¡½Õ¹Ð€ôô€Ä¤É•ÑÕÉ¸M¥¹±•Ñ½¹íÑÉÕ”°É½½Ð°Ý½É°½¹±åôì(€€€€€ô(€€€ô(€€€É•ÑÕÉ¸M¥¹±•Ñ½¹íôì(€ô((€Ù½¥I•ÕÉÍ”¡5…Í¬ÍÕÁÁ½ÉÐ°¥¹ÐÉ•µ…¥¹¥¹œ¤ì(€€€¥˜€ ¡Í••¹|¹Í¥é” ¤€˜€ÄÀÈÍT¤€ôô€À€˜˜MÑ½ÁI•ÅÕ•ÍÑ• ¤¤É•ÑÕÉ¸ì(€€€½¹ÍÐ…ÕÑ¼m|°¥¹Í•ÉÑ•‘t€ôÍ••¹|¹¥¹Í•ÉÐ¡ÍÕÁÁ½ÉÐ¤ì(€€€¥˜€ …¥¹Í•ÉÑ•¤ì(€€€€€€¬­‰É…¹¡•Í}l‰‘ÕÁ±¥…Ñ•}ÍÑ…Ñ”‰tì(€€€€€É•ÑÕÉ¸ì(€€€ô(€€€€¬­ÍÑ…Ñ•Í}‰å}É•µ…¥¹¥¹}mÉ•µ…¥¹¥¹tì(€€€½¹ÍÐ¥¹Ð‰…€ô	…‘=ÉÑ¡½½¹…±¥ÑåÉ½ÕÁÌ¡ÍÕÁÁ½ÉÐ¤ì(€€€¥˜€¡‰…€øÉ•µ…¥¹¥¹œ¤ì(€€€€€€¬­‰É…¹¡•Í}l‰½ÉÑ¡½½¹…±¥Ñå}±½Ý•É}‰½Õ¹‘}ÁÉÕ¹”‰tì(€€€€€É•ÑÕÉ¸ì(€€€ô(€€€½¹ÍÐM¥¹±•Ñ½¸Í¥¹±•Ñ½¸€ô¥ÉÍÑM¥¹±•Ñ½¸¡ÍÕÁÁ½ÉÐ¤ì(€€€¥˜€¡É•µ…¥¹¥¹œ€ôô€À¤ì(€€€€€¥˜€ …Í¥¹±•Ñ½¸¹™½Õ¹€˜˜‰…€ôô€À¤ì(€€€€€€€¥˜€¡A½Á½Õ¹Ð¡ÍÕÁÁ½ÉÐ¤€„ô…ÉÍ|¹Ñ…É•Ñ}Í¥é”¤ì(€€€€€€€€€Ñ¡É½ÜÍÑèéÉÕ¹Ñ¥µ•}•ÉÉ½È ‰™É½¹Ñ¥•ÈÍÕÁÁ½ÉÐµÍ¥é”µ¥Íµ…Ñ ˆ¤ì(€€€€€€€ô(€€€€€€€€¬­™É½¹Ñ¥•É}½Õ¹Ñ|ì(€€€€€€€½¹ÍÐ±…ÍÍ¥™¥…Ñ¥½¸±…ÍÍ¥™¥…Ñ¥½¸€ô±…ÍÍ¥™ä¡µ½‘•±|°…ÉÍ|¹Á…ÑÑ•É¸°ÍÕÁÁ½ÉÐ¤ì(€€€€€€€€¬­½ÕÑ½µ•}½Õ¹ÑÍ}m±…ÍÍ¥™¥…Ñ¥½¸¹½ÕÑ½µ•tì(€€€€€€€¥˜€¡±…ÍÍ¥™¥…Ñ¥½¸¹Á½ÉÑ…‰±•}­¥¹€„ô€‰¹½¹”ˆ¤ì(€€€€€€€€€€¬­Á½ÉÑ…‰±•}•ÉÑ¥™¥…Ñ•}½Õ¹ÑÍ}m±…ÍÍ¥™¥…Ñ¥½¸¹Á½ÉÑ…‰±•}­¥¹‘tì(€€€€€€€ô•±Í”ì(€€€€€€€€€•á•ÁÑ¥½¹…±}ÍÕÁÁ½ÉÑÍ|¹ÁÕÍ¡}‰…¬¡á•ÁÑ¥½¹…±MÕÁÁ½ÉÑì(€€€€€€€€€€€€€ÍÕÁÁ½ÉÐ°±…ÍÍ¥™¥…Ñ¥½¸¹½ÕÑ½µ”°±…ÍÍ¥™¥…Ñ¥½¸¹‰¥¹½µ¥…±}É½ÝÌ°(€€€€€€€€€€€€€±…ÍÍ¥™¥…Ñ¥½¸¹±…ÑÑ¥•}É…¹­ô¤ì(€€€€€€€ô(€€€€€€€¥˜€¡±…ÍÍ¥™¥…Ñ¥½¸¹½ÕÑ½µ”€ôô€‰½Á•¸ˆ¤½Á•¹}ÍÕÁÁ½ÉÑÍ|¹¥¹Í•ÉÐ¡ÍÕÁÁ½ÉÐ¤ì(€€€€€ô(€€€€€É•ÑÕÉ¸ì(€€€ô((€€€½¹ÍÐ…ÕÑ¼Á…É•¹Ñ}¥µ…•Ì€ô%µ…•Ì¡ÍÕÁÁ½ÉÐ¤ì(€€€ÍÑèéÙ•Ñ½Èñ5…Í¬ø¡¥±‘É•¸ì(€€€¥˜€ …Í¥¹±•Ñ½¸¹™½Õ¹¤ì(€€€€€€¬­‰É…¹¡•Í}l‰™É••}ÍÑ…Ñ•Ì‰tì(€€€€€™½È€¡¥¹Ð‰¥Ð€èµ½‘•±|¹Ù…±¥‘}‰¥ÑÌ¤ì(€€€€€€€¥˜€ …!…Í	¥Ð¡ÍÕÁÁ½ÉÐ°‰¥Ð¤¤ì(€€€€€€€€€¡¥±‘É•¸¹ÁÕÍ¡}‰…¬¡…¹½¹¥…±áÑ•¹Í¥½¸¡Á…É•¹Ñ}¥µ…•Ì°	¥Ð¡‰¥Ð¤¤¤ì(€€€€€€€ô(€€€€€ô(€€€€€‰É…¹¡•Í}l‰™É••}¡¥±‘}½É‰¥ÑÌ‰t€¬ô¡¥±‘É•¸¹Í¥é” ¤ì(€€€ô•±Í”ì(€€€€€™½È€¡5…Í¬…±Ñ•É¹…Ñ¥Ù”€èµ½‘•±|¹µ…Ñ¡}µ…Í­ÍmÍ¥¹±•Ñ½¸¹É½½ÑumÍ¥¹±•Ñ½¸¹Ý½É‘t¤ì(€€€€€€€¥˜€¡…±Ñ•É¹…Ñ¥Ù”€ôôÍ¥¹±•Ñ½¸¹½¹±ä¤½¹Ñ¥¹Õ”ì(€€€€€€€½¹ÍÐ5…Í¬µ¥ÍÍ¥¹œ€ô…±Ñ•É¹…Ñ¥Ù”€˜ùÍÕÁÁ½ÉÐì(€€€€€€€½¹ÍÐ¥¹ÐÕÍ•€ôA½Á½Õ¹Ð¡µ¥ÍÍ¥¹œ¤ì(€€€€€€€¥˜€¡ÕÍ•€ø€À€˜˜ÕÍ•€ðôÉ•µ…¥¹¥¹œ¤ì(€€€€€€€€€¡¥±‘É•¸¹ÁÕÍ¡}‰…¬¡…¹½¹¥…±áÑ•¹Í¥½¸¡Á…É•¹Ñ}¥µ…•Ì°µ¥ÍÍ¥¹œ¤¤ì(€€€€€€€ô(€€€€€ô(€€€€€ÍÑèéÍ½ÉÐ¡¡¥±‘É•¸¹‰•¥¸ ¤°¡¥±‘É•¸¹•¹ ¤¤ì(€€€€€¡¥±‘É•¸¹•É…Í”¡ÍÑèéÕ¹¥ÅÕ”¡¡¥±‘É•¸¹‰•¥¸ ¤°¡¥±‘É•¸¹•¹ ¤¤°¡¥±‘É•¸¹•¹ ¤¤ì(€€€€€‰É…¹¡•Í}l‰µ…Ñ¡¥¹}¡¥±‘}½É‰¥ÑÌ‰t€¬ô¡¥±‘É•¸¹Í¥é” ¤ì(€€€ô(€€€ÍÑèéÍ½ÉÐ¡¡¥±‘É•¸¹‰•¥¸ ¤°¡¥±‘É•¸¹•¹ ¤¤ì(€€€¡¥±‘É•¸¹•É…Í”¡ÍÑèéÕ¹¥ÅÕ”¡¡¥±‘É•¸¹‰•¥¸ ¤°¡¥±‘É•¸¹•¹ ¤¤°¡¥±‘É•¸¹•¹ ¤¤ì(€€€™½È€¡5…Í¬¡¥±€è¡¥±‘É•¸¤ì(€€€€€½¹ÍÐ¥¹ÐÕÍ•€ôA½Á½Õ¹Ð¡¡¥±¤€´A½Á½Õ¹Ð¡ÍÕÁÁ½ÉÐ¤ì(€€€€€¥˜€¡ÕÍ•€ðô€ÀñðÕÍ•€øÉ•µ…¥¹¥¹œ¤ì(€€€€€€€Ñ¡É½ÜÍÑèéÉÕ¹Ñ¥µ•}•ÉÉ½È ‰…¹½¹¥…°¡¥±¥¹É•µ•¹Ðµ¥Íµ…Ñ ˆ¤ì(€€€€€ô(€€€€€I•ÕÉÍ”¡¡¥±°É•µ…¥¹¥¹œ€´ÕÍ•¤ì(€€€€€¥˜€ …ÍÑ½ÁÁ•‘}É•…Í½¹|¹•µÁÑä ¤¤É•ÑÕÉ¸ì(€€€ô(€ô((€ÍÑ…Ñ¥ŒÙ½¥]É¥Ñ•5…À¡ÍÑèé½ÍÑÉ•…´˜½ÕÑÁÕÐ°½¹ÍÐÍÑèéµ…ÀñÍÑèéÍÑÉ¥¹œ°ÍÑèéÕ¥¹ÐØÑ}Ðø˜µ…À¤ì(€€€‰½½°™¥ÉÍÐ€ôÑÉÕ”ì(€€€½ÕÑÁÕÐ€ðð€ìœì(€€€™½È€¡½¹ÍÐ…ÕÑ¼˜m­•ä°Ù…±Õ•t€èµ…À¤ì(€€€€€¥˜€ …™¥ÉÍÐ¤½ÕÑÁÕÐ€ðð€œ°œì(€€€€€™¥ÉÍÐ€ô™…±Í”ì(€€€€€½ÕÑÁÕÐ€ðð€pˆœ€ðð­•ä€ðð€‰pˆèˆ€ððÙ…±Õ”ì(€€€ô(€€€½ÕÑÁÕÐ€ðð€ôœì(€ô((€Ù½¥]É¥Ñ•M¹…ÁÍ¡½Ð¡‰½½°½µÁ±•Ñ”¤½¹ÍÐì(€€€½¹ÍÐ™ÌèéÁ…Ñ Ñ•µÁ½É…Éä€ô…ÉÍ|¹½ÕÑÁÕÐ¹ÍÑÉ¥¹œ ¤€¬€ˆ¹ÑµÀˆì(€€€™ÌèéÉ•…Ñ•}‘¥É•Ñ½É¥•Ì¡…ÉÍ|¹½ÕÑÁÕÐ¹Á…É•¹Ñ}Á…Ñ  ¤¤ì(€€€ÍÑèé½™ÍÑÉ•…´½ÕÑÁÕÐ¡Ñ•µÁ½É…Éä°ÍÑèé¥½Ìèé‰¥¹…ÉäðÍÑèé¥½ÌèéÑÉÕ¹Œ¤ì(€€€¥˜€ …½ÕÑÁÕÐ¤Ñ¡É½ÜÍÑèéÉÕ¹Ñ¥µ•}•ÉÉ½È ‰…¹¹½Ð½Á•¸½ÕÑÁÕÐˆ¤ì(€€€½ÕÑÁÕÐ€ðð€‰íq¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰Í¡•µ…pˆèp‰ÉÕ¸ÀàÌµ¹…Ñ¥Ù”µ™É½¹Ñ¥•ÈµØÉpˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰ÉÕ¹}¥‘pˆèpˆˆ€ðð…ÉÍ|¹ÉÕ¹}¥€ðð€‰pˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰ÍÁ•}Í¡„ÈÔÙpˆèpˆˆ€ðð…ÉÍ|¹ÍÁ•}Í¡„ÈÔØ€ðð€‰pˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰Á…ÑÑ•É¹pˆèpˆˆ€ððA…ÑÑ•É¹9…µ”¡…ÉÍ|¹Á…ÑÑ•É¸¤€ðð€‰pˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰Ñ…É•Ñ}Í¥é•pˆè€ˆ€ðð…ÉÍ|¹Ñ…É•Ñ}Í¥é”€ðð€ˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰Í¡…É‘}¥‘pˆè€ˆ€ðð…ÉÍ|¹Í¡…É‘}¥€ðð€ˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰Í¡…É‘}½Õ¹Ñpˆè€ˆ€ðð…ÉÍ|¹Í¡…É‘}½Õ¹Ð€ðð€ˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰‰…Í•}½É‰¥Ñ}½Õ¹Ñpˆè€ˆ€ðð‰…Í•Í|¹Í¥é” ¤€ðð€ˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰…ÍÍ¥¹•‘}‰…Í•}½É‰¥ÑÍpˆè€ˆ€ðð…ÍÍ¥¹•‘}‰…Í•Í|¹Í¥é” ¤€ðð€ˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰ÁÉ½•ÍÍ•‘}‰…Í•}½É‰¥ÑÍpˆè€ˆ€ððÁÉ½•ÍÍ•‘}‰…Í•Í|€ðð€ˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰½µÁ±•Ñ•pˆè€ˆ€ðð€¡½µÁ±•Ñ”€ü€‰ÑÉÕ”ˆ€è€‰™…±Í”ˆ¤€ðð€ˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰ÍÑ½ÁÁ•‘}É•…Í½¹pˆèpˆˆ(€€€€€€€€€€€ðð€¡½µÁ±•Ñ”€ü€‰½µÁ±•Ñ”ˆ€è€¡ÍÑ½ÁÁ•‘}É•…Í½¹|¹•µÁÑä ¤€ü€‰¡•­Á½¥¹Ðˆ€èÍÑ½ÁÁ•‘}É•…Í½¹|¤¤(€€€€€€€€€€€ðð€‰pˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰Ù¥Í¥Ñ•‘}ÍÑ…Ñ•Ípˆè€ˆ€ððÍ••¹|¹Í¥é” ¤€ðð€ˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰™É½¹Ñ¥•É}½Õ¹Ñpˆè€ˆ€ðð™É½¹Ñ¥•É}½Õ¹Ñ|€ðð€ˆ±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰ÍÑ…Ñ•Í}‰å}É•µ…¥¹¥¹pˆèìˆì(€€€‰½½°™¥ÉÍÐ€ôÑÉÕ”ì(€€€™½È€¡½¹ÍÐ…ÕÑ¼˜m­•ä°Ù…±Õ•t€èÍÑ…Ñ•Í}‰å}É•µ…¥¹¥¹|¤ì(€€€€€¥˜€ …™¥ÉÍÐ¤½ÕÑÁÕÐ€ðð€œ°œì(€€€€€™¥ÉÍÐ€ô™…±Í”ì(€€€€€½ÕÑÁÕÐ€ðð€pˆœ€ðð­•ä€ðð€‰pˆèˆ€ððÙ…±Õ”ì(€€€ô(€€€½ÕÑÁÕÐ€ðð€‰ô±q¸ˆì(€€€½ÕÑÁÕÐ€ðð€ˆ€p‰‰É…¹¡}½Õ¹ÑÍpˆè€ˆì(€€€]É¥Ñ•5…À¡½ÕÑÁÕÐ°‰É…¹¡•Í|¤ì(€€€½ÕÑÁÕÐ€ðð€ˆ±q¸€p‰½ÕÑ½µ•}½Õ¹ÑÍpˆè€ˆì(€€€]É¥Ñ•5…À¡½ÕÑÁÕÐ°½ÕÑ½µ•}½Õ¹ÑÍ|¤ì(€€€½ÕÑÁÕÐ€ðð€ˆ±q¸€p‰Á½ÉÑ…‰±•}•ÉÑ¥™¥…Ñ•}½Õ¹ÑÍpˆè€ˆì(€€€]É¥Ñ•5…À¡½ÕÑÁÕÐ°Á½ÉÑ…‰±•}•ÉÑ¥™¥…Ñ•}½Õ¹ÑÍ|¤ì(€€€½ÕÑÁÕÐ€ðð€ˆ±q¸€p‰•á•ÁÑ¥½¹…±}ÍÕÁÁ½ÉÑÍpˆèlˆì(€€€™¥ÉÍÐ€ôÑÉÕ”ì(€€€™½È€¡½¹ÍÐá•ÁÑ¥½¹…±MÕÁÁ½ÉÐ˜¥Ñ•´€è•á•ÁÑ¥½¹…±}ÍÕÁÁ½ÉÑÍ|¤ì(€€€€€¥˜€ …™¥ÉÍÐ¤½ÕÑÁÕÐ€ðð€œ°œì(€€€€€™¥ÉÍÐ€ô™…±Í”ì(€€€€€½ÕÑÁÕÐ€ðð€‰íp‰ÍÕÁÁ½ÉÑ}µ…Í­pˆépˆˆ€ðð•¥µ…°¡¥Ñ•´¹ÍÕÁÁ½ÉÐ¤(€€€€€€€€€€€€€ðð€‰pˆ±p‰½ÕÑ½µ•pˆépˆˆ€ðð¥Ñ•´¹½ÕÑ½µ”(€€€€€€€€€€€€€ðð€‰pˆ±p‰‰¥¹½µ¥…±}É½ÝÍpˆèˆ€ðð¥Ñ•´¹‰¥¹½µ¥…±}É½ÝÌ(€€€€€€€€€€€€€ðð€ˆ±p‰±…ÑÑ¥•}É…¹­pˆèˆ€ðð¥Ñ•´¹±…ÑÑ¥•}É…¹¬€ðð€ôœì(€€€ô(€€€½ÕÑÁÕÐ€ðð€‰t±q¸€p‰½Á•¹}ÍÕÁÁ½ÉÑ}µ…Í­Ípˆèlˆì(€€€™¥ÉÍÐ€ôÑÉÕ”ì(€€€™½È€¡5…Í¬ÍÕÁÁ½ÉÐ€è½Á•¹}ÍÕÁÁ½ÉÑÍ|¤ì(€€€€€¥˜€ …™¥ÉÍÐ¤½ÕÑÁÕÐ€ðð€œ°œì(€€€€€™¥ÉÍÐ€ô™…±Í”ì(€€€€€½ÕÑÁÕÐ€ðð€pˆœ€ðð•¥µ…°¡ÍÕÁÁ½ÉÐ¤€ðð€pˆœì(€€€ô(€€€½ÕÑÁÕÐ€ðð€‰uq¹õq¸ˆì(€€€½ÕÑÁÕÐ¹±½Í” ¤ì(€€€¥˜€ …½ÕÑÁÕÐ¤Ñ¡É½ÜÍÑèéÉÕ¹Ñ¥µ•}•ÉÉ½È ‰™…¥±•ÝÉ¥Ñ¥¹œ½ÕÑÁÕÐˆ¤ì(€€€ÍÑèé•ÉÉ½É}½‘”•ÉÉ½Èì(€€€™ÌèéÉ•¹…µ”¡Ñ•µÁ½É…Éä°…ÉÍ|¹½ÕÑÁÕÐ°•ÉÉ½È¤ì(€€€¥˜€¡•ÉÉ½È¤ì(€€€€€™ÌèéÉ•µ½Ù”¡…ÉÍ|¹½ÕÑÁÕÐ°•ÉÉ½È¤ì(€€€€€•ÉÉ½È¹±•…È ¤ì(€€€€€™ÌèéÉ•¹…µ”¡Ñ•µÁ½É…Éä°…ÉÍ|¹½ÕÑÁÕÐ°•ÉÉ½È¤ì(€€€€€¥˜€¡•ÉÉ½È¤Ñ¡É½ÜÍÑèéÉÕ¹Ñ¥µ•}•ÉÉ½È ‰…Ñ½µ¥Œ½ÕÑÁÕÐÉ•Á±…•µ•¹Ð™…¥±•ˆ¤ì(€€€ô(€ô((€ÉÕµ•¹ÑÌ…ÉÍ|ì(€5½‘•°µ½‘•±|ì(€ÍÑèéÙ•Ñ½Èñ5…ÁÁ¥¹œøÉ½ÕÁ|ì(€ÍÑèéÙ•Ñ½Èñ5…Í¬ø‰…Í•Í|ì(€ÍÑèéÙ•Ñ½Èñ5…Í¬ø…ÍÍ¥¹•‘}‰…Í•Í|ì(€ÍÑèé…ÉÉ…äñÍÑèé…ÉÉ…äñ5…Í¬°­	¥ÑÌø°­É½ÕÁM¥é”ø‰¥Ñ}¥µ…•Í}íôì(€ÍÑèéÕ¹½É‘•É•‘}Í•Ðñ5…Í¬°5…Í­!…Í øÍ••¹|ì(€ÍÑèéµ…Àñ¥¹Ð°ÍÑèéÕ¥¹ÐØÑ}ÐøÍÑ…Ñ•Í}‰å}É•µ…¥¹¥¹|ì(€ÍÑèéµ…ÀñÍÑèéÍÑÉ¥¹œ°ÍÑèéÕ¥¹ÐØÑ}Ðø‰É…¹¡•Í|ì(€ÍÑèéµ…ÀñÍÑèéÍÑÉ¥¹œ°ÍÑèéÕ¥¹ÐØÑ}Ðø½ÕÑ½µ•}½Õ¹ÑÍ|ì(€ÍÑèéµ…ÀñÍÑèéÍÑÉ¥¹œ°ÍÑèéÕ¥¹ÐØÑ}ÐøÁ½ÉÑ…‰±•}•ÉÑ¥™¥…Ñ•}½Õ¹ÑÍ|ì(€ÍÑèéÙ•Ñ½Èñá•ÁÑ¥½¹…±MÕÁÁ½ÉÐø•á•ÁÑ¥½¹…±}ÍÕÁÁ½ÉÑÍ|ì(€ÍÑèéÍ•Ðñ5…Í¬ø½Á•¹}ÍÕÁÁ½ÉÑÍ|ì(€ÍÑèéÕ¥¹ÐØÑ}Ð™É½¹Ñ¥•É}½Õ¹Ñ|€ô€Àì(€ÍÑèéÕ¥¹ÐØÑ}ÐÁÉ½•ÍÍ•‘}‰…Í•Í|€ô€Àì(€ÍÑèéÍÑÉ¥¹œÍÑ½ÁÁ•‘}É•…Í½¹|ì(€ÍÑèé¡É½¹¼èéÍÑ•…‘å}±½¬èéÑ¥µ•}Á½¥¹ÐÍÑ…ÉÑ•‘|ì(€ÍÑèé¡É½¹¼èéÍÑ•…‘å}±½¬èéÑ¥µ•}Á½¥¹Ð±…ÍÑ}¡•­Á½¥¹Ñ|ì)ôì()ô€€¼¼¹…µ•ÍÁ…”()¥¹Ðµ…¥¸¡¥¹Ð…ÉŒ°¡…È¨¨…ÉØ¤ì(€ÑÉäì(€€€ÍÑèéÍ¥¹…°¡M%QI4°!…¹‘±•M¥¹…°¤ì(€€€ÍÑèéÍ¥¹…°¡M%%9P°!…¹‘±•M¥¹…°¤ì(€€€IÕ¹M¥¹•‘A…Ñ¡½¹ÑÉ…ÑQ•ÍÑÌ ¤ì(€€€ÉÕµ•¹ÑÌ…ÉÌ€ôA…ÉÍ•ÉÕµ•¹ÑÌ¡…ÉŒ°…ÉØ¤ì(€€€¹Õµ•É…Ñ½È•¹Õµ•É…Ñ½È¡ÍÑèéµ½Ù”¡…ÉÌ¤¤ì(€€€•¹Õµ•É…Ñ½È¹IÕ¸ ¤ì(€€€™±¥¹Ñ}±•…¹ÕÀ ¤ì(€€€É•ÑÕÉ¸€Àì(€ô…Ñ €¡½¹ÍÐÍÑèé•á•ÁÑ¥½¸˜•ÉÉ½È¤ì(€€€ÍÑèé•ÉÈ€ðð€‰•ÉÉ½Èè€ˆ€ðð•ÉÉ½È¹Ý¡…Ð ¤€ðð€q¸œì(€€€™±¥¹Ñ}±•…¹ÕÀ ¤ì(€€€É•ÑÕÉ¸€Äì(€ô)ô(