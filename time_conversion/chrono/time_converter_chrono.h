#pragma once

#include "../base/time_converter_base.h"

class TimeConverterChrono : public TimeConverterBase
{
	TimeConverterChrono() = default;
	~TimeConverterChrono() = default;

public:
	TimeConverterChrono(const TimeConverterChrono&) = delete;
	TimeConverterChrono& operator=(const TimeConverterChrono&) = delete;
	TimeConverterChrono(TimeConverterChrono&&) = delete;
	TimeConverterChrono& operator=(TimeConverterChrono&&) = delete;

	static TimeConverterChrono& instance()
	{
		static TimeConverterChrono singleton;
		return singleton;
	}

	TimeValue
	convert_time(const TimeValue& input, TimeFormat input_format, TimeFormat output_format) const override;

#ifdef HAS_CHRONO_UTC_CLOCK
	double posix_to_tai_j2000(double posix_time) const override;
	double parsed_utc_iso_to_tai_j2000(const ParsedUtcIso& parsed_utc_iso) const override;
	ParsedUtcIso tai_j2000_to_parsed_utc_iso(double tai_j2000_time) const override;
#endif

	//
	// *_to_sys_time() functions
	//

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration>
	parsed_utc_iso_to_sys_time(const ParsedUtcIso& parsed_utc_iso) const
	{
		const auto posix_time = parsed_utc_iso_to_posix(parsed_utc_iso);
		return posix_to_sys_time<Duration>(posix_time);
	}

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration>
	utc_iso_to_sys_time(const std::string& iso_string) const
	{
		const auto parsed_utc_iso = utc_iso_to_parsed_utc_iso(iso_string);
		return parsed_utc_iso_to_sys_time<Duration>(parsed_utc_iso);
	}

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration> posix_to_sys_time(double posix_time) const
	{
		return std::chrono::sys_time<Duration>{
			std::chrono::duration_cast<Duration>(std::chrono::duration<double>{ posix_time })
		};
	}

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration> utc_j2000_to_sys_time(double utc_j2000_time
	) const
	{
		const auto posix_time = utc_j2000_to_posix(utc_j2000_time);
		return posix_to_sys_time<Duration>(posix_time);
	}

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration> tai_j2000_to_sys_time(double tai_j2000_time
	) const
	{
		const auto posix_time = tai_j2000_to_posix(tai_j2000_time);
		return posix_to_sys_time<Duration>(posix_time);
	}

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration> tt_j2000_to_sys_time(double tt_j2000_time
	) const
	{
		const auto posix_time = tt_j2000_to_posix(tt_j2000_time);
		return posix_to_sys_time<Duration>(posix_time);
	}

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration> tdb_j2000_to_sys_time(double tdb_j2000_time
	) const
	{
		const auto posix_time = tdb_j2000_to_posix(tdb_j2000_time);
		return posix_to_sys_time<Duration>(posix_time);
	}

	//
	// sys_time_to_*() functions
	//

	template <typename Duration = std::chrono::system_clock::duration>
	std::string sys_time_to_utc_iso(
		std::chrono::time_point<std::chrono::system_clock, Duration> sys_time,
		bool use_t_separator = false
	) const
	{
		if(use_t_separator)
		{
			return std::format("{:%FT%T}", sys_time);
		}
		else
		{
			return std::format("{:%F %T}", sys_time);
		}
	}

	template <typename Rep = double, typename Period = std::ratio<1>>
	Rep sys_time_to_utc_posix(std::chrono::time_point<std::chrono::system_clock> sys_time) const
	{
		return std::chrono::duration_cast<std::chrono::duration<Rep, Period>>(sys_time.time_since_epoch())
			.count();
	}

#ifdef HAS_CHRONO_UTC_CLOCK

	//
	// *_to_utc_time() functions
	//

	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration>
	parsed_utc_iso_to_utc_time(const ParsedUtcIso& parsed_utc_iso) const
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

	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration>
	utc_iso_to_utc_time(const std::string& iso_string) const
	{
		const auto parsed_utc_iso = utc_iso_to_parsed_utc_iso(iso_string);
		return parsed_utc_iso_to_utc_time<Duration>(parsed_utc_iso);
	}

	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration> posix_to_utc_time(double posix_time) const
	{
		const auto sys_time = posix_to_sys_time<Duration>(posix_time);
		return std::chrono::utc_clock::from_sys(sys_time);
	}

	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration> utc_j2000_to_utc_time(double utc_j2000_time
	) const
	{
		const auto posix_time = utc_j2000_to_posix(utc_j2000_time);
		return posix_to_utc_time<Duration>(posix_time);
	}

	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration> tai_j2000_to_utc_time(double tai_j2000_time
	) const
	{
		return epochs::TAI_J2000_EPOCH_IN_UTC_TIME<Duration>
			+ std::chrono::duration_cast<Duration>(std::chrono::duration<double>{ tai_j2000_time });
	}

	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration> tt_j2000_to_utc_time(double tt_j2000_time) const
	{
		const auto tai_j2000_time = tt_j2000_to_tai_j2000(tt_j2000_time);
		return tai_j2000_to_utc_time<Duration>(tai_j2000_time);
	}

	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration> tdb_j2000_to_utc_time(double tdb_j2000_time
	) const
	{
		const auto tai_j2000_time = tdb_j2000_to_tai_j2000(tdb_j2000_time);
		return tai_j2000_to_utc_time<Duration>(tai_j2000_time);
	}

	//
	// utc_time_to_*() functions
	//

	template <typename Duration = std::chrono::utc_clock::duration>
	std::string utc_time_to_utc_iso(
		std::chrono::time_point<std::chrono::utc_clock, Duration> utc_time,
		bool use_t_separator = false
	) const
	{
		if(use_t_separator)
		{
			return std::format("{:%FT%T}", utc_time);
		}
		else
		{
			return std::format("{:%F %T}", utc_time);
		}
	}

#endif

#ifdef HAS_CHRONO_TAI_CLOCK

	//
	// *_to_tai_time() functions
	//

	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration>
	parsed_utc_iso_to_tai_time(const ParsedUtcIso& parsed_utc_iso) const
	{
		const auto utc_time = parsed_utc_iso_to_utc_time<Duration>(parsed_utc_iso);
		return std::chrono::tai_clock::from_utc(utc_time);
	}

	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration>
	utc_iso_to_tai_time(const std::string& iso_string) const
	{
		const auto parsed_utc_iso = utc_iso_to_parsed_utc_iso(iso_string);
		return parsed_utc_iso_to_tai_time<Duration>(parsed_utc_iso);
	}

	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration> posix_to_tai_time(double posix_time) const
	{
		const auto utc_time = posix_to_utc_time<Duration>(posix_time);
		return std::chrono::tai_clock::from_utc(utc_time);
	}

	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration> utc_j2000_to_tai_time(double utc_j2000_time
	) const
	{
		const auto posix_time = utc_j2000_to_posix(utc_j2000_time);
		return posix_to_tai_time<Duration>(posix_time);
	}

	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration> tai_j2000_to_tai_time(double tai_j2000_time
	) const
	{
		const auto utc_time = tai_j2000_to_utc_time<Duration>(tai_j2000_time);
		return std::chrono::tai_clock::from_utc(utc_time);
	}

	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration> tt_j2000_to_tai_time(double tt_j2000_time) const
	{
		const auto tai_j2000_time = tt_j2000_to_tai_j2000(tt_j2000_time);
		return tai_j2000_to_tai_time<Duration>(tai_j2000_time);
	}
#endif
};
