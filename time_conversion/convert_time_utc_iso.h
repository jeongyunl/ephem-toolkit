#pragma once

#include <chrono>

// Time unit constants
constexpr std::int64_t SECONDS_PER_MINUTE = 60;
constexpr std::int64_t SECONDS_PER_HOUR = 3600;
constexpr std::int64_t SECONDS_PER_DAY = 86400;

// Gregorian calendar constants (used in days_from_civil)
constexpr int MONTH_LENGTH_ENCODING = 153; // Encodes non-uniform month lengths: (153*m+2)/5
constexpr std::int64_t GREGORIAN_ERA_DAYS = 146097; // Days per 400-year Gregorian era
constexpr std::int64_t UNIX_EPOCH_DAY_OFFSET = 719468; // Days from proleptic epoch to Unix epoch

#ifdef HAS_CHRONO_PARSE
std::chrono::utc_time<std::chrono::nanoseconds> iso_to_utc_time(const std::string& s)
{
	// Accepts e.g. "2026-04-17T12:34:56Z" or "2026-04-17 12:34:56Z"
	// %FT%T  -> YYYY-MM-DD'T'HH:MM:SS
	// %Ez    -> ISO 8601 offset / 'Z'
	std::chrono::utc_time<std::chrono::nanoseconds> tp;

	std::istringstream in(s);

	in >> std::chrono::parse("%FT%T%Ez", tp);

	if(in.fail())
	{
		// Try a slightly more permissive variant (space instead of 'T')
		in.clear();
		in.str(s);
		in >> std::chrono::parse("%F %T%Ez", tp);
	}

	if(in.fail())
	{
		throw std::runtime_error("Failed to parse ISO-8601 UTC time: " + s);
	}

	return tp;
}
#else

struct LeapTransition
{
	std::int64_t unix_transition_seconds;
	int correction_seconds;
};

struct ParsedIsoUtc
{
	int year = 0;
	unsigned month = 0;
	unsigned day = 0;
	int hour = 0;
	int minute = 0;
	int second = 0;
	std::int64_t nanos = 0;
	int tz_offset_seconds = 0;
};

constexpr std::int64_t days_from_civil(int year, unsigned month, unsigned day) noexcept
{
	// Shift January and February to months 13 and 14 of the previous year so that
	// the leap day (Feb 29) always falls at the end of the shifted year, simplifying
	// the day-of-year calculation below.
	year -= (month <= 2 ? 1 : 0);

	// A 400-year Gregorian era contains exactly 146097 days. This gives the era index
	// and keeps subsequent offsets in the range [0, 146096].
	const int era = (year >= 0 ? year : year - 399) / 400;

	// Year within the era [0, 399].
	const unsigned year_of_era = static_cast<unsigned>(year - era * 400);

	// Day within the shifted year [0, 365].
	// The factor (153 * m + 2) / 5 encodes the non-uniform month lengths for
	// March–February layout without any branching beyond the month shift above.
	const unsigned day_of_year = (MONTH_LENGTH_ENCODING * (month + (month > 2 ? -3 : 9)) + 2) / 5 + day - 1;

	// Day within the era [0, 146096].
	// Adds one leap day per 4 years, subtracts the century non-leap years,
	// and the century-of-era correction is already embedded in year_of_era / 100.
	const unsigned day_of_era = year_of_era * 365 + year_of_era / 4 - year_of_era / 100 + day_of_year;

	// GREGORIAN_ERA_DAYS = days per 400-year era.
	// UNIX_EPOCH_DAY_OFFSET = days from the proleptic Gregorian epoch (0000-03-01) to the
	//                        Unix epoch (1970-01-01), used to produce a Unix day count.
	return static_cast<std::int64_t>(era) * GREGORIAN_ERA_DAYS + static_cast<std::int64_t>(day_of_era)
		- UNIX_EPOCH_DAY_OFFSET;
}

ParsedIsoUtc parse_iso8601_utc(const std::string& iso);

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration>
iso_utc_to_unix_seconds_non_leap(const ParsedIsoUtc& p)
{
#if 1
	// Number of days since the Unix epoch (1970-01-01) for the calendar date.
	const std::int64_t days_since_unix_epoch = days_from_civil(p.year, p.month, p.day);

	// Seconds elapsed within the day from midnight, treating leap second 60 as 59
	// for the purpose of building a Unix timestamp (POSIX ignores the leap second).
	std::int64_t seconds_within_day = static_cast<std::int64_t>(p.hour) * SECONDS_PER_HOUR
		+ static_cast<std::int64_t>(p.minute) * SECONDS_PER_MINUTE + static_cast<std::int64_t>(p.second);

	// A leap second (second == 60) does not exist in the POSIX/Unix time scale.
	// Map it to SECONDS_PER_DAY so the resulting Unix timestamp equals midnight of the next day,
	// which is the same value POSIX assigns to the next second after the leap second.
	if(p.second == 60)
	{
		seconds_within_day = SECONDS_PER_DAY;
	}

	// Convert to a Unix timestamp, applying the UTC offset so the result is always UTC.
	// Subtracting the offset converts a local/offset time to UTC: e.g. +05:30 → subtract 19800 s.
	const std::int64_t unix_seconds =
		days_since_unix_epoch * SECONDS_PER_DAY + seconds_within_day - p.tz_offset_seconds;
#else
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmissing-field-initializers"
	struct tm tm = {
		.tm_sec = (p.second == 60) ? 59 : p.second, // Map leap second to 59 for timegm
		.tm_min = p.minute, // 0-59
		.tm_hour = p.hour, // 0-23
		.tm_mday = static_cast<int>(p.day), // 1-31
		.tm_mon = static_cast<int>(p.month) - 1, // 0-11
		.tm_year = p.year - 1900, // years since 1900
	};
#pragma GCC diagnostic pop

	const time_t unix_seconds = timegm(&tm) - p.tz_offset_seconds
		+ ((p.second == 60) ? 1 : 0); // Add 1 second if it was a leap second
#endif

	// Combine the integer-second Unix timestamp with the sub-second nanosecond remainder.
	return std::chrono::sys_time<Duration>{ std::chrono::seconds{ unix_seconds }
											+ std::chrono::nanoseconds{ p.nanos } };
}

std::vector<LeapTransition> load_zoneinfo_leap_transitions(const std::string& leapseconds_path);

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration> iso_to_sys_time(const std::string& iso_string)
{
	const ParsedIsoUtc utc = parse_iso8601_utc(iso_string);
	const auto unix_tp = iso_utc_to_unix_seconds_non_leap(utc);
	return std::chrono::time_point_cast<Duration>(unix_tp);
}

#endif // HAS_CHRONO_PARSE

double utc_iso_to_utc_posix(const std::string& iso_string);
double utc_iso_to_utc_tudat(const std::string& iso_string);
double utc_iso_to_tai_tudat(const std::string& iso_string);
double utc_iso_to_tt_tudat(const std::string& iso_string);
double utc_iso_to_tdb_tudat(const std::string& iso_string);

std::string utc_iso_tudat_to_utc_iso_tudat(const std::string& iso_string);

double utc_iso_tudat_to_utc_posix(const std::string& iso_string);
double utc_iso_tudat_to_utc_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tai_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tt_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tdb_tudat(const std::string& iso_string);
