#pragma once

#include "convert_time.h"

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

#include <chrono>

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

TimeValue convert_time(const TimeValue& input, TimeFormat input_format, TimeFormat output_format);
