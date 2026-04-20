#pragma once

#include <tudat/astro/earth_orientation/terrestrialTimeScaleConverter.h>
#include <chrono>

// POSIX epoch (1970-01-01 00:00:00 UTC) minus TUDAT UTC J2000 epoch (2000-01-01 12:00:00 UTC)
constexpr auto POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH = 946728000.0;

// the TAI realization of TT is defined as: TT = TAI + 32.184 seconds
// See https://en.wikipedia.org/wiki/Terrestrial_Time
constexpr auto TT_EPOCH_MINUS_TAI_EPOCH = 32.184;

// If C++20 or later
#if __cplusplus >= 202002L

#ifdef _GLIBCXX_RELEASE
// If we are using GNU C++ library

// std::chrono::utc_clock was added in GNU C++ library version 13 (not fully functional until version 14)
#if _GLIBCXX_RELEASE >= 13
#define HAS_CHRONO_UTC_CLOCK
#endif

// std::chrono::parse was added in GNU C++ library version 14
#if _GLIBCXX_RELEASE >= 14
#define HAS_CHRONO_PARSE
#endif

#elif defined(_LIBCPP_STD_VER)
// If we are using LLVM libc++?

#if _LIBCPP_STD_VER >= 20 && _LIBCPP_HAS_TIME_ZONE_DATABASE
#define HAS_CHRONO_UTC_CLOCK
#define HAS_CHRONO_PARSE
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

std::shared_ptr<tudat::earth_orientation::TerrestrialTimeScaleConverter> get_tudat_time_scale_converter();
