#pragma once

#include "convert_time_common.h"

#include <chrono>

// Tudat DateTime based implementations

std::string utc_iso_tudat_to_utc_iso_tudat(const std::string& iso_string);

double utc_iso_tudat_to_utc_posix(const std::string& iso_string);
double utc_iso_tudat_to_utc_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tai_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tt_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tdb_tudat(const std::string& iso_string);

std::string utc_posix_to_utc_iso_tudat(double utc_posix_epoch);
std::string utc_tudat_to_utc_iso_tudat(double utc_tudat_epoch);
std::string tai_tudat_to_utc_iso_tudat(double tai_tudat_epoch);
std::string tt_tudat_to_utc_iso_tudat(double tt_tudat_epoch);
std::string tdb_tudat_to_utc_iso_tudat(double tdb_tudat_epoch);
