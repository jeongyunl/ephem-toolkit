#pragma once

#include <chrono>

// Time unit constants
constexpr std::int64_t NANOSECONDS_PER_SECOND = 1000000000LL;
constexpr std::int64_t SECONDS_PER_MINUTE = 60;
constexpr std::int64_t SECONDS_PER_HOUR = 3600;
constexpr std::int64_t SECONDS_PER_DAY = 86400;

// the TAI realization of TT is defined as: TT = TAI + 32.184 seconds
// See https://en.wikipedia.org/wiki/Terrestrial_Time
constexpr auto TT_MINUS_TAI = 32.184;

// Historical TAI-UTC offset constants (pre-1972 UTC scale)
constexpr double TAI_MINUS_UTC_AT_1970 = 8.000082; // TAI-UTC at 1970-01-01 00:00:00 UTC (s)
constexpr double UTC_DRIFT_RATE_PRE_1972 = 0.002592; // Linear drift rate before 1972 (s/day)
constexpr double TAI_MINUS_UTC_AT_1972 = 10.0; // TAI-UTC at 1972-01-01 (s)
constexpr double TAI_MINUS_UTC_AT_J2000 = 32.0; // TAI-UTC at J2000 epoch (s)

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

#include <string>
#include <variant>

enum class TimeFormat
{
	UNKNOWN = -1,
	UTC_ISO8601 = 0, // ISO 8601 format in UTC: "YYYY-MM-DDTHH:MM:SS.sss"
	POSIX, // POSIX timestamp; in seconds since 1970-01-01 00:00:00 UTC
	UTC_J2000, // Time in UTC; in seconds since UTC J2000 epoch (2000-01-01 12:00:00.000 UTC)
	TAI_J2000, // Time in TAI; in seconds since TAI J2000 epoch (2000-01-01 12:00:00.000 TAI =
			   // 2000-01-01 11:59:28 UTC)
	TT_J2000, // Terrestial Time; in seconds since TT J2000 epoch (2000-01-01 12:00:00.000 TT =
			  // 2000-01-01 11:58:55.816 UTC)
	TDB_J2000, // Barycentric Dynamical Time; in seconds since TDB J2000 epoch (2000-01-01
			   // 12:00:00.000 TDB ≈ 2000-01-01 11:58:55.816 UTC)
	CHRONO_SYS_TIME_ISO, // ISO 8601 format in chrono::sys_time
	CHRONO_SYS_TIME, // Seconds since chrono::sys_time epoch. Ignores leap seconds (1970-01-01 00:00:00 UTC)
#ifdef HAS_CHRONO_UTC_CLOCK
	CHRONO_UTC_TIME_ISO, // ISO 8601 format in chrono::utc_time
	CHRONO_UTC_TIME, // Seconds since chrono::utc_time epoch. Includes leap seconds (1970-01-01 00:00:00 UTC)
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	CHRONO_TAI_TIME_ISO, // ISO 8601 format in chrono::tai_time
	CHRONO_TAI_TIME, // Seconds since chrono::tai_time epoch. (1958-01-01 00:00:00 TAI, or 1957-12-31 23:59:50
					 // UTC)
#endif
};

typedef std::variant<
	std::string,
	double,
	std::chrono::system_clock::time_point
#ifdef HAS_CHRONO_UTC_CLOCK
	,
	std::chrono::utc_clock::time_point
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	,
	std::chrono::tai_clock::time_point
#endif
	>
	TimeValue;
