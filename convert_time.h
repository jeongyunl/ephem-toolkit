#pragma once

#include <string>
#include <type_traits>

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
double tdb_tudat_to_tdb_apx_tudat(double tdb_tudat_epoch);

std::string tdb_apx_tudat_to_utc_iso_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_utc_posix(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_utc_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tai_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tt_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tdb_tudat(double tdb_apx_tudat_epoch);
double tdb_apx_tudat_to_tdb_apx_tudat(double tdb_apx_tudat_epoch);

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

template <auto>
inline constexpr bool always_false_v = false;

template <TimeFormat In, TimeFormat Out>
auto convert_time(std::conditional_t<In == TimeFormat::UTC_ISO_TUDAT, const std::string&, double> input)
	-> std::conditional_t<Out == TimeFormat::UTC_ISO_TUDAT, std::string, double>
{
	if constexpr(In == TimeFormat::UTC_ISO_TUDAT)
	{
		if constexpr(Out == TimeFormat::UTC_ISO_TUDAT)
		{
			return utc_iso_tudat_to_utc_iso_tudat(input);
		}
		else if constexpr(Out == TimeFormat::UTC_POSIX)
		{
			return utc_iso_tudat_to_utc_posix(input);
		}
		else if constexpr(Out == TimeFormat::UTC_TUDAT)
		{
			return utc_iso_tudat_to_utc_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TAI_TUDAT)
		{
			return utc_iso_tudat_to_tai_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TT_TUDAT)
		{
			return utc_iso_tudat_to_tt_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_TUDAT)
		{
			return utc_iso_tudat_to_tdb_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_APX_TUDAT)
		{
			return utc_iso_tudat_to_tdb_apx_tudat(input);
		}
		else
		{
			static_assert(always_false_v<Out>, "Unsupported output TimeFormat");
		}
	}
	else if constexpr(In == TimeFormat::UTC_POSIX)
	{
		if constexpr(Out == TimeFormat::UTC_ISO_TUDAT)
		{
			return utc_posix_to_utc_iso_tudat(input);
		}
		else if constexpr(Out == TimeFormat::UTC_POSIX)
		{
			return utc_posix_to_utc_posix(input);
		}
		else if constexpr(Out == TimeFormat::UTC_TUDAT)
		{
			return utc_posix_to_utc_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TAI_TUDAT)
		{
			return utc_posix_to_tai_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TT_TUDAT)
		{
			return utc_posix_to_tt_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_TUDAT)
		{
			return utc_posix_to_tdb_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_APX_TUDAT)
		{
			return utc_posix_to_tdb_apx_tudat(input);
		}
		else
		{
			static_assert(always_false_v<Out>, "Unsupported output TimeFormat");
		}
	}
	else if constexpr(In == TimeFormat::UTC_TUDAT)
	{
		if constexpr(Out == TimeFormat::UTC_ISO_TUDAT)
		{
			return utc_tudat_to_utc_iso_tudat(input);
		}
		else if constexpr(Out == TimeFormat::UTC_POSIX)
		{
			return utc_tudat_to_utc_posix(input);
		}
		else if constexpr(Out == TimeFormat::UTC_TUDAT)
		{
			return utc_tudat_to_utc_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TAI_TUDAT)
		{
			return utc_tudat_to_tai_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TT_TUDAT)
		{
			return utc_tudat_to_tt_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_TUDAT)
		{
			return utc_tudat_to_tdb_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_APX_TUDAT)
		{
			return utc_tudat_to_tdb_apx_tudat(input);
		}
		else
		{
			static_assert(always_false_v<Out>, "Unsupported output TimeFormat");
		}
	}
	else if constexpr(In == TimeFormat::TAI_TUDAT)
	{
		if constexpr(Out == TimeFormat::UTC_ISO_TUDAT)
		{
			return tai_tudat_to_utc_iso_tudat(input);
		}
		else if constexpr(Out == TimeFormat::UTC_POSIX)
		{
			return tai_tudat_to_utc_posix(input);
		}
		else if constexpr(Out == TimeFormat::UTC_TUDAT)
		{
			return tai_tudat_to_utc_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TAI_TUDAT)
		{
			return tai_tudat_to_tai_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TT_TUDAT)
		{
			return tai_tudat_to_tt_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_TUDAT)
		{
			return tai_tudat_to_tdb_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_APX_TUDAT)
		{
			return tai_tudat_to_tdb_apx_tudat(input);
		}
		else
		{
			static_assert(always_false_v<Out>, "Unsupported output TimeFormat");
		}
	}
	else if constexpr(In == TimeFormat::TT_TUDAT)
	{
		if constexpr(Out == TimeFormat::UTC_ISO_TUDAT)
		{
			return tt_tudat_to_utc_iso_tudat(input);
		}
		else if constexpr(Out == TimeFormat::UTC_POSIX)
		{
			return tt_tudat_to_utc_posix(input);
		}
		else if constexpr(Out == TimeFormat::UTC_TUDAT)
		{
			return tt_tudat_to_utc_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TAI_TUDAT)
		{
			return tt_tudat_to_tai_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TT_TUDAT)
		{
			return tt_tudat_to_tt_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_TUDAT)
		{
			return tt_tudat_to_tdb_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_APX_TUDAT)
		{
			return tt_tudat_to_tdb_apx_tudat(input);
		}
		else
		{
			static_assert(always_false_v<Out>, "Unsupported output TimeFormat");
		}
	}
	else if constexpr(In == TimeFormat::TDB_TUDAT)
	{
		if constexpr(Out == TimeFormat::UTC_ISO_TUDAT)
		{
			return tdb_tudat_to_utc_iso_tudat(input);
		}
		else if constexpr(Out == TimeFormat::UTC_POSIX)
		{
			return tdb_tudat_to_utc_posix(input);
		}
		else if constexpr(Out == TimeFormat::UTC_TUDAT)
		{
			return tdb_tudat_to_utc_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TAI_TUDAT)
		{
			return tdb_tudat_to_tai_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TT_TUDAT)
		{
			return tdb_tudat_to_tt_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_TUDAT)
		{
			return tdb_tudat_to_tdb_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_APX_TUDAT)
		{
			return tdb_tudat_to_tdb_apx_tudat(input);
		}
		else
		{
			static_assert(always_false_v<Out>, "Unsupported output TimeFormat");
		}
	}
	else if constexpr(In == TimeFormat::TDB_APX_TUDAT)
	{
		if constexpr(Out == TimeFormat::UTC_ISO_TUDAT)
		{
			return tdb_apx_tudat_to_utc_iso_tudat(input);
		}
		else if constexpr(Out == TimeFormat::UTC_POSIX)
		{
			return tdb_apx_tudat_to_utc_posix(input);
		}
		else if constexpr(Out == TimeFormat::UTC_TUDAT)
		{
			return tdb_apx_tudat_to_utc_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TAI_TUDAT)
		{
			return tdb_apx_tudat_to_tai_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TT_TUDAT)
		{
			return tdb_apx_tudat_to_tt_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_TUDAT)
		{
			return tdb_apx_tudat_to_tdb_tudat(input);
		}
		else if constexpr(Out == TimeFormat::TDB_APX_TUDAT)
		{
			return tdb_apx_tudat_to_tdb_apx_tudat(input);
		}
		else
		{
			static_assert(always_false_v<Out>, "Unsupported output TimeFormat");
		}
	}
	else
	{
		static_assert(always_false_v<In>, "Unsupported input TimeFormat");
	}
}
