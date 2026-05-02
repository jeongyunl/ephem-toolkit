#pragma once

#include "convert_time_epochs.h"
#include "convert_time_iso8601.h"
#include "time_converter.h"

#include <format>
#include <string>

class TimeConverterBase : public TimeConverter
{
protected:
	TimeConverterBase() = default;

public:
	TimeConverterBase(const TimeConverterBase&) = delete;
	TimeConverterBase& operator=(const TimeConverterBase&) = delete;
	TimeConverterBase(TimeConverterBase&&) = delete;
	TimeConverterBase& operator=(TimeConverterBase&&) = delete;

	static TimeConverterBase& instance()
	{
		static TimeConverterBase singleton;
		return singleton;
	}

	TimeValue
	convert_time(const TimeValue& input, TimeFormat input_format, TimeFormat output_format) const override;

	bool
	iso_8601_equal(const std::string& lhs, const std::string& rhs, std::size_t fractional_second_places = 3)
		const;

	//
	// parsed_utc_iso_to_*() functions
	//

	std::string parsed_utc_iso_to_utc_iso(
		const ParsedUtcIso& parsed_utc_iso,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const;

	double parsed_utc_iso_to_posix(const ParsedUtcIso& parsed_utc_iso) const;

	double parsed_utc_iso_to_utc_j2000(const ParsedUtcIso& parsed_utc_iso) const
	{
		return posix_to_utc_j2000(parsed_utc_iso_to_posix(parsed_utc_iso));
	}

	virtual double parsed_utc_iso_to_tai_j2000(const ParsedUtcIso& parsed_utc_iso) const;

	double parsed_utc_iso_to_tt_j2000(const ParsedUtcIso& parsed_utc_iso) const
	{
		return tai_j2000_to_tt_j2000(parsed_utc_iso_to_tai_j2000(parsed_utc_iso));
	}

	//
	// utc_iso_to_*() functions
	//

	ParsedUtcIso utc_iso_to_parsed_utc_iso(const std::string& utc_iso) const;

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

	//
	// posix_to_*() functions
	//

	ParsedUtcIso posix_to_parsed_utc_iso(double posix_time) const;

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

	double posix_to_utc_j2000(double posix_time) const override
	{
		return posix_time - static_cast<double>(epochs::UTC_J2000_EPOCH_IN_POSIX_TIME);
	}

	double posix_to_tai_j2000(double posix_time) const override;

	double posix_to_tt_j2000(double posix_time) const override
	{
		return tai_j2000_to_tt_j2000(posix_to_tai_j2000(posix_time));
	}

	double posix_to_tdb_j2000(double posix_time) const override { return posix_to_tt_j2000(posix_time); }

	//
	// utc_j2000_to_*() functions
	//

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

	double utc_j2000_to_posix(double utc_j2000_time) const override
	{
		return utc_j2000_time + static_cast<double>(epochs::UTC_J2000_EPOCH_IN_POSIX_TIME);
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

	//
	// tai_j2000_to_*() functions
	//

	virtual ParsedUtcIso tai_j2000_to_parsed_utc_iso(double tai_j2000_time) const;

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

	double tai_j2000_to_posix(double tai_j2000_time) const override;

	double tai_j2000_to_utc_j2000(double tai_j2000_time) const override
	{
		return posix_to_utc_j2000(tai_j2000_to_posix(tai_j2000_time));
	}
	double tai_j2000_to_tt_j2000(double tai_j2000_time) const override
	{
		return tai_j2000_time + TT_MINUS_TAI;
	}

	double tai_j2000_to_tdb_j2000(double tai_j2000_time) const override
	{
		return tai_j2000_to_tt_j2000(tai_j2000_time);
	}

	//
	// tt_j2000_to_*() functions
	//

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

	double tt_j2000_to_tai_j2000(double tt_j2000_time) const override { return tt_j2000_time - TT_MINUS_TAI; }

	double tt_j2000_to_tdb_j2000(double tt_j2000_time) const override { return tt_j2000_time; }

	//
	// tdb_j2000_to_*() functions
	//

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
};
