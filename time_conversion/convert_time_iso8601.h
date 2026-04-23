#pragma once

#include <cstdint>
#include <string>
#include <vector>

// Time unit constants
constexpr std::int64_t NANOSECONDS_PER_SECOND = 1000000000LL;
constexpr std::int64_t SECONDS_PER_MINUTE = 60;
constexpr std::int64_t SECONDS_PER_HOUR = 3600;
constexpr std::int64_t SECONDS_PER_DAY = 86400;

// Gregorian calendar constants (used in posix_days_from_civil)
constexpr int MONTH_LENGTH_ENCODING = 153; // Encodes non-uniform month lengths: (153*m+2)/5
constexpr std::int64_t GREGORIAN_ERA_DAYS = 146097; // Days per 400-year Gregorian era
constexpr std::int64_t POSIX_EPOCH_DAY_OFFSET = 719468; // Days from proleptic epoch to POSIX epoch

struct LeapTransition
{
	std::int64_t transition_posix_epoch;
	int correction_seconds;
};

struct ParsedUtcIso
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

// power of 10 as a 64-bit integer
inline std::int64_t pow10_i64(std::size_t exponent)
{
	std::int64_t value = 1;
	for(std::size_t i = 0; i < exponent; ++i)
	{
		value *= 10;
	}
	return value;
}

// Convert a calendar date to the number of days since the POSIX epoch (1970-01-01).
constexpr std::int64_t posix_days_from_civil(int year, unsigned month, unsigned day) noexcept
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
	// POSIX_EPOCH_DAY_OFFSET = days from the proleptic Gregorian epoch (0000-03-01) to the
	//                        POSIX epoch (1970-01-01), used to produce a POSIX day count.
	return static_cast<std::int64_t>(era) * GREGORIAN_ERA_DAYS + static_cast<std::int64_t>(day_of_era)
		- POSIX_EPOCH_DAY_OFFSET;
}

const std::vector<LeapTransition>& get_zoneinfo_leap_transitions();

double cumulative_leap_correction(
	const std::vector<LeapTransition>& transitions,
	double utc_posix_epoch,
	bool include_transition_at_equal
);

ParsedUtcIso parse_iso8601_utc(const std::string& iso);

// UTC J2000 epoch: 2000-01-01 12:00:00 UTC
constexpr auto UTC_J2000_EPOCH_IN_POSIX_TIME =
	posix_days_from_civil(2000, 1, 1) * SECONDS_PER_DAY + 12 * SECONDS_PER_HOUR;

// TAI epoch = 2000-01-01 12:00:00 TAI = 2000-01-01 11:59:28 UTC
constexpr auto TAI_J2000_EPOCH_IN_POSIX_TIME = posix_days_from_civil(2000, 1, 1) * SECONDS_PER_DAY
	+ 11 * SECONDS_PER_HOUR + 59 * SECONDS_PER_MINUTE + 28;
