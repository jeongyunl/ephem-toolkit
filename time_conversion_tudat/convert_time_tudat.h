#pragma once

#include <string>

namespace convert_time_tudat
{
std::string utc_iso_to_utc_iso(const std::string& iso_string);
double utc_iso_to_posix(const std::string& iso_string);
double utc_iso_to_utc_tudat(const std::string& iso_string);
double utc_iso_to_tai_tudat(const std::string& iso_string);
double utc_iso_to_tt_tudat(const std::string& iso_string);
double utc_iso_to_tdb_tudat(const std::string& iso_string);

std::string posix_to_utc_iso(double posix_time);
double posix_to_posix(double posix_time);
double posix_to_utc_tudat(double posix_time);
double posix_to_tai_tudat(double posix_time);
double posix_to_tt_tudat(double posix_time);
double posix_to_tdb_tudat(double posix_time);

std::string utc_tudat_to_utc_iso(double utc_tudat_time);
double utc_tudat_to_posix(double utc_tudat_time);
double utc_tudat_to_utc_tudat(double utc_tudat_time);
double utc_tudat_to_tai_tudat(double utc_tudat_time);
double utc_tudat_to_tt_tudat(double utc_tudat_time);
double utc_tudat_to_tdb_tudat(double utc_tudat_time);

std::string tai_tudat_to_utc_iso(double tai_tudat_time);
double tai_tudat_to_posix(double tai_tudat_time);
double tai_tudat_to_utc_tudat(double tai_tudat_time);
double tai_tudat_to_tai_tudat(double tai_tudat_time);
double tai_tudat_to_tt_tudat(double tai_tudat_time);
double tai_tudat_to_tdb_tudat(double tai_tudat_time);

std::string tt_tudat_to_utc_iso(double tt_tudat_time);
double tt_tudat_to_posix(double tt_tudat_time);
double tt_tudat_to_utc_tudat(double tt_tudat_time);
double tt_tudat_to_tai_tudat(double tt_tudat_time);
double tt_tudat_to_tt_tudat(double tt_tudat_time);
double tt_tudat_to_tdb_tudat(double tt_tudat_time);

std::string tdb_tudat_to_utc_iso(double tdb_tudat_time);
double tdb_tudat_to_posix(double tdb_tudat_time);
double tdb_tudat_to_utc_tudat(double tdb_tudat_time);
double tdb_tudat_to_tai_tudat(double tdb_tudat_time);
double tdb_tudat_to_tt_tudat(double tdb_tudat_time);
double tdb_tudat_to_tdb_tudat(double tdb_tudat_time);

} // namespace convert_time_tudat
