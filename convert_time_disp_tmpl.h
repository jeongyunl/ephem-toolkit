#pragma once

#include "convert_time.h"

template <auto>
inline constexpr bool always_false_v = false;

// Compile-time-based time conversion (input and output formats are template arguments)
// Input must be std::string if In is UTC_ISO_TUDAT, otherwise double
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
