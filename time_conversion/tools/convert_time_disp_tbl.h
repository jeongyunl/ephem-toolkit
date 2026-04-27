#pragma once

#include "convert_time.h"

#include <variant>

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

typedef std::variant<std::string, double> TimeValue;

std::variant<std::string, double> convert_time(
	const std::variant<std::string, double>& input,
	TimeFormat input_format,
	TimeFormat output_format
);
