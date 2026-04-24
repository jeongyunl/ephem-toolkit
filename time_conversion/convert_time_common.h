#pragma once

#include <chrono>

// Time unit constants
constexpr std::int64_t NANOSECONDS_PER_SECOND = 1000000000LL;
constexpr std::int64_t SECONDS_PER_MINUTE = 60;
constexpr std::int64_t SECONDS_PER_HOUR = 3600;
constexpr std::int64_t SECONDS_PER_DAY = 86400;

// POSIX epoch (1970-01-01 00:00:00 UTC) minus UTC J2000 epoch (2000-01-01 12:00:00 UTC)
constexpr auto POSIX_EPOCH_MINUS_UTC_J200_EPOCH = 946728000.0;

// the TAI realization of TT is defined as: TT = TAI + 32.184 seconds
// See https://en.wikipedia.org/wiki/Terrestrial_Time
constexpr auto TT_EPOCH_MINUS_TAI_EPOCH = 32.184;

// Historical TAI-UTC offset constants (pre-1972 UTC scale)
constexpr double PRE_1972_TAI_MINUS_UTC_AT_1970 = 8.000082; // TAI-UTC at 1970-01-01 00:00:00 UTC (s)
constexpr double PRE_1972_DRIFT_RATE = 0.002592; // Linear drift rate before 1972 (s/day)
constexpr double POST_1972_TAI_MINUS_UTC = 10.0; // TAI-UTC from 1972-01-01 onwards (s)
constexpr double J2000_TAI_MINUS_UTC = 32.0; // TAI-UTC at J2000 epoch (s)

// If C++20 or later
#if __cplusplus >= 202002L

#ifdef _GLIBCXX_RELEASE
// If we are using GNU C++ library

// std::chrono::utc_clock was added in GNU C++ library version 13 (not fully functional until version 14)
#if _GLIBCXX_RELEASE >= 13
#define HAS_CHRONO_UTC_CLOCK
#define HAS_CHRONO_TAI_CLOCK
#endif

#elif defined(_LIBCPP_STD_VER)
// If we are using LLVM libc++?

#if _LIBCPP_STD_VER >= 20 && _LIBCPP_HAS_TIME_ZONE_DATABASE
#define HAS_CHRONO_UTC_CLOCK
#define HAS_CHRONO_TAI_CLOCK
#endif

#endif

#endif

#ifdef _LIBCPP_STD_VER
#include <tzfile.h>
#endif

#ifdef TZDIR
// System tzdata directory is available at compile time.
#define ZONEINFO_DIR TZDIR
#elif defined(_GLIBCXX_ZONEINFO_DIR)
// GNU libstdc++ provides a compile-time macro for the tzdata directory.
#define ZONEINFO_DIR _GLIBCXX_ZONEINFO_DIR
#else
// Fallback default path (may not exist on all systems)
#define ZONEINFO_DIR "/usr/share/zoneinfo"
#endif

#define LEAPSECONDS_PATH_DEFAULT ZONEINFO_DIR "/leapseconds"

// FIXME Currently Tudat's TDB to UTC conversions fail for the second after end-of-June leap second
// insertions.
#define TUDAT_BUGGY_TDB_TO_UTC_CONVERSIONS
