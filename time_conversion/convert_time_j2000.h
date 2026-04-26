#pragma once

#include "convert_time_epochs.h"
#include "convert_time_iso8601.h"

#include <string>

// Simple direct conversions

constexpr double posix_to_posix(const double posix_time)
{
	return posix_time;
}

constexpr double utc_j2000_to_utc_j2000(const double utc_j2000_time)
{
	return utc_j2000_time;
}

constexpr double tai_j2000_to_tai_j2000(const double tai_j2000_time)
{
	return tai_j2000_time;
}

constexpr double tt_j2000_to_tt_j2000(const double tt_j2000_time)
{
	return tt_j2000_time;
}

constexpr double tdb_j2000_to_tdb_j2000(const double tdb_j2000_time)
{
	return tdb_j2000_time;
}

constexpr double posix_to_utc_j2000(double posix_time)
{
	return posix_time - static_cast<double>(epochs::UTC_J2000_EPOCH_IN_POSIX_TIME);
}

constexpr double utc_j2000_to_posix(double utc_j2000_time)
{
	return utc_j2000_time + static_cast<double>(epochs::UTC_J2000_EPOCH_IN_POSIX_TIME);
}

constexpr double tai_j2000_to_tt_j2000(double tai_j2000_time)
{
	// TT is exactly 32.184 seconds ahead of TAI.
	return tai_j2000_time + TT_EPOCH_MINUS_TAI_EPOCH;
}

constexpr double tai_j2000_to_tdb_j2000(double tai_j2000_time)
{
	// TT is exactly 32.184 seconds ahead of TAI.
	return tai_j2000_to_tt_j2000(tai_j2000_time);
}

constexpr double tt_j2000_to_tai_j2000(double tt_j2000_time)
{
	// TT is exactly 32.184 seconds ahead of TAI.
	return tt_j2000_time - TT_EPOCH_MINUS_TAI_EPOCH;
}

//
// ParsedUtcIso Time to X
//

// Direct conversions

double parsed_utc_iso_to_posix(const ParsedUtcIso& parsed_utc_iso);
double parsed_utc_iso_to_tai_j2000(const ParsedUtcIso& parsed_utc_iso);

// Indirect conversions

inline double parsed_utc_iso_to_utc_j2000(const ParsedUtcIso& parsed_utc_iso)
{
	const double posix_time = parsed_utc_iso_to_posix(parsed_utc_iso);
	return posix_to_utc_j2000(posix_time);
}

inline double parsed_utc_iso_to_tt_j2000(const ParsedUtcIso& parsed_utc_iso)
{
	const double tai_j2000_time = parsed_utc_iso_to_tai_j2000(parsed_utc_iso);
	return tai_j2000_to_tt_j2000(tai_j2000_time);
}

//
// ISO-8601 Time to X
//

// Indirect conversions

inline double utc_iso_to_posix(const std::string& iso_string)
{
	const ParsedUtcIso parsed_utc_iso = utc_iso_to_parsed_utc_iso(iso_string);
	return parsed_utc_iso_to_posix(parsed_utc_iso);
}

inline double utc_iso_to_utc_j2000(const std::string& iso_string)
{
	const double posix_time = utc_iso_to_posix(iso_string);
	return posix_to_utc_j2000(posix_time);
}

inline double utc_iso_to_tai_j2000(const std::string& iso_string)
{
	const ParsedUtcIso parsed_utc_iso = utc_iso_to_parsed_utc_iso(iso_string);
	return parsed_utc_iso_to_tai_j2000(parsed_utc_iso);
}

inline double utc_iso_to_tt_j2000(const std::string& iso_string)
{
	const double tai_j2000_time = utc_iso_to_tai_j2000(iso_string);
	return tai_j2000_to_tt_j2000(tai_j2000_time);
}

inline double utc_iso_to_tdb_j2000(const std::string& iso_string)
{
	const double tai_j2000_time = utc_iso_to_tai_j2000(iso_string);
	return tai_j2000_to_tdb_j2000(tai_j2000_time);
}

//
// POSIX Time to X
//

// Direct conversions

ParsedUtcIso posix_to_parsed_utc_iso(double posix_time);
double posix_to_tai_j2000(double posix_time);

// Indirect conversions

inline std::string posix_to_utc_iso(double posix_time)
{
	const ParsedUtcIso parsed_utc_iso = posix_to_parsed_utc_iso(posix_time);
	return parsed_utc_iso_to_utc_iso(parsed_utc_iso);
}

inline double posix_to_tt_j2000(double posix_time)
{
	const double tai_j2000_time = posix_to_tai_j2000(posix_time);
	return tai_j2000_to_tt_j2000(tai_j2000_time);
}

inline double posix_to_tdb_j2000(double posix_time)
{
	return posix_to_tt_j2000(posix_time);
}

//
// UTC J2000 Time to X
//

// Indirect conversions

inline ParsedUtcIso utc_j2000_to_parsed_utc_iso(double utc_j2000_time)
{
	const double posix_time = utc_j2000_to_posix(utc_j2000_time);
	return posix_to_parsed_utc_iso(posix_time);
}

inline std::string utc_j2000_to_utc_iso(double utc_j2000_time)
{
	const ParsedUtcIso parsed_utc_iso = utc_j2000_to_parsed_utc_iso(utc_j2000_time);
	return parsed_utc_iso_to_utc_iso(parsed_utc_iso);
}

inline double utc_j2000_to_tai_j2000(double utc_j2000_time)
{
	const double posix_time = utc_j2000_to_posix(utc_j2000_time);
	return posix_to_tai_j2000(posix_time);
}

inline double utc_j2000_to_tt_j2000(double utc_j2000_time)
{
	const double tai_j2000_time = utc_j2000_to_tai_j2000(utc_j2000_time);
	return tai_j2000_to_tt_j2000(tai_j2000_time);
}

inline double utc_j2000_to_tdb_j2000(double utc_j2000_time)
{
	return utc_j2000_to_tt_j2000(utc_j2000_time);
}

//
// TAI J2000 Time to X
//

// Direct conversions

ParsedUtcIso tai_j2000_to_parsed_utc_iso(double tai_j2000_time);
double tai_j2000_to_posix(double tai_j2000_time);

// Indirect conversions

inline std::string tai_j2000_to_utc_iso(double tai_j2000_time)
{
	const ParsedUtcIso parsed_utc_iso = tai_j2000_to_parsed_utc_iso(tai_j2000_time);
	return parsed_utc_iso_to_utc_iso(parsed_utc_iso);
}

inline double tai_j2000_to_utc_j2000(double tai_j2000_time)
{
	const double posix_time = tai_j2000_to_posix(tai_j2000_time);
	return posix_to_utc_j2000(posix_time);
}

//
// TT J2000 Time to X
//

// Indirect conversions

inline ParsedUtcIso tt_j2000_to_parsed_utc_iso(double tt_j2000_time)
{
	const double tai_j2000_time = tt_j2000_to_tai_j2000(tt_j2000_time);
	return tai_j2000_to_parsed_utc_iso(tai_j2000_time);
}

inline std::string tt_j2000_to_utc_iso(double tt_j2000_time)
{
	const double tai_j2000_time = tt_j2000_to_tai_j2000(tt_j2000_time);
	const ParsedUtcIso parsed_utc_iso = tai_j2000_to_parsed_utc_iso(tai_j2000_time);
	return parsed_utc_iso_to_utc_iso(parsed_utc_iso);
}

inline double tt_j2000_to_posix(double tt_j2000_time)
{
	const double tai_j2000_time = tt_j2000_to_tai_j2000(tt_j2000_time);
	return tai_j2000_to_posix(tai_j2000_time);
}

inline double tt_j2000_to_utc_j2000(double tt_j2000_time)
{
	const double posix_time = tt_j2000_to_posix(tt_j2000_time);
	return posix_to_utc_j2000(posix_time);
}

inline double tt_j2000_to_tdb_j2000(double tt_j2000_time)
{
	return tt_j2000_time;
}

//
// TDB J2000 Time to X
//

inline std::string tdb_j2000_to_utc_iso(double tdb_j2000_time)
{
	return tt_j2000_to_utc_iso(tdb_j2000_time);
}

inline double tdb_j2000_to_posix(double tdb_j2000_time)
{
	return tt_j2000_to_posix(tdb_j2000_time);
}

inline double tdb_j2000_to_utc_j2000(double tdb_j2000_time)
{
	return tt_j2000_to_utc_j2000(tdb_j2000_time);
}

inline double tdb_j2000_to_tai_j2000(double tdb_j2000_time)
{
	return tt_j2000_to_tai_j2000(tdb_j2000_time);
}

inline double tdb_j2000_to_tt_j2000(double tdb_j2000_time)
{
	return tdb_j2000_time;
}

//
// Utility for testing
//

// Compares two ISO-8601 timestamps after parsing, allowing either 'T' or space between date/time.
// Fractional seconds are compared at the requested precision (0-9 decimal places) by truncation.
bool iso_8601_equal(const std::string& lhs, const std::string& rhs, std::size_t fractional_second_places = 3);
