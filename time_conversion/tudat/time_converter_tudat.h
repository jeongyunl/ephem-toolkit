#pragma once

#include "../convert_time_common.h"
#include "../convert_time_epochs.h"
#include "../time_converter.h"

class TimeConverterTudat : public TimeConverter
{
private:
	TimeConverterTudat() = default;
	~TimeConverterTudat() = default;

public:
	TimeConverterTudat(const TimeConverterTudat&) = delete;
	TimeConverterTudat& operator=(const TimeConverterTudat&) = delete;
	TimeConverterTudat(TimeConverterTudat&&) = delete;
	TimeConverterTudat& operator=(TimeConverterTudat&&) = delete;

	static TimeConverterTudat& instance()
	{
		static TimeConverterTudat singleton;
		return singleton;
	}

	void make_dispatch_table() override;

	double utc_iso_to_posix(const std::string& iso_string) const override;
	double utc_iso_to_utc_j2000(const std::string& iso_string) const override;
	double utc_iso_to_tai_j2000(const std::string& iso_string) const override;
	double utc_iso_to_tt_j2000(const std::string& iso_string) const override;
	double utc_iso_to_tdb_j2000(const std::string& iso_string) const override;

	std::string posix_to_utc_iso(
		double posix_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override;
	double posix_to_utc_j2000(double posix_time) const override
	{
		return posix_time - epochs::UTC_J2000_EPOCH_IN_POSIX_TIME;
	}
	double posix_to_tai_j2000(double posix_time) const override;
	double posix_to_tt_j2000(double posix_time) const override;
	double posix_to_tdb_j2000(double posix_time) const override;

	std::string utc_j2000_to_utc_iso(
		double utc_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override;
	double utc_j2000_to_posix(const double utc_j2000_time) const override
	{
		return utc_j2000_time + epochs::UTC_J2000_EPOCH_IN_POSIX_TIME;
	}
	double utc_j2000_to_tai_j2000(double utc_j2000_time) const override;
	double utc_j2000_to_tt_j2000(double utc_j2000_time) const override;
	double utc_j2000_to_tdb_j2000(double utc_j2000_time) const override;

	std::string tai_j2000_to_utc_iso(
		double tai_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override;
	double tai_j2000_to_posix(double tai_j2000_time) const override;
	double tai_j2000_to_utc_j2000(double tai_j2000_time) const override;
	double tai_j2000_to_tt_j2000(double tai_j2000_time) const override;
	double tai_j2000_to_tdb_j2000(double tai_j2000_time) const override;

	std::string tt_j2000_to_utc_iso(
		double tt_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override;
	double tt_j2000_to_posix(double tt_j2000_time) const override;
	double tt_j2000_to_utc_j2000(double tt_j2000_time) const override;
	double tt_j2000_to_tai_j2000(double tt_j2000_time) const override;
	double tt_j2000_to_tdb_j2000(double tt_j2000_time) const override;

	std::string tdb_j2000_to_utc_iso(
		double tdb_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const override;
	double tdb_j2000_to_posix(double tdb_j2000_time) const override;
	double tdb_j2000_to_utc_j2000(double tdb_j2000_time) const override;
	double tdb_j2000_to_tai_j2000(double tdb_j2000_time) const override;
	double tdb_j2000_to_tt_j2000(double tdb_j2000_time) const override;
};
