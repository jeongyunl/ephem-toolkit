#pragma once

#include "utc_conversion.h"

//
// std::chrono::time_point to time_t conversion helpers
//

// duration_cast-based system_clock to time_t conversion helper
template <typename Duration = std::chrono::system_clock::duration>
time_t sys_time_to_time_t_dc(std::chrono::time_point<std::chrono::system_clock, Duration> tp)
{
	return std::chrono::duration_cast<std::chrono::seconds>(tp.time_since_epoch()).count();
}

// duration_cast-based system_clock to floating-point POSIX time conversion helper
template <typename Rep = double, typename Period = std::ratio<1>>
double sys_time_to_posix(std::chrono::time_point<std::chrono::system_clock> tp)
{
	return std::chrono::duration_cast<std::chrono::duration<Rep, Period>>(tp.time_since_epoch()).count();
}

// system_clock::to_time_t()-based system_clock to time_t conversion helper
template <typename Duration = std::chrono::system_clock::duration>
time_t sys_time_to_time_t_std(std::chrono::time_point<std::chrono::system_clock, Duration> tp)
{
	return std::chrono::system_clock::to_time_t(
		std::chrono::time_point_cast<std::chrono::system_clock::duration>(tp)
	);
}
