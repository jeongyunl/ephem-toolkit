#include "convert_time_utc_iso.h"

#include "convert_time.h"
#include "convert_time_chrono.h"
#include "convert_time_iso8601.h"
#include "convert_time_tudat.h"

#include <tudat/astro/basic_astro/dateTime.h>
#include <tudat/astro/earth_orientation/terrestrialTimeScaleConverter.h>
#include <array>
#include <cctype>
#include <chrono>

double utc_iso_to_utc_posix(const std::string& iso_string)
{
#ifdef HAS_CHRONO_UTC_CLOCK
	std::chrono::system_clock::time_point sys_time;

	const auto utc_time = utc_iso_to_utc_time(iso_string);

	if(std::chrono::get_leap_second_info(utc_time).is_leap_second)
	{
		// For any time point during a leap second, std::chrono::utc_clock::to_sys() returns
		// 23:59:59.999999999.
		// e.g. The time points: 2016-12-31 23:59:60.0, 2016-12-31 23:59:60.1, 2016-12-31 23:59:60.999
		// all map to 2016-12-31 23:59:59.999999999 in sys_time.
		// To get the correct POSIX epoch, we must subtract one second from the UTC time point before
		// conversion, then add it back afterward.
		const auto utc_time_before_leap = utc_time - std::chrono::seconds{ 1 };
		sys_time = std::chrono::utc_clock::to_sys(utc_time_before_leap) + std::chrono::seconds{ 1 };
	}
	else
	{
		sys_time = std::chrono::utc_clock::to_sys(utc_time);
	}

	return std::chrono::duration<double>(sys_time.time_since_epoch()).count();
#else
	const auto sys_time = utc_iso_to_sys_time(iso_string);
	return std::chrono::duration<double>(sys_time.time_since_epoch()).count();
#endif
}

double utc_iso_to_utc_tudat(const std::string& iso_string)
{
	const ParsedUtcIso parsed_utc_iso = parse_iso8601_utc(iso_string);
	const auto sys_time = parsed_utc_iso_to_sys_time(parsed_utc_iso);
	const double posix_seconds = std::chrono::duration<double>(sys_time.time_since_epoch()).count();

	return posix_seconds - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
}

double utc_iso_to_tai_tudat(const std::string& iso_string)
{
	const ParsedUtcIso parsed_utc_iso = parse_iso8601_utc(iso_string);
	const auto sys_time = parsed_utc_iso_to_sys_time(parsed_utc_iso);
	const double posix_epoch = std::chrono::duration<double>(sys_time.time_since_epoch()).count();

	// At 23:59:60, UTC maps to the same POSIX second as 00:00:00 next day.
	// For correct boundary behavior, that leap transition must not be counted yet.
	const bool include_transition_now = (parsed_utc_iso.second != 60);
	const double posix_epoch_for_leap_lookup = (parsed_utc_iso.second == 60)
		? static_cast<double>(
			std::chrono::time_point_cast<std::chrono::seconds>(sys_time).time_since_epoch().count()
		)
		: posix_epoch;
	const double leap_now = cumulative_leap_correction(
		get_zoneinfo_leap_transitions(),
		posix_epoch_for_leap_lookup,
		include_transition_now
	);
	const double leap_epoch = cumulative_leap_correction(
		get_zoneinfo_leap_transitions(),
		static_cast<double>(TAI_J2000_EPOCH_IN_POSIX_TIME),
		true
	);

	const double utc_elapsed_non_leap = posix_epoch - static_cast<double>(TAI_J2000_EPOCH_IN_POSIX_TIME);
	const double leap_delta = leap_now - leap_epoch;

	return utc_elapsed_non_leap + leap_delta;
}

double utc_iso_to_tt_tudat(const std::string& iso_string)
{
	return utc_iso_to_tai_tudat(iso_string) + TT_EPOCH_MINUS_TAI_EPOCH;
}

double utc_iso_to_tdb_tudat(const std::string& iso_string)
{
	// TDB differs from TT in periodic terms, with a difference of at most 2 milliseconds
	// We can ignore that
	return utc_iso_to_tt_tudat(iso_string);
}

std::string utc_posix_to_utc_iso(double utc_posix_epoch)
{
	const auto sys_time = utc_posix_to_sys_time(utc_posix_epoch);

	return sys_time_to_utc_iso(sys_time);
}

std::string utc_tudat_to_utc_iso(double utc_tudat_epoch)
{
	const double utc_posix_epoch = utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;

	return utc_posix_to_utc_iso(utc_posix_epoch);
}

std::string tai_tudat_to_utc_iso(double tai_tudat_epoch)
{
	const double leap_epoch = cumulative_leap_correction(
		get_zoneinfo_leap_transitions(),
		static_cast<double>(TAI_J2000_EPOCH_IN_POSIX_TIME),
		true
	);

	// Monotonically increasing TAI seconds since 1970-01-01 00:00:00 TAI
	const double tai_posix =
		tai_tudat_epoch + static_cast<double>(TAI_J2000_EPOCH_IN_POSIX_TIME) + leap_epoch;

	// Invert TAI POSIX → UTC POSIX via fixed-point iteration.
	// Start conservatively below the correct UTC (TAI - UTC is at most ~50 s historically)
	// and refine upward by re-evaluating the cumulative leap correction at the candidate epoch.
	// Two iterations suffice because transitions are spaced years apart and N < 50 s.
	double utc_posix = tai_posix - 50.0;
	utc_posix = tai_posix - cumulative_leap_correction(get_zoneinfo_leap_transitions(), utc_posix, true);
	utc_posix = tai_posix - cumulative_leap_correction(get_zoneinfo_leap_transitions(), utc_posix, true);

	// Check whether we landed inside a positive leap second.
	// At a leap second transition (UTC 23:59:60), the iteration converges to
	// utc_posix = t + frac  (where t is the POSIX second of 23:59:59)
	// because cumulative(t, true) = N (the new leap not yet counted),
	// leaving residual = tai_posix - (utc_posix + N) == 1 + frac >= 1.
	const double leap_at_utc = cumulative_leap_correction(get_zoneinfo_leap_transitions(), utc_posix, true);
	const double residual = tai_posix - (utc_posix + leap_at_utc);

	if(residual > 1.0 - 1e-9)
	{
		// Inside a positive leap second (23:59:60.xxx).
		// utc_posix = (POSIX second of 23:59:59) + fractional offset within the leap second.
		const double base_posix = static_cast<double>(static_cast<std::int64_t>(utc_posix));
		const double frac_in_leap = utc_posix - base_posix;
		const std::int64_t leap_nanos = static_cast<std::int64_t>(frac_in_leap * 1e9 + 0.5);

		// Format year/month/day/hour/minute from the 23:59:59 base time, then append ":60"
		const auto base_sys_time = utc_posix_to_sys_time<std::chrono::nanoseconds>(base_posix);
		const std::string base_iso = std::format("{:%FT%H:%M:}60", base_sys_time);
		if(leap_nanos > 0)
		{
			return base_iso + std::format(".{:09}", leap_nanos);
		}
		return base_iso;
	}

	// Normal UTC second: convert utc_posix to a sys_time and format as ISO-8601
	return sys_time_to_utc_iso(utc_posix_to_sys_time<std::chrono::nanoseconds>(utc_posix));
}

std::string tt_tudat_to_utc_iso(double tt_tudat_epoch)
{
	return tai_tudat_to_utc_iso(tt_tudat_epoch - TT_EPOCH_MINUS_TAI_EPOCH);
}

std::string tdb_tudat_to_utc_iso(double tdb_tudat_epoch)
{
	return tt_tudat_to_utc_iso(tdb_tudat_epoch);
}

//
// Tudat DateTime based implementations
//

std::string utc_iso_to_utc_iso(const std::string& iso_string)
{
	return iso_string;
}

double utc_iso_tudat_to_utc_posix(const std::string& iso_string)
{
	// Convert ISO 8601 string to POSIX timestamp

	try
	{
		return tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string).epoch<double>()
			+ POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to POSIX timestamp: " << e.what() << "\n";

		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_iso_tudat_to_utc_tudat(const std::string& iso_string)
{
	try
	{
		return tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string).epoch<double>();
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to TUDAT UTC timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}
double utc_iso_tudat_to_tai_tudat(const std::string& iso_string)
{
	try
	{
		const auto tudat_date_time = tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string);
		const double leap_second = (tudat_date_time.getSeconds() >= 60.0) ? 1.0 : 0.0;

		return get_tudat_time_scale_converter()->getCurrentTime(
				   tudat::basic_astrodynamics::TimeScales::utc_scale,
				   tudat::basic_astrodynamics::TimeScales::tai_scale,
				   tudat_date_time.epoch<double>()
			   )
			- leap_second;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_iso_tudat_to_tt_tudat(const std::string& iso_string)
{
	try
	{
		const auto tudat_date_time = tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string);
		const double leap_second = (tudat_date_time.getSeconds() >= 60.0) ? 1.0 : 0.0;

		return get_tudat_time_scale_converter()->getCurrentTime(
				   tudat::basic_astrodynamics::TimeScales::utc_scale,
				   tudat::basic_astrodynamics::TimeScales::tt_scale,
				   tudat_date_time.epoch<double>()
			   )
			- leap_second;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_iso_tudat_to_tdb_tudat(const std::string& iso_string)
{
	try
	{
		const auto tudat_date_time = tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string);
		const double leap_second = (tudat_date_time.getSeconds() >= 60.0) ? 1.0 : 0.0;

		return get_tudat_time_scale_converter()->getCurrentTime(
				   tudat::basic_astrodynamics::TimeScales::utc_scale,
				   tudat::basic_astrodynamics::TimeScales::tdb_scale,
				   tudat_date_time.epoch<double>()
			   )
			- leap_second;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

std::string utc_posix_to_utc_iso_tudat(const double utc_posix_epoch)
{
	try
	{
		const double utc_tudat_epoch = utc_posix_epoch - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_tudat_epoch).isoString(false, 3);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to ISO string: " << e.what() << "\n";
		return "";
	}
}
std::string utc_tudat_to_utc_iso_tudat(const double utc_tudat_epoch)
{
	try
	{
		return tudat::basic_astrodynamics::DateTime::fromTime(utc_tudat_epoch).isoString(false, 3);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to ISO string: " << e.what() << "\n";
		return "";
	}
}
std::string tai_tudat_to_utc_iso_tudat(const double tai_tudat_epoch)
{
	try
	{
		const double utc_tudat_epoch = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tai_tudat_epoch
		);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_tudat_epoch).isoString(false, 3);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT UTC ISO timestamp: " << e.what() << "\n";
		return "";
	}
}
std::string tt_tudat_to_utc_iso_tudat(const double tt_tudat_epoch)
{
	try
	{
		const double utc_tudat_epoch = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tt_tudat_epoch
		);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_tudat_epoch).isoString(false, 3);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT UTC ISO timestamp: " << e.what() << "\n";
		return "";
	}
}
std::string tdb_tudat_to_utc_iso_tudat(const double tdb_tudat_epoch)
{
	try
	{
		const double utc_tudat_epoch = get_tudat_time_scale_converter()->getCurrentTime(
#ifdef TUDAT_BUGGY_TDB_TO_UTC_CONVERSIONS
			tudat::basic_astrodynamics::TimeScales::tt_scale,
#else
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
#endif
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tdb_tudat_epoch
		);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_tudat_epoch).isoString(false, 3);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT UTC ISO timestamp: " << e.what() << "\n";
		return "";
	}
}
