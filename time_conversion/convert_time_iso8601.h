#pragma once

#include "convert_time_common.h"

#include <cstdint>
#include <string>
#include <vector>

// Gregorian calendar constants (used in calendar_date_to_posix_days)
constexpr int MONTH_LENGTH_ENCODING = 153; // Encodes non-uniform month lengths: (153*m+2)/5
constexpr std::int64_t GREGORIAN_ERA_DAYS = 146097; // Days per 400-year Gregorian era
constexpr std::int64_t POSIX_EPOCH_DAY_OFFSET = 719468; // Days from proleptic epoch to POSIX epoch

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
constexpr std::int64_t calendar_date_to_posix_days(int year, unsigned month, unsigned day) noexcept
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

// Inverse of calendar_date_to_posix_days: converts POSIX days to calendar date.
// This implementation carefully reverses the forward algorithm.
constexpr void
posix_days_to_calendar_date(std::int64_t posix_days, int& year, unsigned& month, unsigned& day) noexcept
{
	// Add back POSIX_EPOCH_DAY_OFFSET to get days from proleptic Gregorian epoch
	std::int64_t days = posix_days + POSIX_EPOCH_DAY_OFFSET;

	// Calculate 400-year era
	std::int64_t era;
	std::int64_t day_of_era;
	if(days >= 0)
	{
		era = days / GREGORIAN_ERA_DAYS;
		day_of_era = days % GREGORIAN_ERA_DAYS;
	}
	else
	{
		// For negative days, we need careful handling of the division
		era = (days - (GREGORIAN_ERA_DAYS - 1)) / GREGORIAN_ERA_DAYS;
		day_of_era = days - era * GREGORIAN_ERA_DAYS;
	}

	// Calculate year within 400-year era
	// day_of_era ranges from 0 to 146096
	std::int64_t year_of_era = (day_of_era * 400) / GREGORIAN_ERA_DAYS;
	if(year_of_era >= 400)
	{
		year_of_era = 399;
	}

	// Calculate day within year (0-365)
	std::int64_t day_of_year = day_of_era - (year_of_era * 365 + year_of_era / 4 - year_of_era / 100);

	// Convert day_of_year to month and day using the inverse of the shifted-month formula
	// Forward: (153*m + 2)/5 where m is shifted month (0=Mar, 1=Apr, ..., 9=Dec, 10=Jan, 11=Feb)
	std::int64_t month_shifted = (5 * day_of_year + 2) / 153;

	// Map shifted month back to actual month and year
	// Shifted month 0-9 maps to months 3-12 in the same year
	// Shifted month 10-11 maps to months 1-2 in the NEXT year
	year = static_cast<int>(era * 400 + year_of_era);
	if(month_shifted < 10)
	{
		month = static_cast<unsigned>(month_shifted + 3);
	}
	else
	{
		month = static_cast<unsigned>(month_shifted - 9);
		year += 1;
	}

	// Calculate day within month (1-based)
	day = static_cast<unsigned>(day_of_year - (153 * month_shifted + 2) / 5 + 1);
}

extern ParsedUtcIso utc_iso_to_parsed_utc_iso(const std::string& utc_iso);

std::string parsed_utc_iso_to_utc_iso(
	const ParsedUtcIso& parsed_utc_iso,
	bool use_t_separator = true,
	int fractional_second_places = 9
);

inline std::string utc_iso_to_utc_iso(const std::string& iso_string)
{
	return iso_string;
}
