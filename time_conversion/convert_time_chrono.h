#pragma once

#include "convert_time_common.h"

#include <chrono>
#include <format>
#include <string>

//
// utc_posix_to_*_time()
//

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration> utc_posix_to_sys_time(double utc_posix_epoch)
{
	return std::chrono::sys_time<Duration>{
		std::chrono::duration_cast<Duration>(std::chrono::duration<double>{ utc_posix_epoch })
	};
}

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> utc_posix_to_utc_time(double utc_posix_epoch)
{
	return std::chrono::utc_clock::from_sys(utc_posix_to_sys_time<Duration>(utc_posix_epoch));
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
std::chrono::time_point<std::chrono::tai_clock, Duration> utc_posix_to_tai_time(double utc_posix_epoch)
{
	const auto utc_time = utc_posix_to_utc_time<std::chrono::utc_clock::duration>(utc_posix_epoch);
	const auto tai_time = std::chrono::tai_clock::from_utc(utc_time);
	return std::chrono::time_point_cast<Duration>(tai_time);
}
#endif

//
// utc_tudat_to_*_time() functions
//

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration> utc_tudat_to_sys_time(double utc_tudat_epoch)
{
	const double utc_posix_epoch = utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;

	return utc_posix_to_sys_time<Duration>(utc_posix_epoch);
}

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> utc_tudat_to_utc_time(double utc_tudat_epoch)
{
	const double utc_posix_epoch = utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;

	return utc_posix_to_utc_time<Duration>(utc_posix_epoch);
}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
template <typename Duration = std::chrono::tai_clock::duration>
std::chrono::time_point<std::chrono::tai_clock, Duration> utc_tudat_to_tai_time(double utc_tudat_epoch)
{
	const double utc_posix_epoch = utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
	return utc_posix_to_tai_time<Duration>(utc_posix_epoch);
}
#endif

//
// tai_tudat_to_*() functions
//

extern double tai_tudat_to_utc_posix(double tai_tudat_epoch);

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration> tai_tudat_to_sys_time(double tai_tudat_epoch)
{
	// TUDAT epochs:
	// - UTC TUDAT epoch is J2000: 2000-01-01 12:00:00 UTC
	// - TAI TUDAT epoch is J2000: 2000-01-01 12:00:00 TAI
	//
	// Convert TAI(TUDAT) -> UTC(POSIX) using the existing numeric conversion, then map to sys_time.
	const double utc_posix_epoch = tai_tudat_to_utc_posix(tai_tudat_epoch);
	return utc_posix_to_sys_time<Duration>(utc_posix_epoch);
}

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> tai_tudat_to_utc_time(double tai_tudat_epoch)
{
	const double utc_posix_epoch = tai_tudat_to_utc_posix(tai_tudat_epoch);
	return utc_posix_to_utc_time<Duration>(utc_posix_epoch);
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
