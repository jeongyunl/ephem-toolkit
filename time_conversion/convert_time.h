#pragma once

#include "convert_time_common.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include <time.h>

// Time unit constants
constexpr std::int64_t SECONDS_PER_MINUTE = 60;
constexpr std::int64_t SECONDS_PER_HOUR = 3600;
constexpr std::int64_t SECONDS_PER_DAY = 86400;

// Gregorian calendar constants (used in days_from_civil)
constexpr int MONTH_LENGTH_ENCODING = 153; // Encodes non-uniform month lengths: (153*m+2)/5
constexpr std::int64_t GREGORIAN_ERA_DAYS = 146097; // Days per 400-year Gregorian era
constexpr std::int64_t UNIX_EPOCH_DAY_OFFSET = 719468; // Days from proleptic epoch to Unix epoch

// Historical TAI-UTC offset constants (pre-1972 UTC scale)
constexpr double PRE_1972_TAI_MINUS_UTC_AT_1970 = 8.000082; // TAI-UTC at 1970-01-01 00:00:00 UTC (s)
constexpr double PRE_1972_DRIFT_RATE = 0.002592; // Linear drift rate before 1972 (s/day)
constexpr double POST_1972_TAI_MINUS_UTC = 10.0; // TAI-UTC from 1972-01-01 onwards (s)

//
// std::chrono::time_point to time_t conversion helpers
//

// duration_cast-based system_clock to time_t conversion helper
template <typename Duration = std::chrono::system_clock::duration>
time_t sys_time_to_time_t_dc(std::chrono::time_point<std::chrono::system_clock, Duration> tp)
{
	return std::chrono::duration_cast<std::chrono::seconds>(tp.time_since_epoch()).count();
}

// duration_cast-based system_clock to floating-point POSIX time conversion helper
template <typename Rep = double, typename Period = std::ratio<1>>
double sys_time_to_posix(std::chrono::time_point<std::chrono::system_clock> tp)
{
	return std::chrono::duration_cast<std::chrono::duration<Rep, Period>>(tp.time_since_epoch()).count();
}

// system_clock::to_time_t()-based system_clock to time_t conversion helper
template <typename Duration = std::chrono::system_clock::duration>
time_t sys_time_to_time_t_std(std::chrono::time_point<std::chrono::system_clock, Duration> tp)
{
	return std::chrono::system_clock::to_time_t(
		std::chrono::time_point_cast<std::chrono::system_clock::duration>(tp)
	);
}

#include "convert_time_utc_iso.h"

std::string utc_posix_to_utc_iso_tudat(double utc_posix_epoch);
double utc_posix_to_utc_posix(double utc_posix_epoch);
double utc_posix_to_utc_tudat(double utc_posix_epoch);
double utc_posix_to_tai_tudat(double utc_posix_epoch);
double utc_posix_to_tt_tudat(double utc_posix_epoch);
double utc_posix_to_tdb_tudat(double utc_posix_epoch);
double utc_posix_to_tdb_apx_tudat(double utc_posix_epoch);

std::string utc_tudat_to_utc_iso_tudat(double utc_tudat_epoch);
double utc_tudat_to_utc_posix(double utc_tudat_epoch);
double utc_tudat_to_utc_tudat(double utc_tudat_epoch);
double utc_tudat_to_tai_tudat(double utc_tudat_epoch);
double utc_tudat_to_tt_tudat(double utc_tudat_epoch);
double utc_tudat_to_tdb_tudat(double utc_tudat_epoch);
double utc_tudat_to_tdb_apx_tudat(double utc_tudat_epoch);

std::string tai_tudat_to_utc_iso_tudat(double tai_tudat_epoch);
double tai_tudat_to_utc_posix(double tai_tudat_epoch);
double tai_tudat_to_utc_tudat(double tai_tudat_epoch);
double tai_tudat_to_tai_tudat(double tai_tudat_epoch);
double tai_tudat_to_tt_tudat(double tai_tudat_epoch);
double tai_tudat_to_tdb_tudat(double tai_tudat_epoch);
double tai_tudat_to_tdb_apx_tudat(double tai_tudat_epoch);

std::string tt_tudat_to_utc_iso_tudat(double tt_tudat_epoch);
double tt_tudat_to_utc_posix(double tt_tudat_epoch);
double tt_tudat_to_utc_tudat(double tt_tudat_epoch);
double tt_tudat_to_tai_tudat(double tt_tudat_epoch);
double tt_tudat_to_tt_tudat(double tt_tudat_epoch);
double tt_tudat_to_tdb_tudat(double tt_tudat_epoch);
double tt_tudat_to_tdb_apx_tudat(double tt_tudat_epoch);

std::string tdb_tudat_to_utc_iso_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_utc_posix(double tdb_tudat_epoch);
double tdb_tudat_to_utc_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_tai_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_tt_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_tdb_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_tdb_apx_tudat(double tdb_tudat_epoch);

std::string tdb_apx_tudat_to_utc_iso_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_utc_posix(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_utc_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tai_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tt_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tdb_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tdb_apx_tudat(double tdb_apx_tudat_epoch);

enum class TimeFormat
{
	UNKNOWN = -1,
	UTC_ISO_TUDAT = 0, // ISO 8601 format in UTC: "YYYY-MM-DDTHH:MM:SS.sss"
	UTC_POSIX, // POSIX timestamp; in seconds since 1970-01-01 00:00:00 UTC
	UTC_TUDAT, // Time in UTC; in seconds since UTC J2000 epoch (2000-01-01 12:00:00.000 UTC)
	TAI_TUDAT, // Time in TAI; in seconds since TAI J2000 epoch (2000-01-01 12:00:00.000 TAI =
			   // 2000-01-01 11:59:28 UTC)
	TT_TUDAT, // Terrestial Time; in seconds since TT J2000 epoch (2000-01-01 12:00:00.000 TT =
			  // 2000-01-01 11:58:55.816 UTC)
	TDB_TUDAT, // Barycentric Dynamical Time; in seconds since TDB J2000 epoch (2000-01-01
			   // 12:00:00.000 TDB ≈ 2000-01-01 11:58:55.816 UTC)
	TDB_APX_TUDAT, // Approximate TDB J2000 epoch
};
