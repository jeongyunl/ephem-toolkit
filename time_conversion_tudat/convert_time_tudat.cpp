#include "convert_time_tudat.h"

#include <tudat/astro/basic_astro/dateTime.h>
#include <tudat/astro/earth_orientation/terrestrialTimeScaleConverter.h>

namespace
{

std::shared_ptr<tudat::earth_orientation::TerrestrialTimeScaleConverter> get_tudat_time_scale_converter()
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
} // namespace

namespace convert_time_tudat
{

//
// utc_iso_to_*() functions
//

std::string utc_iso_to_utc_iso(const std::string& iso_string)
{
	return iso_string;
}

double utc_iso_to_posix(const std::string& iso_string)
{
	// Convert ISO 8601 string to POSIX timestamp

	try
	{
		return utc_tudat_to_posix(
			tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string).epoch<double>()
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to POSIX timestamp: " << e.what() << "\n";

		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_iso_to_utc_tudat(const std::string& iso_string)
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
double utc_iso_to_tai_tudat(const std::string& iso_string)
{
	try
	{
		const auto tudat_date_time = tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string);

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat_date_time.epoch<double>()
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_iso_to_tt_tudat(const std::string& iso_string)
{
	try
	{
		const auto tudat_date_time = tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string);

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat_date_time.epoch<double>()
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_iso_to_tdb_tudat(const std::string& iso_string)
{
	try
	{
		const auto tudat_date_time = tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string);

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat_date_time.epoch<double>()
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

//
// posix_to_*() functions
//

std::string posix_to_utc_iso(const double posix_time)
{
	try
	{
		const double utc_tudat_time = posix_to_utc_tudat(posix_time);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_tudat_time).isoString(false, 3);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to ISO string: " << e.what() << "\n";
		return "";
	}
}

double posix_to_tai_tudat(const double posix_time)
{
	try
	{
		const double utc_tudat_time = posix_to_utc_tudat(posix_time);

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			utc_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double posix_to_tt_tudat(const double posix_time)
{
	try
	{
		const double utc_tudat_time = posix_to_utc_tudat(posix_time);

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			utc_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double posix_to_tdb_tudat(const double posix_time)
{
	try
	{
		const double utc_tudat_time = posix_to_utc_tudat(posix_time);

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			utc_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

//
// utc_tudat_to_*() functions
//

std::string utc_tudat_to_utc_iso(const double utc_tudat_time)
{
	try
	{
		return tudat::basic_astrodynamics::DateTime::fromTime(utc_tudat_time).isoString(false, 3);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to ISO string: " << e.what() << "\n";
		return "";
	}
}

double utc_tudat_to_tai_tudat(const double utc_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			utc_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_tudat_to_tt_tudat(const double utc_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			utc_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_tudat_to_tdb_tudat(const double utc_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			utc_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

//
// tai_tudat_to_*() functions
//

std::string tai_tudat_to_utc_iso(const double tai_tudat_time)
{
	try
	{
		const double utc_tudat_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tai_tudat_time
		);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_tudat_time).isoString(false, 3);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT UTC ISO timestamp: " << e.what() << "\n";
		return "";
	}
}

double tai_tudat_to_posix(const double tai_tudat_time)
{
	try
	{
		const double utc_tudat_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tai_tudat_time
		);

		return utc_tudat_to_posix(utc_tudat_time);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to POSIX timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tai_tudat_to_utc_tudat(const double tai_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tai_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT UTC timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tai_tudat_to_tt_tudat(const double tai_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tai_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tai_tudat_to_tdb_tudat(const double tai_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tai_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

//
// tt_tudat_to_*() functions
//

std::string tt_tudat_to_utc_iso(const double tt_tudat_time)
{
	try
	{
		const double utc_tudat_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tt_tudat_time
		);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_tudat_time).isoString(false, 3);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT UTC ISO timestamp: " << e.what() << "\n";
		return "";
	}
}

double tt_tudat_to_posix(const double tt_tudat_time)
{
	try
	{
		const double utc_tudat_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tt_tudat_time
		);

		return utc_tudat_to_posix(utc_tudat_time);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to POSIX timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tt_tudat_to_utc_tudat(const double tt_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tt_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT UTC timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tt_tudat_to_tai_tudat(const double tt_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tt_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tt_tudat_to_tdb_tudat(const double tt_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tt_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

//
// tdb_tudat_to_*() functions
//

std::string tdb_tudat_to_utc_iso(const double tdb_tudat_time)
{
	try
	{
		const double utc_tudat_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tdb_tudat_time
		);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_tudat_time).isoString(false, 3);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT UTC ISO timestamp: " << e.what() << "\n";
		return "";
	}
}

double tdb_tudat_to_posix(const double tdb_tudat_time)
{
	try
	{
		const double utc_tudat_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tdb_tudat_time
		);

		return utc_tudat_to_posix(utc_tudat_time);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to POSIX timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tdb_tudat_to_utc_tudat(const double tdb_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tdb_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT UTC timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tdb_tudat_to_tai_tudat(const double tdb_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tdb_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double tdb_tudat_to_tt_tudat(const double tdb_tudat_time)
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tdb_tudat_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

} // namespace convert_time_tudat
