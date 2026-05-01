#pragma once

#include <string>

class TimeConverterBase
{
public:
	virtual ~TimeConverterBase() = default;

	virtual std::string utc_iso_to_utc_iso(const std::string& iso_string) const = 0;
	virtual double utc_iso_to_posix(const std::string& iso_string) const = 0;
	virtual double utc_iso_to_utc_j2000(const std::string& iso_string) const = 0;
	virtual double utc_iso_to_tai_j2000(const std::string& iso_string) const = 0;
	virtual double utc_iso_to_tt_j2000(const std::string& iso_string) const = 0;
	virtual double utc_iso_to_tdb_j2000(const std::string& iso_string) const = 0;

	virtual double posix_to_posix(double posix_time) const = 0;
	virtual double posix_to_utc_j2000(double posix_time) const = 0;
	virtual double posix_to_tai_j2000(double posix_time) const = 0;
	virtual double posix_to_tt_j2000(double posix_time) const = 0;
	virtual double posix_to_tdb_j2000(double posix_time) const = 0;
	virtual std::string posix_to_utc_iso(
		double posix_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const = 0;

	virtual double utc_j2000_to_posix(double utc_j2000_time) const = 0;
	virtual double utc_j2000_to_utc_j2000(double utc_j2000_time) const = 0;
	virtual double utc_j2000_to_tai_j2000(double utc_j2000_time) const = 0;
	virtual double utc_j2000_to_tt_j2000(double utc_j2000_time) const = 0;
	virtual double utc_j2000_to_tdb_j2000(double utc_j2000_time) const = 0;
	virtual std::string utc_j2000_to_utc_iso(
		double utc_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const = 0;

	virtual double tai_j2000_to_posix(double tai_j2000_time) const = 0;
	virtual double tai_j2000_to_utc_j2000(double tai_j2000_time) const = 0;
	virtual double tai_j2000_to_tai_j2000(double tai_j2000_time) const = 0;
	virtual double tai_j2000_to_tt_j2000(double tai_j2000_time) const = 0;
	virtual double tai_j2000_to_tdb_j2000(double tai_j2000_time) const = 0;
	virtual std::string tai_j2000_to_utc_iso(
		double tai_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const = 0;

	virtual double tt_j2000_to_posix(double tt_j2000_time) const = 0;
	virtual double tt_j2000_to_utc_j2000(double tt_j2000_time) const = 0;
	virtual double tt_j2000_to_tai_j2000(double tt_j2000_time) const = 0;
	virtual double tt_j2000_to_tt_j2000(double tt_j2000_time) const = 0;
	virtual double tt_j2000_to_tdb_j2000(double tt_j2000_time) const = 0;
	virtual std::string tt_j2000_to_utc_iso(
		double tt_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const = 0;

	virtual double tdb_j2000_to_posix(double tdb_j2000_time) const = 0;
	virtual double tdb_j2000_to_utc_j2000(double tdb_j2000_time) const = 0;
	virtual double tdb_j2000_to_tai_j2000(double tdb_j2000_time) const = 0;
	virtual double tdb_j2000_to_tt_j2000(double tdb_j2000_time) const = 0;
	virtual double tdb_j2000_to_tdb_j2000(double tdb_j2000_time) const = 0;
	virtual std::string tdb_j2000_to_utc_iso(
		double tdb_j2000_time,
		bool use_t_separator = false,
		int fractional_second_places = 3
	) const = 0;
};
