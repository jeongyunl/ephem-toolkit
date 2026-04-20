#pragma once

#include "convert_time_common.h"
#include "convert_time_utc_iso.h"

#include <chrono>

double utc_posix_to_utc_posix(double utc_posix_epoch);
double utc_posix_to_utc_tudat(double utc_posix_epoch);
double utc_posix_to_tai_tudat(double utc_posix_epoch);
double utc_posix_to_tt_tudat(double utc_posix_epoch);
double utc_posix_to_tdb_tudat(double utc_posix_epoch);

double utc_tudat_to_utc_posix(double utc_tudat_epoch);
double utc_tudat_to_utc_tudat(double utc_tudat_epoch);
double utc_tudat_to_tai_tudat(double utc_tudat_epoch);
double utc_tudat_to_tt_tudat(double utc_tudat_epoch);
double utc_tudat_to_tdb_tudat(double utc_tudat_epoch);

double tai_tudat_to_utc_posix(double tai_tudat_epoch);
double tai_tudat_to_utc_tudat(double tai_tudat_epoch);
double tai_tudat_to_tai_tudat(double tai_tudat_epoch);
double tai_tudat_to_tt_tudat(double tai_tudat_epoch);
double tai_tudat_to_tdb_tudat(double tai_tudat_epoch);

double tt_tudat_to_utc_posix(double tt_tudat_epoch);
double tt_tudat_to_utc_tudat(double tt_tudat_epoch);
double tt_tudat_to_tai_tudat(double tt_tudat_epoch);
double tt_tudat_to_tt_tudat(double tt_tudat_epoch);
double tt_tudat_to_tdb_tudat(double tt_tudat_epoch);

double tdb_tudat_to_utc_posix(double tdb_tudat_epoch);
double tdb_tudat_to_utc_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_tai_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_tt_tudat(double tdb_tudat_epoch);
double tdb_tudat_to_tdb_tudat(double tdb_tudat_epoch);

enum class TimeFormat
{
	UNKNOWN = -1,
	UTC_ISO_TUDAT = 0, // ISO 8601 format in UTC: "YYYY-MM-DDTHH:MM:SS.sss"
	UTC_POSIX, // POSIX timestamp; in seconds since 1970-01-01 00:00:00 UTC
	UTC_TUDAT, // Time in UTC; in seconds since UTC J2000 epoch (2000-01-01 12:00:00.000 UTC)
	TAI_TUDAT, // Time in TAI; in seconds since TAI J2000 epoch (2000-01-01 12:00:00.000 TAI =
			   // 2000-01-01 11:59:28 UTC)
	TT_TUDAT, // Terrestial Time; in seconds since TT J2000 epoch (2000-01-01 12:00:00.000 TT =
			  // 2000-01-01 11:58:55.816 UTC)
	TDB_TUDAT, // Barycentric Dynamical Time; in seconds since TDB J2000 epoch (2000-01-01
			   // 12:00:00.000 TDB ≈ 2000-01-01 11:58:55.816 UTC)
	TDB_APX_TUDAT, // Approximate TDB J2000 epoch
};
