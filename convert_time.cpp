#include "convert_time.h"

#include <tudat/astro/basic_astro/dateTime.h>
#include <tudat/astro/earth_orientation/terrestrialTimeScaleConverter.h>

// POSIX epoch (1970-01-01 00:00:00 UTC) minus TUDAT UTC J2000 epoch (2000-01-01 12:00:00 UTC)
constexpr auto POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH = 946728000.0;

// TT epoch (2000-01-01 12:00:00 TT) minus TAI epoch (2000-01-01 12:00:00 TAI)
constexpr auto TT_EPOCH_MINUS_TAI_EPOCH = 32.184;

static std::shared_ptr<tudat::earth_orientation::TerrestrialTimeScaleConverter>
get_tudat_time_scale_converter()
{
	static std::shared_ptr<tudat::earth_orientation::TerrestrialTimeScaleConverter>
		tudat_time_scale_converter = nullptr;

	if(tudat_time_scale_converter != nullptr)
	{
		return tudat_time_scale_converter;
	}

	tudat_time_scale_converter = tudat::earth_orientation::createDefaultTimeConverter();

	return tudat_time_scale_converter;
}

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

double utc_iso_tudat_to_tdb_apx_tudat(const std::string& iso_string)
{
	return utc_iso_tudat_to_tt_tudat(iso_string);
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

double utc_posix_to_utc_posix(const double utc_posix_epoch)
{
	return utc_posix_epoch;
}

double utc_posix_to_utc_tudat(const double utc_posix_epoch)
{
	return utc_posix_epoch - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
}

double utc_posix_to_tai_tudat(const double utc_posix_epoch)
{
	try
	{
		const double utc_tudat_epoch = utc_posix_epoch - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			utc_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_posix_to_tdb_tudat(const double utc_posix_epoch)
{
	try
	{
		const double utc_tudat_epoch = utc_posix_epoch - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			utc_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_posix_to_tt_tudat(const double utc_posix_epoch)
{
	try
	{
		const double utc_tudat_epoch = utc_posix_epoch - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			utc_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_posix_to_tdb_apx_tudat(const double utc_posix_epoch)
{
	return utc_posix_to_tt_tudat(utc_posix_epoch);
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

double utc_tudat_to_utc_posix(const double utc_tudat_epoch)
{
	return utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
}

double utc_tudat_to_utc_tudat(const double utc_tudat_epoch)
{
	return utc_tudat_epoch;
}

double utc_tudat_to_tai_tudat(const double utc_tudat_epoch)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			utc_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_tudat_to_tt_tudat(const double utc_tudat_epoch)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			utc_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_tudat_to_tdb_tudat(const double utc_tudat_epoch)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			utc_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_tudat_to_tdb_apx_tudat(const double utc_tudat_epoch)
{
	return utc_tudat_to_tt_tudat(utc_tudat_epoch);
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

double tai_tudat_to_utc_posix(const double tai_tudat_epoch)
{
	try
	{
		const double utc_tudat_epoch = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tai_tudat_epoch
		);

		return utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to POSIX timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tai_tudat_to_utc_tudat(const double tai_tudat_epoch)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tai_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT UTC timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tai_tudat_to_tai_tudat(const double tai_tudat_epoch)
{
	return tai_tudat_epoch;
}

double tai_tudat_to_tt_tudat(const double tai_tudat_epoch)
{
	return tai_tudat_epoch + TT_EPOCH_MINUS_TAI_EPOCH;
}

double tai_tudat_to_tdb_tudat(const double tai_tudat_epoch)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tai_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tai_tudat_to_tdb_apx_tudat(const double tai_tudat_epoch)
{
	return tai_tudat_to_tt_tudat(tai_tudat_epoch);
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

double tt_tudat_to_utc_posix(const double tt_tudat_epoch)
{
	try
	{
		const double utc_tudat_epoch = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tt_tudat_epoch
		);

		return utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to POSIX timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tt_tudat_to_utc_tudat(const double tt_tudat_epoch)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tt_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT UTC timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tt_tudat_to_tai_tudat(const double tt_tudat_epoch)
{
	return tt_tudat_epoch - TT_EPOCH_MINUS_TAI_EPOCH;
}

double tt_tudat_to_tt_tudat(const double tt_tudat_epoch)
{
	return tt_tudat_epoch;
}

double tt_tudat_to_tdb_tudat(const double tt_tudat_epoch)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tt_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tt_tudat_to_tdb_apx_tudat(const double tt_tudat_epoch)
{
	return tt_tudat_epoch;
}

std::string tdb_tudat_to_utc_iso_tudat(const double tdb_tudat_epoch)
{
	try
	{
		const double utc_tudat_epoch = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
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

double tdb_tudat_to_utc_posix(const double tdb_tudat_epoch)
{
	try
	{
		const double utc_tudat_epoch = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tdb_tudat_epoch
		);

		return utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to POSIX timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tdb_tudat_to_utc_tudat(const double tdb_tudat_epoch)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tdb_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT UTC timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tdb_tudat_to_tai_tudat(const double tdb_tudat_epoch)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tdb_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tdb_tudat_to_tt_tudat(const double tdb_tudat_epoch)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tdb_tudat_epoch
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tdb_tudat_to_tdb_tudat(const double tdb_tudat_epoch)
{
	return tdb_tudat_epoch;
}

double tdb_tudat_to_tdb_apx_tudat(const double tdb_tudat_epoch)
{
	return tdb_tudat_epoch;
}

std::string tdb_apx_tudat_to_utc_iso_tudat(const double tdb_apx_tudat_epoch)
{
	return tt_tudat_to_utc_iso_tudat(tdb_apx_tudat_epoch);
}

double tdb_apx_tudat_to_utc_posix(const double tdb_apx_tudat_epoch)
{
	return tt_tudat_to_utc_posix(tdb_apx_tudat_epoch);
}

double tdb_apx_tudat_to_utc_tudat(const double tdb_apx_tudat_epoch)
{
	return tt_tudat_to_utc_tudat(tdb_apx_tudat_epoch);
}

double tdb_apx_tudat_to_tai_tudat(const double tdb_apx_tudat_epoch)
{
	return tt_tudat_to_tai_tudat(tdb_apx_tudat_epoch);
}

double tdb_apx_tudat_to_tt_tudat(const double tdb_apx_tudat_epoch)
{
	return tdb_apx_tudat_epoch;
}

double tdb_apx_tudat_to_tdb_tudat(const double tdb_apx_tudat_epoch)
{
	return tdb_apx_tudat_epoch;
}

double tdb_apx_tudat_to_tdb_apx_tudat(const double tdb_apx_tudat_epoch)
{
	return tdb_apx_tudat_epoch;
}
