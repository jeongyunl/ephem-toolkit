#pragma once

#include "convert_time_common.h"

#include <chrono>
#include <format>
#include <string>

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

template <typename Duration = std::chrono::system_clock::duration>
std::chrono::time_point<std::chrono::system_clock, Duration> utc_posix_to_sys_time(double utc_posix_epoch)
{
	return std::chrono::sys_time<Duration>{
		std::chrono::duration_cast<Duration>(std::chrono::duration<double>{ utc_posix_epoch })
	};
}

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
std::string utc_time_to_utc_iso(std::chrono::time_point<std::chrono::utc_clock, Duration> utc_time)
{
	return std::format("{:%FT%T}", utc_time);
}

template <typename Rep = double, typename Period = std::ratio<1>>
Rep sys_time_to_utc_posix(std::chrono::time_point<std::chrono::utc_clock> utc_time)
{
	return std::chrono::duration_cast<std::chrono::duration<Rep, Period>>(utc_time.time_since_epoch())
		.count();
}

template <typename Duration = std::chrono::utc_clock::duration>
std::chrono::time_point<std::chrono::utc_clock, Duration> utc_posix_to_utc_time(double utc_posix_epoch)
{
	return std::chrono::utc_time<Duration>{
		std::chrono::duration_cast<Duration>(std::chrono::duration<double>{ utc_posix_epoch })
	};
}

#endif
