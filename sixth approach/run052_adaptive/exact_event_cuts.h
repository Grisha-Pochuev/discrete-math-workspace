#pragma once

#include <array>
#include <string_view>

namespace exact_event_cuts {

inline constexpr std::string_view kBundleSha256 =
    "b37d4e04d449a4f03ea9150a36a7d2f3d41183aa9545b39086bd0f2dc450a9fc";

struct BinomialEvent {
  int state;
  int left;
  int right;
};

struct Cut {
  std::string_view graph;
  int source_shard;
  std::array<BinomialEvent, 3> binomials;
  bool has_target;
  int target_state;
  std::array<int, 3> target_matchings;
};

// Compact, independently audited event no-goods.  A binomial event means that
// the named row has exactly two supported terms and they are the named pair.
// A target event means that the named row has exactly the three named terms.
inline constexpr std::array<Cut, 4> kVersion1{{
    {
        "C4+C4",
        2,
        {{{1000, 1, 30}, {1026, 7, 30}, {1027, 1, 30}}},
        true,
        999,
        {{6, 7, 30}},
    },
    {
        "C4+C4",
        3,
        {{{2247, 15, 31}, {2248, 8, 9}, {2352, 16, 32}}},
        false,
        -1,
        {{-1, -1, -1}},
    },
    {
        "C5+C3",
        2,
        {{{63, 14, 27}, {792, 13, 21}, {1026, 20, 24}}},
        false,
        -1,
        {{-1, -1, -1}},
    },
    {
        "C5+C3",
        3,
        {{{139, 1, 17}, {300, 1, 17}, {381, 1, 17}}},
        true,
        58,
        {{1, 5, 17}},
    },
}};

}  // namespace exact_event_cuts
