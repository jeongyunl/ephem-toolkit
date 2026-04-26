
#include "convert_time_j2000.h"

#include "convert_time_iso8601.h"
#include "convert_time_leap_transition.h"

#include <cmath>
#include <cstdint>

static inline std::int64_t extract_nanoseconds(double fractional_seconds) noexcept
{
	std::int64_t nanos = static_cast<std::int64_t>(std::llround(fractional_seconds * 1.0e9));
	if(nanos >= NANOSECONDS_PER_SECOND)
	{
		nanos = NANOSECONDS_PER_SECOND - 1;
	}
	if(nanos < 0)
	{
		nanos = 0;
	}
	return nanos;
}

//
// POSIX
//

double parsed_utc_iso_to_posix(const ParsedUtcIso& parsed_utc_iso)
{
	// Compute POSIX-like seconds since 1970-01-01 for the UTC instant.
	// Leap second 23:59:60 is mapped to the POSIX second of the following 00:00:00.
	std::int64_t seconds_within_day = static_cast<std::int64_t>(parsed_utc_iso.hour) * SECONDS_PER_HOUR
		+ static_cast<std::int64_t>(parsed_utc_iso.minute) * SECONDS_PER_MINUTE
		+ static_cast<std::int64_t>((parsed_utc_iso.second == 60) ? 59 : parsed_utc_iso.second);

	std::int64_t posix_seconds =
		calendar_date_to_posix_days(parsed_utc_iso.year, parsed_utc_iso.month, parsed_utc_iso.day)
			* SECONDS_PER_DAY
		+ seconds_within_day - static_cast<std::int64_t>(parsed_utc_iso.tz_offset_seconds);

	if(parsed_utc_iso.second == 60)
	{
		posix_seconds += 1;
	}

	const double posix_time =
		static_cast<double>(posix_seconds) + static_cast<double>(parsed_utc_iso.nanos) * 1.0e-9;

	return posix_time;
}

ParsedUtcIso posix_to_parsed_utc_iso(double posix_time)
{
	ParsedUtcIso result;

	const double floored_posix_time = std::floor(posix_time);
	std::int64_t posix_seconds = static_cast<std::int64_t>(floored_posix_time);
	result.nanos = extract_nanoseconds(posix_time - floored_posix_time);

	std::int64_t posix_days = posix_seconds / SECONDS_PER_DAY;
	std::int64_t seconds_within_day = posix_seconds % SECONDS_PER_DAY;

	if(seconds_within_day < 0)
	{
		posix_days -= 1;
		seconds_within_day += SECONDS_PER_DAY;
	}

	posix_days_to_calendar_date(posix_days, result.year, result.month, result.day);

	result.hour = static_cast<int>(seconds_within_day / SECONDS_PER_HOUR);
	seconds_within_day %= SECONDS_PER_HOUR;
	result.minute = static_cast<int>(seconds_within_day / SECONDS_PER_MINUTE);
	result.second = static_cast<int>(seconds_within_day % SECONDS_PER_MINUTE);
	result.tz_offset_seconds = 0;

	return result;
}

double posix_to_tai_j2000(double posix_time)
{
#if 0
	ParsedUtcIso parsed = posix_to_parsed_utc_iso(posix_time);
	return parsed_utc_iso_to_tai_j2000(parsed);
#else
	const auto& transitions = get_zoneinfo_leap_transitions();

	// Get cumulative leap correction (TAI - UTC) at the input POSIX time
	const double leap_now = cumulative_leap_correction(transitions, posix_time, true);

	// Calculate elapsed UTC seconds (non-leap) from J2000 epoch to input POSIX time
	const double utc_elapsed_non_leap = posix_time - static_cast<double>(TAI_J2000_EPOCH_IN_POSIX_TIME);

	// Calculate the difference in leap corrections between now and epoch
	const double leap_delta = leap_now - J2000_TAI_MINUS_UTC;

	// TAI J2000 = UTC elapsed + leap correction difference
	return utc_elapsed_non_leap + leap_delta;
#endif
}

//
// TAI J2000
//

// construct a 23:59:60 representation with fractional offset within the leap second
static ParsedUtcIso
posix_leap_second_transition_to_parsed_utc_iso(double transition_posix_time, double fractional_second)
{
	ParsedUtcIso result;

	const std::int64_t transition_days = static_cast<std::int64_t>(transition_posix_time) / SECONDS_PER_DAY;

	posix_days_to_calendar_date(transition_days - 1, result.year, result.month, result.day);

	result.hour = 23;
	result.minute = 59;
	result.second = 60;
	result.nanos = extract_nanoseconds(fractional_second);
	result.tz_offset_seconds = 0;
	return result;
}

double parsed_utc_iso_to_tai_j2000(const ParsedUtcIso& parsed_utc_iso)
{
	const auto& transitions = get_zoneinfo_leap_transitions();

	// POSIX-like seconds since 1970-01-01 for the UTC instant.
	std::int64_t seconds_within_day = static_cast<std::int64_t>(parsed_utc_iso.hour) * SECONDS_PER_HOUR
		+ static_cast<std::int64_t>(parsed_utc_iso.minute) * SECONDS_PER_MINUTE
		+ static_cast<std::int64_t>((parsed_utc_iso.second == 60) ? 59 : parsed_utc_iso.second);

	std::int64_t posix_seconds =
		calendar_date_to_posix_days(parsed_utc_iso.year, parsed_utc_iso.month, parsed_utc_iso.day)
			* SECONDS_PER_DAY
		+ seconds_within_day - static_cast<std::int64_t>(parsed_utc_iso.tz_offset_seconds);

	if(parsed_utc_iso.second == 60)
	{
		posix_seconds += 1;
	}

	const double posix_time =
		static_cast<double>(posix_seconds) + static_cast<double>(parsed_utc_iso.nanos) * 1.0e-9;

	// At 23:59:60, UTC maps to the same POSIX second as 00:00:00 next day.
	// For correct boundary behavior, that leap transition must not be counted yet.
	const bool include_transition_now = (parsed_utc_iso.second != 60);
	const double posix_time_for_leap_lookup =
		(parsed_utc_iso.second == 60) ? static_cast<double>(posix_seconds) : posix_time;

	const double leap_now =
		cumulative_leap_correction(transitions, posix_time_for_leap_lookup, include_transition_now);

	const double utc_elapsed_non_leap = posix_time - static_cast<double>(TAI_J2000_EPOCH_IN_POSIX_TIME);
	const double leap_delta = leap_now - J2000_TAI_MINUS_UTC;

	return utc_elapsed_non_leap + leap_delta;
}

ParsedUtcIso tai_j2000_to_parsed_utc_iso(double tai_j2000_time)
{
	// Largest historical UTC-TAI offset is well below this; keep a safe search margin.
	constexpr double BINARY_SEARCH_LOWER_MARGIN_SECONDS = 64.0;
	// UTC is never ahead of TAI, but a small positive margin keeps the upper bracket robust.
	constexpr double BINARY_SEARCH_UPPER_MARGIN_SECONDS = 1.0;
	// Stop once the UTC bracket is well below nanosecond scale.
	constexpr double BINARY_SEARCH_TOLERANCE_SECONDS = 1.0e-12;
	// 2^-32 gives sub-nanosecond-level interval shrinkage for doubles in this range.
	constexpr int BINARY_SEARCH_ITERATIONS = 32;

	// Get the table of leap-second transitions (each with TAI-UTC offset in seconds)
	const auto& transitions = get_zoneinfo_leap_transitions();

	// Convert input TAI J2000 to TAI POSIX epoch (seconds since 1970-01-01 00:00:00 in TAI)
	// = J2000 offset + TAI J2000 epoch in POSIX + accumulated leap corrections at epoch
	const double tai_j2000_time_in_posix_time =
		tai_j2000_time + static_cast<double>(TAI_J2000_EPOCH_IN_POSIX_TIME) + J2000_TAI_MINUS_UTC;

	// PHASE 1: Check if tai_j2000_time_in_posix_time falls within a leap-second interval (23:59:60)
	// A leap second occupies exactly 1 second in TAI immediately before the UTC transition
	for(const LeapTransition& transition : transitions)
	{
		// Skip non-leap transitions (only positive corrections represent leap insertions)
		if(transition.correction_seconds <= 0)
		{
			continue;
		}

		// This transition marks the boundary where UTC jumps (e.g., 23:59:59 → 00:00:00 next day)
		const double transition_posix_time = static_cast<double>(transition.transition_posix_time);

		// Leap correction just before this transition (does not include this leap second itself)
		const double leap_before = cumulative_leap_correction(transitions, transition_posix_time, false);

		// In TAI, the leap-second interval spans [transition + leap_before, transition + leap_before + 1)
		// This maps to UTC 23:59:60 (and fractional seconds within that interval)
		const double leap_second_tai_start = transition_posix_time + leap_before;
		// Leap-second duration is exactly 1 SI second.
		const double leap_second_tai_end = leap_second_tai_start + 1.0;

		// Check if our input instant falls within this leap-second interval
		if(tai_j2000_time_in_posix_time >= leap_second_tai_start
		   && tai_j2000_time_in_posix_time < leap_second_tai_end)
		{
			// Yes: construct a 23:59:60 representation with fractional offset within the leap second
			return posix_leap_second_transition_to_parsed_utc_iso(
				transition_posix_time,
				tai_j2000_time_in_posix_time - leap_second_tai_start // Fractional position within leap second
			);
		}
	}

	// PHASE 2: TAI instant is not in a leap-second interval; use binary search to find UTC POSIX epoch
	// Initial bounds: Presumably, TAI can differ from UTC by at most ~64 seconds
	// We search for the UTC POSIX instant whose corresponding TAI value equals our input
	double lower = tai_j2000_time_in_posix_time - BINARY_SEARCH_LOWER_MARGIN_SECONDS;
	double upper = tai_j2000_time_in_posix_time + BINARY_SEARCH_UPPER_MARGIN_SECONDS;

	// Binary search converges in ~32 iterations for the known leap-second table size
	for(int iteration = 0; iteration < BINARY_SEARCH_ITERATIONS; ++iteration)
	{
		if((upper - lower) <= BINARY_SEARCH_TOLERANCE_SECONDS)
		{
			break;
		}

		// Evaluate midpoint: convert this UTC POSIX candidate to TAI
		const double midpoint = 0.5 * (lower + upper);
		if(midpoint == lower || midpoint == upper)
		{
			break;
		}

		const double midpoint_tai = midpoint + cumulative_leap_correction(transitions, midpoint, true);

		// Adjust search interval based on whether midpoint's TAI is too small or too large
		if(midpoint_tai < tai_j2000_time_in_posix_time)
		{
			lower = midpoint; // Move search interval up
		}
		else
		{
			upper = midpoint; // Move search interval down
		}
	}

	// After 32 iterations, upper converges to the correct UTC POSIX instant (within floating-point precision)
	// Convert the UTC POSIX instant to calendar representation
	return posix_to_parsed_utc_iso(upper);
}

double tai_j2000_to_posix(double tai_j2000_time)
{
	const ParsedUtcIso parsed_utc_iso = tai_j2000_to_parsed_utc_iso(tai_j2000_time);
	return parsed_utc_iso_to_posix(parsed_utc_iso);
}

//
// Utility for testing
//

bool iso_8601_equal(const std::string& lhs, const std::string& rhs, std::size_t fractional_second_places)
{
	if(fractional_second_places > 9)
	{
		return false;
	}

	try
	{
		// Compare instants in a continuous time scale (TAI) so leap seconds are handled naturally.
		const double lhs_tai = utc_iso_to_tai_j2000(lhs);
		const double rhs_tai = utc_iso_to_tai_j2000(rhs);

		// Convert to integer nanoseconds.
		const auto lhs_ns = static_cast<std::int64_t>(lhs_tai * 1.0e9);
		const auto rhs_ns = static_cast<std::int64_t>(rhs_tai * 1.0e9);

		// Truncate to the requested fractional-second precision.
		const std::int64_t ns_resolution = NANOSECONDS_PER_SECOND / pow10_i64(fractional_second_places);
		const std::int64_t lhs_trunc = (lhs_ns / ns_resolution) * ns_resolution;
		const std::int64_t rhs_trunc = (rhs_ns / ns_resolution) * ns_resolution;

		return lhs_trunc == rhs_trunc;
	}
	catch(const std::exception&)
	{
		return false;
	}
}
