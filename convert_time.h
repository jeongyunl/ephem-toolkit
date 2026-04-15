#pragma once

#include <string>

std::string utc_iso_tudat_to_utc_iso_tudat(const std::string& iso_string);
double utc_iso_tudat_to_utc_posix(const std::string& iso_string);
double utc_iso_tudat_to_utc_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tai_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tt_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tdb_tudat(const std::string& iso_string);
double utc_iso_tudat_to_tdb_apx_tudat(const std::string& iso_string);

std::string utc_posix_to_utc_iso_tudat(double utc_posix_epoch);
double utc_posix_to_utc_posix(double utc_posix_epoch);
double utc_posix_to_utc_tudat(double utc_posix_epoch);
double utc_posix_to_tai_tudat(double utc_posix_epoch);
double utc_posix_to_tt_tudat(double utc_posix_epoch);
double utc_posix_to_tdb_tudat(double utc_posix_epoch);
double utc_posix_to_tdb_apx_tudat(double utc_posix_epoch);

std::string utc_tudat_to_utc_iso_tudat(double utc_tudat_epoch);
double utc_tudat_to_utc_posix(double utc_tudat_epoch);
double utc_tudat_to_utc_tudat(double utc_tudat_epoch);
double utc_tudat_to_tai_tudat(double utc_tudat_epoch);
double utc_tudat_to_tt_tudat(double utc_tudat_epoch);
double utc_tudat_to_tdb_tudat(double utc_tudat_epoch);
double utc_tudat_to_tdb_apx_tudat(double utc_tudat_epoch);

std::string tai_tudat_to_utc_iso_tudat(double tai_tudat_epoch);
double tai_tudat_to_utc_posix(double tai_tudat_epoch);
double tai_tudat_to_utc_tudat(double tai_tudat_epoch);
double tai_tudat_to_tai_tudat(double tai_tudat_epoch);
double tai_tudat_to_tt_tudat(double tai_tudat_epoch);
double tai_tudat_to_tdb_tudat(double tai_tudat_epoch);
double tai_tudat_to_tdb_apx_tudat(double tai_tudat_epoch);

std::string tt_tudat_to_utc_iso_tudat(double tt_tudat_epoch);
double tt_tudat_to_utc_posix(double tt_tudat_epoch);
double tt_tudat_to_utc_tudat(double tt_tudat_epoch);
double tt_tudat_to_tai_tudat(double tt_tudat_epoch);
double tt_tudat_to_tt_tudat(double tt_tudat_epoch);
double tt_tudat_to_tdb_tudat(double tt_tudat_epoch);
double tt_tudat_to_tdb_apx_tudat(double tt_tudat_epoch);

std::string tdb_tudat_to_utc_iso_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_utc_posix(double tdb_tudat_epoch);
double tdb_tudat_to_utc_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_tai_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_tt_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_tdb_tudat(double tdb_tudat_epoch);

std::string tdb_apx_tudat_to_utc_iso_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_utc_posix(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_utc_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tai_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tt_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tdb_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tdb_apx_tudat(double tdb_apx_tudat_epoch);
