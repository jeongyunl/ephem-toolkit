#include "utc_iso_to_x.h"

double iso_to_utc_tudat(const std::string& utc_iso8601)
{
	const ParsedIsoUtc utc = parse_iso8601_utc(utc_iso8601);
	const auto utc_unix_tp = iso_utc_to_unix_seconds_non_leap(utc);
	const double utc_unix_seconds = std::chrono::duration<double>(utc_unix_tp.time_since_epoch()).count();

	return utc_unix_seconds - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
}

double iso_to_tai_tudat(const std::string& utc_iso8601)
{
	// Required epoch mapping:
	// TAI epoch = 2000-01-01 12:00:00 TAI = 2000-01-01 11:59:28 UTC
	constexpr std::int64_t tai_epoch_utc_unix =
		days_from_civil(2000, 1, 1) * SECONDS_PER_DAY + 11 * SECONDS_PER_HOUR + 59 * SECONDS_PER_MINUTE + 28;

	const ParsedIsoUtc utc = parse_iso8601_utc(utc_iso8601);
	const auto utc_unix_tp = iso_utc_to_unix_seconds_non_leap(utc);
	const double utc_unix_seconds = std::chrono::duration<double>(utc_unix_tp.time_since_epoch()).count();

	// At 23:59:60, UTC maps to the same Unix second as 00:00:00 next day.
	// For correct boundary behavior, that leap transition must not be counted yet.
	const bool include_transition_now = (utc.second != 60);
	const double utc_unix_for_leap_lookup = (utc.second == 60)
		? static_cast<double>(
			std::chrono::time_point_cast<std::chrono::seconds>(utc_unix_tp).time_since_epoch().count()
		)
		: utc_unix_seconds;
	const double leap_now =
		cumulative_leap_correction(transitions, utc_unix_for_leap_lookup, include_transition_now);
	const double leap_epoch =
		cumulative_leap_correction(transitions, static_cast<double>(tai_epoch_utc_unix), true);

	const double utc_elapsed_non_leap = utc_unix_seconds - static_cast<double>(tai_epoch_utc_unix);
	const double leap_delta = leap_now - leap_epoch;

	return utc_elapsed_non_leap + leap_delta;
}
