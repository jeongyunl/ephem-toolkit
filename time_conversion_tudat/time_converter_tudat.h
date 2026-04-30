#pragma once

#include <string>

namespace convert_time_tudat
{

class TimeConverterTudat
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

	std::string utc_iso_to_utc_iso(const std::string& iso_string) const;
	double utc_iso_to_posix(const std::string& iso_string) const;
	double utc_iso_to_utc_tudat(const std::string& iso_string) const;
	double utc_iso_to_tai_tudat(const std::string& iso_string) const;
	double utc_iso_to_tt_tudat(const std::string& iso_string) const;
	double utc_iso_to_tdb_tudat(const std::string& iso_string) const;

	std::string posix_to_utc_iso(double posix_time) const;
	double posix_to_posix(const double posix_time) const { return posix_time; }
	double posix_to_utc_tudat(const double posix_time) const
	{
		return posix_time - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
	}
	double posix_to_tai_tudat(double posix_time) const;
	double posix_to_tt_tudat(double posix_time) const;
	double posix_to_tdb_tudat(double posix_time) const;

	std::string utc_tudat_to_utc_iso(double utc_tudat_time) const;
	double utc_tudat_to_posix(const double utc_tudat_time) const
	{
		return utc_tudat_time + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
	}
	double utc_tudat_to_utc_tudat(const double utc_tudat_time) const { return utc_tudat_time; }
	double utc_tudat_to_tai_tudat(double utc_tudat_time) const;
	double utc_tudat_to_tt_tudat(double utc_tudat_time) const;
	double utc_tudat_to_tdb_tudat(double utc_tudat_time) const;

	std::string tai_tudat_to_utc_iso(double tai_tudat_time) const;
	double tai_tudat_to_posix(double tai_tudat_time) const;
	double tai_tudat_to_utc_tudat(double tai_tudat_time) const;
	double tai_tudat_to_tai_tudat(const double tai_tudat_time) const { return tai_tudat_time; }
	double tai_tudat_to_tt_tudat(double tai_tudat_time) const;
	double tai_tudat_to_tdb_tudat(double tai_tudat_time) const;

	std::string tt_tudat_to_utc_iso(double tt_tudat_time) const;
	double tt_tudat_to_posix(double tt_tudat_time) const;
	double tt_tudat_to_utc_tudat(double tt_tudat_time) const;
	double tt_tudat_to_tai_tudat(double tt_tudat_time) const;
	double tt_tudat_to_tt_tudat(const double tt_tudat_time) const { return tt_tudat_time; }
	double tt_tudat_to_tdb_tudat(double tt_tudat_time) const;

	std::string tdb_tudat_to_utc_iso(double tdb_tudat_time) const;
	double tdb_tudat_to_posix(double tdb_tudat_time) const;
	double tdb_tudat_to_utc_tudat(double tdb_tudat_time) const;
	double tdb_tudat_to_tai_tudat(double tdb_tudat_time) const;
	double tdb_tudat_to_tt_tudat(double tdb_tudat_time) const;
	double tdb_tudat_to_tdb_tudat(const double tdb_tudat_time) const { return tdb_tudat_time; }

private:
	TimeConverterTudat() = default;
};

} // namespace convert_time_tudat

