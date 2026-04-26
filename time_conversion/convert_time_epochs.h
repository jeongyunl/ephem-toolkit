#pragma once

#include "convert_time_common.h"
#include "convert_time_iso8601.h"

namespace epochs
{
using namespace std::chrono;
using namespace std::chrono_literals;

//
// UTC J2000 epoch: 2000-01-01 12:00:00 UTC
//

constexpr auto UTC_J2000_EPOCH_IN_ISO8601 = "2000-01-01T12:00:00";
constexpr auto UTC_J2000_EPOCH_IN_POSIX_TIME =
	calendar_date_to_posix_days(2000, 1, 1) * SECONDS_PER_DAY + 12 * SECONDS_PER_HOUR;
constexpr auto UTC_J2000_EPOCH_IN_TAI_J2000_TIME = static_cast<int64_t>(J2000_TAI_MINUS_UTC);
constexpr auto UTC_J2000_EPOCH_IN_TT_J2000_TIME = J2000_TAI_MINUS_UTC + TT_EPOCH_MINUS_TAI_EPOCH;

template <typename Duration = std::chrono::system_clock::duration>
constexpr std::chrono::time_point<std::chrono::system_clock, Duration> UTC_J2000_EPOCH_IN_SYS_TIME = {
	sys_days{ 2000y / January / 1 } + hours{ 12 }
};

//
// TAI J2000 epoch = 2000-01-01 12:00:00 TAI = 2000-01-01 11:59:28 UTC
//

constexpr auto TAI_J2000_EPOCH_IN_ISO8601 = "2000-01-01T11:59:28";
constexpr auto TAI_J2000_EPOCH_IN_POSIX_TIME = calendar_date_to_posix_days(2000, 1, 1) * SECONDS_PER_DAY
	+ 11 * SECONDS_PER_HOUR + 59 * SECONDS_PER_MINUTE + 28;
constexpr auto TAI_J2000_EPOCH_IN_UTC_J2000_TIME = -J2000_TAI_MINUS_UTC;
constexpr auto TAI_J2000_EPOCH_IN_TT_J2000_TIME = TT_EPOCH_MINUS_TAI_EPOCH;

template <typename Duration = std::chrono::system_clock::duration>
constexpr std::chrono::time_point<std::chrono::system_clock, Duration> TAI_J2000_EPOCH_IN_SYS_TIME = {
	sys_days{ 2000y / January / 1 } + hours{ 11 } + minutes{ 59 } + seconds{ 28 }
};

#ifdef HAS_CHRONO_UTC_CLOCK
template <typename Duration = std::chrono::utc_clock::duration>
constexpr std::chrono::time_point<std::chrono::utc_clock, Duration> TAI_J2000_EPOCH_IN_UTC_TIME =
	std::chrono::utc_time<Duration>{ std::chrono::duration_cast<Duration>(std::chrono::duration<double>{
		static_cast<double>(
			TAI_J2000_EPOCH_IN_POSIX_TIME + J2000_TAI_MINUS_UTC - POST_1972_TAI_MINUS_UTC
		) }) };
#endif

//
// TT J2000 epoch = 2000-01-01 12:00:00 TT = 2000-01-01 11:58:55.816 UTC
//

constexpr auto TT_J2000_EPOCH_IN_ISO8601 = "2000-01-01T11:58:55.816";
constexpr auto TT_J2000_EPOCH_IN_POSIX_TIME = calendar_date_to_posix_days(2000, 1, 1) * SECONDS_PER_DAY
	+ 11 * SECONDS_PER_HOUR + 58 * SECONDS_PER_MINUTE + 55.816;
constexpr auto TT_J2000_EPOCH_IN_UTC_J2000_TIME = -J2000_TAI_MINUS_UTC - TT_EPOCH_MINUS_TAI_EPOCH;
constexpr auto TT_J2000_EPOCH_IN_TAI_J2000_TIME = -TT_EPOCH_MINUS_TAI_EPOCH;

template <typename Duration = std::chrono::system_clock::duration>
constexpr std::chrono::time_point<std::chrono::system_clock, Duration> TT_J2000_EPOCH_IN_SYS_TIME = {
	sys_days{ 2000y / January / 1 } + hours{ 11 } + minutes{ 58 } + seconds{ 55 } + milliseconds{ 816 }
};

//
// POSIX epoch: 1970-01-01 00:00:00 UTC
//

constexpr auto POSIX_EPOCH_IN_ISO8601 = "1970-01-01T00:00:00";
constexpr auto POSIX_EPOCH_IN_UTC_J2000_TIME = -UTC_J2000_EPOCH_IN_POSIX_TIME;
constexpr auto POSIX_EPOCH_IN_TAI_J2000_TIME =
	-UTC_J2000_EPOCH_IN_POSIX_TIME + static_cast<int64_t>(PRE_1972_TAI_MINUS_UTC_AT_1970);
constexpr auto POSIX_EPOCH_IN_TT_J2000_TIME = POSIX_EPOCH_IN_TAI_J2000_TIME + TT_EPOCH_MINUS_TAI_EPOCH;

template <typename Duration = std::chrono::system_clock::duration>
constexpr std::chrono::time_point<std::chrono::system_clock, Duration> POSIX_EPOCH_IN_SYS_TIME = { sys_days{
	1970y / January / 1 } };

//
// 1972 epoch: 1972-01-01 00:00:00 UTC
// 	the synchronization point of UTC and TAI (with 10 seconds offset)

constexpr auto UTC_1972_EPOCH_IN_ISO8601 = "1972-01-01T00:00:00";
constexpr auto UTC_1972_EPOCH_IN_POSIX_TIME = calendar_date_to_posix_days(1972, 1, 1) * SECONDS_PER_DAY;
template <typename Duration = std::chrono::system_clock::duration>
constexpr std::chrono::time_point<std::chrono::system_clock, Duration> UTC_1972_EPOCH_IN_SYS_TIME = {
	sys_days{ 1972y / January / 1 }
};

} // namespace epochs
