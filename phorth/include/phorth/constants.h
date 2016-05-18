#pragma once
#include <cstddef>

constexpr std::size_t IMMEDIATE_MODE = 0;
constexpr std::size_t HERE  = 1;
constexpr std::size_t LATEST = 2;
constexpr std::size_t CSTACK = 3;
constexpr std::size_t STACK_SIZE = 4;
constexpr std::size_t LITERALS = 5;
constexpr std::size_t TMP = 6;
constexpr std::size_t EXPECTED_NLOCALS = 7;
