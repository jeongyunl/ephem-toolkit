#pragma once

#include "conversion_wrapper.h"
#include "convert_time_common.h"

#include <string>

class TimeConverter
{
protected:
	std::map<DispatchKey, ConversionWrapper> dispatchTable;

public:
	virtual ~TimeConverter() = default;

	virtual void make_dispatch_table() = 0;

	virtual TimeValue
	convert_time(const TimeValue& input, TimeFormat input_format, TimeFormat output_format) const;

	std::string utc_iso_to_utc_iso(const std::string& iso_string) const { return iso_string; }
	virtual double utc_iso_to_posix(const std::string& iso_string) const = 0;
	virtual double utc_iso_to_utc_j2000(const std::string& iso_string) const = 0;
	virtual double utc_iso_to_tai_j2000(const std::string& iso_string) const = 0;
	virtual double utc_iso_to_tt_j2000(const std::string& iso_string) const = 0;
	virtual double utc_iso_to_tdb_j2000(const std::string& iso_string) const = 0;

	virtual std::string posix_to_utc_iso(
		double posix_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const = 0;
	double posix_to_posix(double posix_time) const { return posix_time; }
	virtual double posix_to_utc_j2000(double posix_time) const = 0;
	virtual double posix_to_tai_j2000(double posix_time) const = 0;
	virtual double posix_to_tt_j2000(double posix_time) const = 0;
	virtual double posix_to_tdb_j2000(double posix_time) const = 0;

	virtual std::string utc_j2000_to_utc_iso(
		double utc_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const = 0;
	virtual double utc_j2000_to_posix(double utc_j2000_time) const = 0;
	double utc_j2000_to_utc_j2000(double utc_j2000_time) const { return utc_j2000_time; }
	virtual double utc_j2000_to_tai_j2000(double utc_j2000_time) const = 0;
	virtual double utc_j2000_to_tt_j2000(double utc_j2000_time) const = 0;
	virtual double utc_j2000_to_tdb_j2000(double utc_j2000_time) const = 0;

	virtual std::string tai_j2000_to_utc_iso(
		double tai_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const = 0;
	virtual double tai_j2000_to_posix(double tai_j2000_time) const = 0;
	virtual double tai_j2000_to_utc_j2000(double tai_j2000_time) const = 0;
	double tai_j2000_to_tai_j2000(double tai_j2000_time) const { return tai_j2000_time; }
	virtual double tai_j2000_to_tt_j2000(double tai_j2000_time) const = 0;
	virtual double tai_j2000_to_tdb_j2000(double tai_j2000_time) const = 0;

	virtual std::string tt_j2000_to_utc_iso(
		double tt_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const = 0;
	virtual double tt_j2000_to_posix(double tt_j2000_time) const = 0;
	virtual double tt_j2000_to_utc_j2000(double tt_j2000_time) const = 0;
	virtual double tt_j2000_to_tai_j2000(double tt_j2000_time) const = 0;
	double tt_j2000_to_tt_j2000(double tt_j2000_time) const { return tt_j2000_time; }
	virtual double tt_j2000_to_tdb_j2000(double tt_j2000_time) const = 0;

	virtual std::string tdb_j2000_to_utc_iso(
		double tdb_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const = 0;
	virtual double tdb_j2000_to_posix(double tdb_j2000_time) const = 0;
	virtual double tdb_j2000_to_utc_j2000(double tdb_j2000_time) const = 0;
	virtual double tdb_j2000_to_tai_j2000(double tdb_j2000_time) const = 0;
	virtual double tdb_j2000_to_tt_j2000(double tdb_j2000_time) const = 0;
	double tdb_j2000_to_tdb_j2000(double tdb_j2000_time) const { return tdb_j2000_time; }
};
