#pragma once

#include <string>

namespace convert_time_tudat
{
// POSIX epoch (1970-01-01 00:00:00 UTC) minus TUDAT UTC J2000 epoch (2000-01-01 12:00:00 UTC)
constexpr auto POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH = 946728000.0;

//
// utc_iso_to_*() functions
//

std::string utc_iso_to_utc_iso(const std::string& iso_string);
double utc_iso_to_posix(const std::string& iso_string);
double utc_iso_to_utc_tudat(const std::string& iso_string);
double utc_iso_to_tai_tudat(const std::string& iso_string);
double utc_iso_to_tt_tudat(const std::string& iso_string);
double utc_iso_to_tdb_tudat(const std::string& iso_string);

//
// posix_to_*() functions
//

std::string posix_to_utc_iso(double posix_time);
inline double posix_to_posix(const double posix_time)
{
	return posix_time;
}
inline double posix_to_utc_tudat(const double posix_time)
{
	return posix_time - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
}
double posix_to_tai_tudat(double posix_time);
double posix_to_tt_tudat(double posix_time);
double posix_to_tdb_tudat(double posix_time);

//
// utc_tudat_to_*() functions
//

std::string utc_tudat_to_utc_iso(double utc_tudat_time);
inline double utc_tudat_to_posix(const double utc_tudat_time)
{
	return utc_tudat_time + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
}
inline double utc_tudat_to_utc_tudat(const double utc_tudat_time)
{
	return utc_tudat_time;
}
double utc_tudat_to_tai_tudat(double utc_tudat_time);
double utc_tudat_to_tt_tudat(double utc_tudat_time);
double utc_tudat_to_tdb_tudat(double utc_tudat_time);

//
// tai_tudat_to_*() functions
//

std::string tai_tudat_to_utc_iso(double tai_tudat_time);
double tai_tudat_to_posix(double tai_tudat_time);
double tai_tudat_to_utc_tudat(double tai_tudat_time);
inline double tai_tudat_to_tai_tudat(const double tai_tudat_time)
{
	return tai_tudat_time;
}
double tai_tudat_to_tt_tudat(double tai_tudat_time);
double tai_tudat_to_tdb_tudat(double tai_tudat_time);

//
// tt_tudat_to_*() functions
//

std::string tt_tudat_to_utc_iso(double tt_tudat_time);
double tt_tudat_to_posix(double tt_tudat_time);
double tt_tudat_to_utc_tudat(double tt_tudat_time);
double tt_tudat_to_tai_tudat(double tt_tudat_time);
inline double tt_tudat_to_tt_tudat(const double tt_tudat_time)
{
	return tt_tudat_time;
}
double tt_tudat_to_tdb_tudat(double tt_tudat_time);

//
// tdb_tudat_to_*() functions
//

std::string tdb_tudat_to_utc_iso(double tdb_tudat_time);
double tdb_tudat_to_posix(double tdb_tudat_time);
double tdb_tudat_to_utc_tudat(double tdb_tudat_time);
double tdb_tudat_to_tai_tudat(double tdb_tudat_time);
double tdb_tudat_to_tt_tudat(double tdb_tudat_time);
inline double tdb_tudat_to_tdb_tudat(const double tdb_tudat_time)
{
	return tdb_tudat_time;
}

} // namespace convert_time_tudat
