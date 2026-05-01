#pragma once

#include "../time_converter.h"

class TimeConverterChronoUtc : public TimeConverter
{
public:
	static TimeConverterChronoUtc& instance()
	{
		static TimeConverterChronoUtc singleton;
		return singleton;
	}

	double posix_to_tai_j2000(double posix_time) const override;
	double parsed_utc_iso_to_tai_j2000(const ParsedUtcIso& parsed_utc_iso) const override;
	ParsedUtcIso tai_j2000_to_parsed_utc_iso(double tai_j2000_time) const override;

#ifdef HAS_CHRONO_UTC_CLOCK
	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration> posix_to_utc_time(double posix_time) const
	{
		return std::chrono::utc_clock::from_sys(posix_to_sys_time<Duration>(posix_time));
	}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration> posix_to_tai_time(double posix_time) const
	{
		const auto utc_time = posix_to_utc_time<Duration>(posix_time);
		return std::chrono::tai_clock::from_utc(utc_time);
	}
#endif

#ifdef HAS_CHRONO_UTC_CLOCK
	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration>
	utc_j2000_to_utc_time(double utc_j2000_time) const
	{
		return posix_to_utc_time<Duration>(utc_j2000_to_posix(utc_j2000_time));
	}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration>
	utc_j2000_to_tai_time(double utc_j2000_time) const
	{
		return posix_to_tai_time<Duration>(utc_j2000_to_posix(utc_j2000_time));
	}
#endif

#ifdef HAS_CHRONO_UTC_CLOCK
	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration>
	tai_j2000_to_utc_time(double tai_j2000_time) const
	{
		return epochs::TAI_J2000_EPOCH_IN_UTC_TIME<Duration>
			+ std::chrono::duration_cast<Duration>(std::chrono::duration<double>{ tai_j2000_time });
	}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration>
	tai_j2000_to_tai_time(double tai_j2000_time) const
	{
		return std::chrono::tai_clock::from_utc(tai_j2000_to_utc_time<Duration>(tai_j2000_time));
	}
#endif

#ifdef HAS_CHRONO_UTC_CLOCK
	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration> tt_j2000_to_utc_time(double tt_j2000_time) const
	{
		return tai_j2000_to_utc_time<Duration>(tt_j2000_to_tai_j2000(tt_j2000_time));
	}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration> tt_j2000_to_tai_time(double tt_j2000_time) const
	{
		return tai_j2000_to_tai_time<Duration>(tt_j2000_to_tai_j2000(tt_j2000_time));
	}
#endif

#ifdef HAS_CHRONO_UTC_CLOCK
	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration>
	tdb_j2000_to_utc_time(double tdb_j2000_time) const
	{
		return tai_j2000_to_utc_time<Duration>(tdb_j2000_to_tai_j2000(tdb_j2000_time));
	}
#endif

#ifdef HAS_CHRONO_UTC_CLOCK
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

#ifdef HAS_CHRONO_UTC_CLOCK
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
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration>
	parsed_utc_iso_to_tai_time(const ParsedUtcIso& parsed_utc_iso) const
	{
		const auto utc_time = parsed_utc_iso_to_utc_time<Duration>(parsed_utc_iso);
		return std::chrono::tai_clock::from_utc(utc_time);
	}
#endif

#ifdef HAS_CHRONO_UTC_CLOCK
	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration>
	utc_iso_to_utc_time(const std::string& iso_string) const
	{
		return parsed_utc_iso_to_utc_time<Duration>(utc_iso_to_parsed_utc_iso(iso_string));
	}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration>
	utc_iso_to_tai_time(const std::string& iso_string) const
	{
		return parsed_utc_iso_to_tai_time<Duration>(utc_iso_to_parsed_utc_iso(iso_string));
	}
#endif

	TimeConverterChronoUtc(const TimeConverterChronoUtc&) = delete;
	TimeConverterChronoUtc& operator=(const TimeConverterChronoUtc&) = delete;
	TimeConverterChronoUtc(TimeConverterChronoUtc&&) = delete;
	TimeConverterChronoUtc& operator=(TimeConverterChronoUtc&&) = delete;

	TimeValue convert_time(const TimeValue& input, TimeFormat input_format, TimeFormat output_format)
		const override;

private:
	TimeConverterChronoUtc() = default;
	~TimeConverterChronoUtc() = default;
};
