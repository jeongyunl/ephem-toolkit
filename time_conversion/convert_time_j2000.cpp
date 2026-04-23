
#include "convert_time_j2000.h"

#include "convert_time_iso8601.h"
#include "convert_time_utc_iso.h"

#include <cstdint>

double parsed_utc_iso_to_utc_j2000(const ParsedUtcIso& parsed_utc_iso)
{
	const auto& transitions = get_zoneinfo_leap_transitions();

	// Compute POSIX-like seconds since 1970-01-01 for the UTC instant.
	// Leap second 23:59:60 is mapped to the POSIX second of the following 00:00:00.
	std::int64_t seconds_within_day = static_cast<std::int64_t>(parsed_utc_iso.hour) * SECONDS_PER_HOUR
		+ static_cast<std::int64_t>(parsed_utc_iso.minute) * SECONDS_PER_MINUTE
		+ static_cast<std::int64_t>((parsed_utc_iso.second == 60) ? 59 : parsed_utc_iso.second);

	std::int64_t posix_seconds =
		posix_days_from_civil(parsed_utc_iso.year, parsed_utc_iso.month, parsed_utc_iso.day) * SECONDS_PER_DAY
		+ seconds_within_day - static_cast<std::int64_t>(parsed_utc_iso.tz_offset_seconds);

	if(parsed_utc_iso.second == 60)
	{
		posix_seconds += 1;
	}

	const double posix_epoch =
		static_cast<double>(posix_seconds) + static_cast<double>(parsed_utc_iso.nanos) * 1.0e-9;

	// At 23:59:60, UTC maps to the same POSIX second as 00:00:00 next day.
	// For correct boundary behavior, that leap transition must not be counted yet.
	const bool include_transition_now = (parsed_utc_iso.second != 60);
	const double posix_epoch_for_leap_lookup =
		(parsed_utc_iso.second == 60) ? static_cast<double>(posix_seconds) : posix_epoch;

	const double leap_now =
		cumulative_leap_correction(transitions, posix_epoch_for_leap_lookup, include_transition_now);
	const double leap_epoch =
		cumulative_leap_correction(transitions, static_cast<double>(utc_j2000_epoch_in_posix_time), true);

	const double utc_elapsed_non_leap = posix_epoch - static_cast<double>(utc_j2000_epoch_in_posix_time);
	const double leap_delta = leap_now - leap_epoch;

	return utc_elapsed_non_leap + leap_delta;
}

double utc_iso_to_utc_j2000(const std::string& iso_string)
{
	ParsedUtcIso parsed_utc_iso = parse_iso8601_utc(iso_string);
	return parsed_utc_iso_to_utc_j2000(parsed_utc_iso);
}

double parsed_utc_iso_to_tai_j2000(const ParsedUtcIso& parsed_utc_iso)
{
	const auto& transitions = get_zoneinfo_leap_transitions();

	// POSIX-like seconds since 1970-01-01 for the UTC instant.
	std::int64_t seconds_within_day = static_cast<std::int64_t>(parsed_utc_iso.hour) * SECONDS_PER_HOUR
		+ static_cast<std::int64_t>(parsed_utc_iso.minute) * SECONDS_PER_MINUTE
		+ static_cast<std::int64_t>((parsed_utc_iso.second == 60) ? 59 : parsed_utc_iso.second);

	std::int64_t posix_seconds =
		posix_days_from_civil(parsed_utc_iso.year, parsed_utc_iso.month, parsed_utc_iso.day) * SECONDS_PER_DAY
		+ seconds_within_day - static_cast<std::int64_t>(parsed_utc_iso.tz_offset_seconds);

	if(parsed_utc_iso.second == 60)
	{
		posix_seconds += 1;
	}

	const double posix_epoch =
		static_cast<double>(posix_seconds) + static_cast<double>(parsed_utc_iso.nanos) * 1.0e-9;

	// At 23:59:60, UTC maps to the same POSIX second as 00:00:00 next day.
	// For correct boundary behavior, that leap transition must not be counted yet.
	const bool include_transition_now = (parsed_utc_iso.second != 60);
	const double posix_epoch_for_leap_lookup =
		(parsed_utc_iso.second == 60) ? static_cast<double>(posix_seconds) : posix_epoch;

	const double leap_now =
		cumulative_leap_correction(transitions, posix_epoch_for_leap_lookup, include_transition_now);
	const double leap_epoch =
		cumulative_leap_correction(transitions, static_cast<double>(tai_j2000_epoch_in_posix_time), true);

	const double utc_elapsed_non_leap = posix_epoch - static_cast<double>(tai_j2000_epoch_in_posix_time);
	const double leap_delta = leap_now - leap_epoch;

	return utc_elapsed_non_leap + leap_delta;
}

double utc_iso_to_tai_j2000(const std::string& iso_string)
{
	ParsedUtcIso parsed_utc_iso = parse_iso8601_utc(iso_string);
	return parsed_utc_iso_to_tai_j2000(parsed_utc_iso);
}

bool iso_8601_equal(const std::string& lhs, const std::string& rhs, std::size_t fractional_second_places)
{
	if(fractional_second_places > 9)
	{
		return false;
	}

	try
	{
		// Compare instants in a continuous time scale (TAI) so leap seconds are handled naturally.
		// We convert each ISO string to TAI seconds since the TAI J2000 epoch, then compare at the
		// requested fractional-second precision.
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
