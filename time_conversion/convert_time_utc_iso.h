#pragma once

#include "convert_time_common.h"
#include "convert_time_iso8601.h"

#include <chrono>

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration>
parsed_utc_iso_to_sys_time(const ParsedUtcIso& parsed_utc_iso)
{
#if 0
	// Number of days since the POSIX epoch (1970-01-01) for the calendar date.
	const std::int64_t days_since_posix_epoch =
		calendar_date_to_posix_days(parsed_utc_iso.year, parsed_utc_iso.month, parsed_utc_iso.day);

	// Seconds elapsed within the day from midnight, treating leap second 60 as 59
	// for the purpose of building a POSIX timestamp (POSIX ignores the leap second).
	std::int64_t seconds_within_day = static_cast<std::int64_t>(parsed_utc_iso.hour) * SECONDS_PER_HOUR
		+ static_cast<std::int64_t>(parsed_utc_iso.minute) * SECONDS_PER_MINUTE
		+ static_cast<std::int64_t>(parsed_utc_iso.second);

	// A leap second (second == 60) does not exist in the POSIX/Unix time scale.
	// Map it to SECONDS_PER_DAY so the resulting POSIX timestamp equals midnight of the next day,
	// which is the same value POSIX assigns to the next second after the leap second.
	if(parsed_utc_iso.second == 60)
	{
		seconds_within_day = SECONDS_PER_DAY;
	}

	// Convert to a POSIX timestamp, applying the UTC offset so the result is always UTC.
	// Subtracting the offset converts a local/offset time to UTC: e.g. +05:30 → subtract 19800 s.
	const std::int64_t posix_seconds =
		days_since_posix_epoch * SECONDS_PER_DAY + seconds_within_day - parsed_utc_iso.tz_offset_seconds;
#else
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wmissing-field-initializers"
	struct tm tm = {
		.tm_sec =
			(parsed_utc_iso.second == 60) ? 59 : parsed_utc_iso.second, // Map leap second to 59 for timegm
		.tm_min = parsed_utc_iso.minute, // 0-59
		.tm_hour = parsed_utc_iso.hour, // 0-23
		.tm_mday = static_cast<int>(parsed_utc_iso.day), // 1-31
		.tm_mon = static_cast<int>(parsed_utc_iso.month) - 1, // 0-11
		.tm_year = parsed_utc_iso.year - 1900, // years since 1900
	};
#pragma GCC diagnostic pop

	const time_t posix_seconds = timegm(&tm) - parsed_utc_iso.tz_offset_seconds
		+ ((parsed_utc_iso.second == 60) ? 1 : 0); // Add 1 second if it was a leap second
#endif

	// Combine the integer-second POSIX timestamp with the sub-second nanosecond remainder.
	return std::chrono::sys_time<Duration>{ std::chrono::duration_cast<Duration>(
		std::chrono::seconds{ posix_seconds } + std::chrono::nanoseconds{ parsed_utc_iso.nanos }
	) };
}

#ifdef HAS_CHRONO_UTC_CLOCK
// Convert a parsed ISO-8601 UTC timestamp to a std::chrono::utc_time, preserving leap-second information.
//
// Rationale:
// - parsed_utc_iso_to_sys_time() maps an ISO leap second (..:59:60) to the POSIX/sys_time instant
//   of the following second (00:00:00 of the next day), because POSIX has no leap seconds.
// - std::chrono::utc_clock::from_sys() will therefore yield a utc_time that is normalized and
//   typically not marked as a leap second.
// - To preserve the leap-second label for round-tripping/formatting, we detect second==60 and
//   subtract one second after conversion, so the resulting utc_time falls into the leap second.
//
// Note: timezone offsets are already applied in parsed_utc_iso_to_sys_time().
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration>
parsed_utc_iso_to_utc_time(const ParsedUtcIso& parsed_utc_iso)
{
	const bool is_leap_second = (parsed_utc_iso.second == 60);

	const auto sys_time = parsed_utc_iso_to_sys_time<std::chrono::system_clock::duration>(parsed_utc_iso);
	auto utc_time = std::chrono::utc_clock::from_sys(sys_time);

	if(is_leap_second)
	{
		utc_time -= std::chrono::seconds{ 1 };
	}

	return std::chrono::time_point_cast<Duration>(utc_time);
}
#endif

// ISO-8601 parser based implementations

double utc_iso_to_utc_posix(const std::string& iso_string);
double utc_iso_to_utc_tudat(const std::string& iso_string);
double utc_iso_to_tai_tudat(const std::string& iso_string);
double utc_iso_to_tt_tudat(const std::string& iso_string);
double utc_iso_to_tdb_tudat(const std::string& iso_string);

std::string utc_posix_to_utc_iso(double utc_posix_epoch);
std::string utc_tudat_to_utc_iso(double utc_tudat_epoch);
std::string tai_tudat_to_utc_iso(double tai_tudat_epoch);
std::string tt_tudat_to_utc_iso(double tt_tudat_epoch);
std::string tdb_tudat_to_utc_iso(double tdb_tudat_epoch);

// Tudat DateTime based implementations

std::string utc_iso_to_utc_iso(const std::string& iso_string);

double utc_iso_tudat_to_utc_posix(const std::string& iso_string);
double utc_iso_tudat_to_utc_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tai_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tt_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tdb_tudat(const std::string& iso_string);

std::string utc_posix_to_utc_iso_tudat(double utc_posix_epoch);
std::string utc_tudat_to_utc_iso_tudat(double utc_tudat_epoch);
std::string tai_tudat_to_utc_iso_tudat(double tai_tudat_epoch);
std::string tt_tudat_to_utc_iso_tudat(double tt_tudat_epoch);
std::string tdb_tudat_to_utc_iso_tudat(double tdb_tudat_epoch);

#ifdef HAS_CHRONO_FROM_STREAM
template <typename Clock, typename Duration = typename Clock::duration>
std::chrono::time_point<Clock, Duration> utc_iso_to_chrono_time(const std::string& iso_string)
{
	std::chrono::time_point<Clock, Duration> time_point;

	std::istringstream is(std::string{ iso_string });
	if(iso_string.find('T') == std::string::npos)
	{
		std::chrono::from_stream(is, "%F %T", time_point);
	}
	else
	{
		std::chrono::from_stream(is, "%FT%T", time_point);
	}

	return time_point;
}
#endif

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration>
utc_iso_to_sys_time(const std::string& iso_string)
{
#ifdef HAS_CHRONO_FROM_STREAM
	return utc_iso_to_chrono_time<std::chrono::system_clock, Duration>(iso_string);
#else
	const ParsedUtcIso utc = utc_iso_to_parsed_utc_iso(iso_string);
	const auto sys_time = parsed_utc_iso_to_sys_time<Duration>(utc);
	return std::chrono::time_point_cast<Duration>(sys_time);
#endif
}

#ifdef HAS_CHRONO_UTC_CLOCK
// Convert an ISO-8601 UTC timestamp (with optional offset) to a std::chrono::utc_time.
//
// Leap seconds:
// - ISO-8601 allows "...:59:60" to represent an inserted leap second.
// - Some standard library implementations normalize utc_time formatting such that the leap second
//   is not preserved when converting from sys_time.
// - To preserve the leap-second instant, we detect second==60 in the parsed input and, after
//   converting to utc_time, subtract one second so that formatting via utc_time_to_utc_iso()
//   yields "...:60".
//
// This relies on utc_iso_to_parsed_utc_iso() and parsed_utc_iso_to_sys_time(const ParsedUtcIso&) already
// mapping the leap second to the correct POSIX/sys_time instant (i.e., the first second of the next day).
//
// Note that std::chrono::from_stream() and std::chrono::parse() are avaialbe in GNU libstdc++ 14 or later
//
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> utc_iso_to_utc_time(const std::string& iso_string)
{
#ifdef HAS_CHRONO_FROM_STREAM
	return utc_iso_to_chrono_time<std::chrono::utc_clock, Duration>(iso_string);
#else
	const ParsedUtcIso parsed = utc_iso_to_parsed_utc_iso(iso_string);
	const bool is_leap_second = (parsed.second == 60);

	const auto sys_time = parsed_utc_iso_to_sys_time<std::chrono::system_clock::duration>(parsed);
	auto utc_time = std::chrono::utc_clock::from_sys(sys_time);

	if(is_leap_second)
	{
		utc_time -= std::chrono::seconds{ 1 };
	}

	return std::chrono::time_point_cast<Duration>(utc_time);
#endif
}

#ifdef HAS_CHRONO_TAI_CLOCK
template <typename Duration = std::chrono::tai_clock::duration>
std::chrono::time_point<std::chrono::tai_clock, Duration> utc_iso_to_tai_time(const std::string& iso_string)
{
#ifdef HAS_CHRONO_FROM_STREAM
	return utc_iso_to_chrono_time<std::chrono::tai_clock, Duration>(iso_string);
#else

	// Parse ISO-8601 UTC timestamp (supports leap second 23:59:60 and optional offset)
	const ParsedUtcIso parsed = utc_iso_to_parsed_utc_iso(iso_string);
	const bool is_leap_second = (parsed.second == 60);

	// Convert to sys_time first (POSIX-like, leap second mapped to next day's 00:00:00)
	const auto sys_time = parsed_utc_iso_to_sys_time<std::chrono::system_clock::duration>(parsed);

	// Convert sys_time -> TAI using chrono clocks
	// (tai_clock::from_sys is not available in all standard library implementations;
	// use utc_clock as an intermediate, which is required when HAS_CHRONO_UTC_CLOCK is set.)
	const auto utc_time = std::chrono::utc_clock::from_sys(sys_time);
	auto tai_time = std::chrono::tai_clock::from_utc(utc_time);

	// Preserve the leap-second instant: map the sys_time instant back into the leap second
	// so that formatting via tai->utc (if done) can round-trip correctly.
	if(is_leap_second)
	{
		tai_time -= std::chrono::seconds{ 1 };
	}

	return std::chrono::time_point_cast<Duration>(tai_time);
#endif
}
#endif // HAS_CHRONO_TAI_CLOCK
#endif // HAS_CHRONO_UTC_CLOCK
