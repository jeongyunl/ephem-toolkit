#include "convert_time_utc_iso.h"

#include "convert_time_tudat.h"

#include <tudat/astro/basic_astro/dateTime.h>
#include <tudat/astro/earth_orientation/terrestrialTimeScaleConverter.h>
#include <array>
#include <cctype>
#include <chrono>

//
// Tudat DateTime based implementations
//

std::string utc_iso_tudat_to_utc_iso_tudat(const std::string& iso_string)
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
