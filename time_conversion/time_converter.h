#pragma once

#include "convert_time_epochs.h"
#include "convert_time_iso8601.h"
#include "time_converter_base.h"

#include <chrono>
#include <format>
#include <string>

class TimeConverter : public TimeConverterBase
{
public:
	static TimeConverter& instance()
	{
		static TimeConverter singleton;
		return singleton;
	}

	TimeConverter(const TimeConverter&) = delete;
	TimeConverter& operator=(const TimeConverter&) = delete;
	TimeConverter(TimeConverter&&) = delete;
	TimeConverter& operator=(TimeConverter&&) = delete;

	ParsedUtcIso utc_iso_to_parsed_utc_iso(const std::string& utc_iso) const;

	std::string parsed_utc_iso_to_utc_iso(
		const ParsedUtcIso& parsed_utc_iso,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const;

	std::string utc_iso_to_utc_iso(const std::string& iso_string) const override { return iso_string; }

	double posix_to_posix(double posix_time) const override { return posix_time; }
	double utc_j2000_to_utc_j2000(double utc_j2000_time) const override { return utc_j2000_time; }
	double tai_j2000_to_tai_j2000(double tai_j2000_time) const override { return tai_j2000_time; }
	double tt_j2000_to_tt_j2000(double tt_j2000_time) const override { return tt_j2000_time; }
	double tdb_j2000_to_tdb_j2000(double tdb_j2000_time) const override { return tdb_j2000_time; }

	double posix_to_utc_j2000(double posix_time) const override
	{
		return posix_time - static_cast<double>(epochs::UTC_J2000_EPOCH_IN_POSIX_TIME);
	}
	double utc_j2000_to_posix(double utc_j2000_time) const override
	{
		return utc_j2000_time + static_cast<double>(epochs::UTC_J2000_EPOCH_IN_POSIX_TIME);
	}
	double tai_j2000_to_tt_j2000(double tai_j2000_time) const override
	{
		return tai_j2000_time + TT_MINUS_TAI;
	}
	double tai_j2000_to_tdb_j2000(double tai_j2000_time) const override
	{
		return tai_j2000_to_tt_j2000(tai_j2000_time);
	}
	double tt_j2000_to_tai_j2000(double tt_j2000_time) const override { return tt_j2000_time - TT_MINUS_TAI; }

	double parsed_utc_iso_to_posix(const ParsedUtcIso& parsed_utc_iso) const;
	double parsed_utc_iso_to_tai_j2000(const ParsedUtcIso& parsed_utc_iso) const;
	double parsed_utc_iso_to_utc_j2000(const ParsedUtcIso& parsed_utc_iso) const
	{
		return posix_to_utc_j2000(parsed_utc_iso_to_posix(parsed_utc_iso));
	}
	double parsed_utc_iso_to_tt_j2000(const ParsedUtcIso& parsed_utc_iso) const
	{
		return tai_j2000_to_tt_j2000(parsed_utc_iso_to_tai_j2000(parsed_utc_iso));
	}

	double utc_iso_to_posix(const std::string& iso_string) const override
	{
		return parsed_utc_iso_to_posix(utc_iso_to_parsed_utc_iso(iso_string));
	}
	double utc_iso_to_utc_j2000(const std::string& iso_string) const override
	{
		return posix_to_utc_j2000(utc_iso_to_posix(iso_string));
	}
	double utc_iso_to_tai_j2000(const std::string& iso_string) const override
	{
		return parsed_utc_iso_to_tai_j2000(utc_iso_to_parsed_utc_iso(iso_string));
	}
	double utc_iso_to_tt_j2000(const std::string& iso_string) const override
	{
		return tai_j2000_to_tt_j2000(utc_iso_to_tai_j2000(iso_string));
	}
	double utc_iso_to_tdb_j2000(const std::string& iso_string) const override
	{
		return tai_j2000_to_tdb_j2000(utc_iso_to_tai_j2000(iso_string));
	}

	ParsedUtcIso posix_to_parsed_utc_iso(double posix_time) const;
	double posix_to_tai_j2000(double posix_time) const override;
	std::string
	posix_to_utc_iso(double posix_time, bool use_t_separator = false, int fractional_second_places = 3)
		const override
	{
		return parsed_utc_iso_to_utc_iso(
			posix_to_parsed_utc_iso(posix_time),
			use_t_separator,
			fractional_second_places
		);
	}
	double posix_to_tt_j2000(double posix_time) const override
	{
		return tai_j2000_to_tt_j2000(posix_to_tai_j2000(posix_time));
	}
	double posix_to_tdb_j2000(double posix_time) const override { return posix_to_tt_j2000(posix_time); }

	ParsedUtcIso utc_j2000_to_parsed_utc_iso(double utc_j2000_time) const
	{
		return posix_to_parsed_utc_iso(utc_j2000_to_posix(utc_j2000_time));
	}
	std::string utc_j2000_to_utc_iso(
		double utc_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override
	{
		return parsed_utc_iso_to_utc_iso(
			utc_j2000_to_parsed_utc_iso(utc_j2000_time),
			use_t_separator,
			fractional_second_places
		);
	}
	double utc_j2000_to_tai_j2000(double utc_j2000_time) const override
	{
		return posix_to_tai_j2000(utc_j2000_to_posix(utc_j2000_time));
	}
	double utc_j2000_to_tt_j2000(double utc_j2000_time) const override
	{
		return tai_j2000_to_tt_j2000(utc_j2000_to_tai_j2000(utc_j2000_time));
	}
	double utc_j2000_to_tdb_j2000(double utc_j2000_time) const override
	{
		return utc_j2000_to_tt_j2000(utc_j2000_time);
	}

	ParsedUtcIso tai_j2000_to_parsed_utc_iso(double tai_j2000_time) const;
	double tai_j2000_to_posix(double tai_j2000_time) const override;
	std::string tai_j2000_to_utc_iso(
		double tai_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override
	{
		return parsed_utc_iso_to_utc_iso(
			tai_j2000_to_parsed_utc_iso(tai_j2000_time),
			use_t_separator,
			fractional_second_places
		);
	}
	double tai_j2000_to_utc_j2000(double tai_j2000_time) const override
	{
		return posix_to_utc_j2000(tai_j2000_to_posix(tai_j2000_time));
	}

	ParsedUtcIso tt_j2000_to_parsed_utc_iso(double tt_j2000_time) const
	{
		return tai_j2000_to_parsed_utc_iso(tt_j2000_to_tai_j2000(tt_j2000_time));
	}
	std::string
	tt_j2000_to_utc_iso(double tt_j2000_time, bool use_t_separator = false, int fractional_second_places = 3)
		const override
	{
		return parsed_utc_iso_to_utc_iso(
			tt_j2000_to_parsed_utc_iso(tt_j2000_time),
			use_t_separator,
			fractional_second_places
		);
	}
	double tt_j2000_to_posix(double tt_j2000_time) const override
	{
		return tai_j2000_to_posix(tt_j2000_to_tai_j2000(tt_j2000_time));
	}
	double tt_j2000_to_utc_j2000(double tt_j2000_time) const override
	{
		return posix_to_utc_j2000(tt_j2000_to_posix(tt_j2000_time));
	}
	double tt_j2000_to_tdb_j2000(double tt_j2000_time) const override { return tt_j2000_time; }

	std::string tdb_j2000_to_utc_iso(
		double tdb_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override
	{
		return tt_j2000_to_utc_iso(tdb_j2000_time, use_t_separator, fractional_second_places);
	}
	double tdb_j2000_to_posix(double tdb_j2000_time) const override
	{
		return tt_j2000_to_posix(tdb_j2000_time);
	}
	double tdb_j2000_to_utc_j2000(double tdb_j2000_time) const override
	{
		return tt_j2000_to_utc_j2000(tdb_j2000_time);
	}
	double tdb_j2000_to_tai_j2000(double tdb_j2000_time) const override
	{
		return tt_j2000_to_tai_j2000(tdb_j2000_time);
	}
	double tdb_j2000_to_tt_j2000(double tdb_j2000_time) const override { return tdb_j2000_time; }

	bool
	iso_8601_equal(const std::string& lhs, const std::string& rhs, std::size_t fractional_second_places = 3)
		const;

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration> posix_to_sys_time(double posix_time) const
	{
		return std::chrono::sys_time<Duration>{
			std::chrono::duration_cast<Duration>(std::chrono::duration<double>{ posix_time })
		};
	}

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

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration> utc_j2000_to_sys_time(double utc_j2000_time
	) const
	{
		return posix_to_sys_time<Duration>(utc_j2000_to_posix(utc_j2000_time));
	}

#ifdef HAS_CHRONO_UTC_CLOCK
	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration> utc_j2000_to_utc_time(double utc_j2000_time
	) const
	{
		return posix_to_utc_time<Duration>(utc_j2000_to_posix(utc_j2000_time));
	}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration> utc_j2000_to_tai_time(double utc_j2000_time
	) const
	{
		return posix_to_tai_time<Duration>(utc_j2000_to_posix(utc_j2000_time));
	}
#endif

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration> tai_j2000_to_sys_time(double tai_j2000_time
	) const
	{
		return posix_to_sys_time<Duration>(tai_j2000_to_posix(tai_j2000_time));
	}

#ifdef HAS_CHRONO_UTC_CLOCK
	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration> tai_j2000_to_utc_time(double tai_j2000_time
	) const
	{
		return epochs::TAI_J2000_EPOCH_IN_UTC_TIME<Duration>
			+ std::chrono::duration_cast<Duration>(std::chrono::duration<double>{ tai_j2000_time });
	}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
	template <typename Duration = std::chrono::tai_clock::duration>
	std::chrono::time_point<std::chrono::tai_clock, Duration> tai_j2000_to_tai_time(double tai_j2000_time
	) const
	{
		return std::chrono::tai_clock::from_utc(tai_j2000_to_utc_time<Duration>(tai_j2000_time));
	}
#endif

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration> tt_j2000_to_sys_time(double tt_j2000_time
	) const
	{
		return posix_to_sys_time<Duration>(tt_j2000_to_posix(tt_j2000_time));
	}

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

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration> tdb_j2000_to_sys_time(double tdb_j2000_time
	) const
	{
		return posix_to_sys_time<Duration>(tdb_j2000_to_posix(tdb_j2000_time));
	}

#ifdef HAS_CHRONO_UTC_CLOCK
	template <typename Duration = std::chrono::utc_clock::duration>
	std::chrono::time_point<std::chrono::utc_clock, Duration> tdb_j2000_to_utc_time(double tdb_j2000_time
	) const
	{
		return tai_j2000_to_utc_time<Duration>(tdb_j2000_to_tai_j2000(tdb_j2000_time));
	}
#endif

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

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration>
	parsed_utc_iso_to_sys_time(const ParsedUtcIso& parsed_utc_iso) const
	{
		return posix_to_sys_time<Duration>(parsed_utc_iso_to_posix(parsed_utc_iso));
	}

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

	template <typename Duration = std::chrono::system_clock::duration>
	std::chrono::time_point<std::chrono::system_clock, Duration>
	utc_iso_to_sys_time(const std::string& iso_string) const
	{
		return parsed_utc_iso_to_sys_time<Duration>(utc_iso_to_parsed_utc_iso(iso_string));
	}

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

private:
	TimeConverter() = default;
};
