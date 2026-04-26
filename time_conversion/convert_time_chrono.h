#pragma once

#include "convert_time_common.h"
#include "convert_time_epochs.h"
#include "convert_time_j2000.h"

#include <chrono>
#include <format>
#include <string>

//
// posix_to_*_time()
//

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration> posix_to_sys_time(double posix_time)
{
	return std::chrono::sys_time<Duration>{
		std::chrono::duration_cast<Duration>(std::chrono::duration<double>{ posix_time })
	};
}

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> posix_to_utc_time(double posix_time)
{
	return std::chrono::utc_clock::from_sys(posix_to_sys_time<Duration>(posix_time));
}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
// Convert POSIX UTC seconds to a std::chrono::tai_time.
//
// POSIX time is aligned with UTC (ignoring leap seconds), while tai_time is continuous.
// A direct duration cast is therefore incorrect.
//
// We convert via posix time -> utc_time -> tai_time using chrono clock conversions.
// Note: this does not preserve the leap-second label (23:59:60) because POSIX cannot represent it.
template <typename Duration = std::chrono::tai_clock::duration>
std::chrono::time_point<std::chrono::tai_clock, Duration> posix_to_tai_time(double posix_time)
{
	const auto utc_time = posix_to_utc_time<Duration>(posix_time);
	return std::chrono::tai_clock::from_utc(utc_time);
}
#endif

//
// utc_j2000_to_*_time() functions
//

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration> utc_j2000_to_sys_time(double utc_j2000_time)
{
	const double posix_time = utc_j2000_to_posix(utc_j2000_time);
	return posix_to_sys_time<Duration>(posix_time);
}

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> utc_j2000_to_utc_time(double utc_j2000_time)
{
	const double posix_time = utc_j2000_to_posix(utc_j2000_time);
	return posix_to_utc_time<Duration>(posix_time);
}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
template <typename Duration = std::chrono::tai_clock::duration>
std::chrono::time_point<std::chrono::tai_clock, Duration> utc_j2000_to_tai_time(double utc_j2000_time)
{
	const double posix_time = utc_j2000_to_posix(utc_j2000_time);
	return posix_to_tai_time<Duration>(posix_time);
}
#endif

//
// tai_j2000_to_*_time() functions
//

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration> tai_j2000_to_sys_time(double tai_j2000_time)
{
	// TUDAT epochs:
	// - UTC TUDAT epoch is J2000: 2000-01-01 12:00:00 UTC
	// - TAI TUDAT epoch is J2000: 2000-01-01 12:00:00 TAI
	//
	// Convert TAI(TUDAT) -> UTC(POSIX) using the existing numeric conversion, then map to sys_time.
	const double posix_time = tai_j2000_to_posix(tai_j2000_time);
	return posix_to_sys_time<Duration>(posix_time);
}

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> tai_j2000_to_utc_time(double tai_j2000_time)
{
	return TAI_J2000_EPOCH_IN_UTC_TIME<Duration>
		+ std::chrono::duration_cast<Duration>(std::chrono::duration<double>{ tai_j2000_time });
}
#endif

//
// tt_j2000_to_*_time() functions
//

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration> tt_j2000_to_sys_time(double tt_j2000_time)
{
	// Convert TT(TUDAT) -> UTC(POSIX) using the existing numeric conversion, then map to sys_time.
	const double posix_time = tt_j2000_to_posix(tt_j2000_time);
	return posix_to_sys_time<Duration>(posix_time);
}

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> tt_j2000_to_utc_time(double tt_j2000_time)
{
	const auto tai_j2000_time = tt_j2000_to_tai_j2000(tt_j2000_time);
	return tai_j2000_to_utc_time<Duration>(tai_j2000_time);
}
#endif

//
// tdb_j2000_to_*_time() functions
//

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration> tdb_j2000_to_sys_time(double tdb_j2000_time)
{
	// Convert TDB(TUDAT) -> UTC(POSIX) using the existing numeric conversion, then map to sys_time.
	const double posix_time = tdb_j2000_to_posix(tdb_j2000_time);
	return posix_to_sys_time<Duration>(posix_time);
}

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> tdb_j2000_to_utc_time(double tdb_j2000_time)
{
	const auto tai_j2000_time = tdb_j2000_to_tai_j2000(tdb_j2000_time);
	return tai_j2000_to_utc_time<Duration>(tai_j2000_time);
}
#endif

//
// sys_time_to_*() functions
//

template <typename Duration = std::chrono::system_clock::duration>
std::string sys_time_to_utc_iso(std::chrono::time_point<std::chrono::system_clock, Duration> sys_time)
{
	return std::format("{:%FT%T}", sys_time);
}

// duration_cast-based system_clock to floating-point POSIX time conversion helper
template <typename Rep = double, typename Period = std::ratio<1>>
Rep sys_time_to_utc_posix(std::chrono::time_point<std::chrono::system_clock> sys_time)
{
	return std::chrono::duration_cast<std::chrono::duration<Rep, Period>>(sys_time.time_since_epoch())
		.count();
}

//
// utc_time_to_*() functions
//

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::string utc_time_to_utc_iso(std::chrono::time_point<std::chrono::utc_clock, Duration> utc_time)
{
	return std::format("{:%FT%T}", utc_time);
}
#endif // HAS_CHRONO_UTC_CLOCK

//
// parsed_utc_iso_to_*_time() functions
//

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration>
parsed_utc_iso_to_sys_time(const ParsedUtcIso& parsed_utc_iso)
{
	// Convert the parsed ISO-8601 time to a POSIX epoch, then map to sys_time.
	const double posix_time = parsed_utc_iso_to_posix(parsed_utc_iso);
	return posix_to_sys_time<Duration>(posix_time);
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
	const double posix_time = parsed_utc_iso_to_posix(parsed_utc_iso);
	const auto sys_time = posix_to_sys_time<Duration>(posix_time);
	auto utc_time = std::chrono::utc_clock::from_sys(sys_time);

	const bool is_leap_second = (parsed_utc_iso.second == 60);
	if(is_leap_second)
	{
		utc_time -= std::chrono::seconds{ 1 };
	}

	return utc_time;
}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
template <typename Duration = std::chrono::tai_clock::duration>
std::chrono::time_point<std::chrono::tai_clock, Duration>
parsed_utc_iso_to_tai_time(const ParsedUtcIso& parsed_utc_iso)
{
	const auto utc_time = parsed_utc_iso_to_utc_time<Duration>(parsed_utc_iso);
	return std::chrono::tai_clock::from_utc(utc_time);
}
#endif

//
// utc_iso_to_*_time() functions
//

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration>
utc_iso_to_sys_time(const std::string& iso_string)
{
	const ParsedUtcIso parsed_utc_iso = utc_iso_to_parsed_utc_iso(iso_string);
	return parsed_utc_iso_to_sys_time<Duration>(parsed_utc_iso);
}

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> utc_iso_to_utc_time(const std::string& iso_string)
{
	const ParsedUtcIso parsed_utc_iso = utc_iso_to_parsed_utc_iso(iso_string);
	return parsed_utc_iso_to_utc_time<Duration>(parsed_utc_iso);
}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
template <typename Duration = std::chrono::tai_clock::duration>
std::chrono::time_point<std::chrono::tai_clock, Duration> utc_iso_to_tai_time(const std::string& iso_string)
{
	const ParsedUtcIso parsed_utc_iso = utc_iso_to_parsed_utc_iso(iso_string);
	return parsed_utc_iso_to_tai_time<Duration>(parsed_utc_iso);
}
#endif // HAS_CHRONO_TAI_CLOCK
