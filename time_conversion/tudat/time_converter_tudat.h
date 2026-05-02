#pragma once

#include "../convert_time_common.h"
#include "../time_converter.h"

#include <string>
#include <variant>

class TimeConverterTudat : public TimeConverter
{
public:
	static TimeConverterTudat& instance()
	{
		static TimeConverterTudat singleton;
		return singleton;
	}

	TimeConverterTudat(const TimeConverterTudat&) = delete;
	TimeConverterTudat& operator=(const TimeConverterTudat&) = delete;
	TimeConverterTudat(TimeConverterTudat&&) = delete;
	TimeConverterTudat& operator=(TimeConverterTudat&&) = delete;

	static constexpr double POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH = 946728000.0;

	double utc_iso_to_posix(const std::string& iso_string) const override;
	double utc_iso_to_utc_j2000(const std::string& iso_string) const override;
	double utc_iso_to_tai_j2000(const std::string& iso_string) const override;
	double utc_iso_to_tt_j2000(const std::string& iso_string) const override;
	double utc_iso_to_tdb_j2000(const std::string& iso_string) const override;

	std::string
	posix_to_utc_iso(double posix_time, bool use_t_separator = false, int fractional_second_places = 3)
		const override;
	double posix_to_utc_j2000(double posix_time) const override
	{
		return posix_time - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
	}
	double posix_to_tai_j2000(double posix_time) const override;
	double posix_to_tt_j2000(double posix_time) const override;
	double posix_to_tdb_j2000(double posix_time) const override;

	std::string utc_j2000_to_utc_iso(
		double utc_tudat_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override;
	double utc_j2000_to_posix(const double utc_tudat_time) const override
	{
		return utc_tudat_time + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
	}
	double utc_j2000_to_tai_j2000(double utc_tudat_time) const override;
	double utc_j2000_to_tt_j2000(double utc_tudat_time) const override;
	double utc_j2000_to_tdb_j2000(double utc_tudat_time) const override;

	std::string tai_j2000_to_utc_iso(
		double tai_tudat_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override;
	double tai_j2000_to_posix(double tai_tudat_time) const override;
	double tai_j2000_to_utc_j2000(double tai_tudat_time) const override;
	double tai_j2000_to_tt_j2000(double tai_tudat_time) const override;
	double tai_j2000_to_tdb_j2000(double tai_tudat_time) const override;

	std::string
	tt_j2000_to_utc_iso(double tt_tudat_time, bool use_t_separator = false, int fractional_second_places = 3)
		const override;
	double tt_j2000_to_posix(double tt_tudat_time) const override;
	double tt_j2000_to_utc_j2000(double tt_tudat_time) const override;
	double tt_j2000_to_tai_j2000(double tt_tudat_time) const override;
	double tt_j2000_to_tdb_j2000(double tt_tudat_time) const override;

	std::string tdb_j2000_to_utc_iso(
		double tdb_tudat_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override;
	double tdb_j2000_to_posix(double tdb_tudat_time) const override;
	double tdb_j2000_to_utc_j2000(double tdb_tudat_time) const override;
	double tdb_j2000_to_tai_j2000(double tdb_tudat_time) const override;
	double tdb_j2000_to_tt_j2000(double tdb_tudat_time) const override;

private:
	TimeConverterTudat() = default;

public:
	TimeValue convert_time(const TimeValue& input, TimeFormat input_format, TimeFormat output_format) const;
};
