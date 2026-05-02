#include "time_converter_tudat.h"

#include <tudat/astro/basic_astro/dateTime.h>
#include <tudat/astro/earth_orientation/terrestrialTimeScaleConverter.h>
#include <iostream>
#include <limits>
#include <memory>

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

//
// utc_iso_to_*() functions
//

double TimeConverterTudat::utc_iso_to_posix(const std::string& iso_string) const
{
	// Convert ISO 8601 string to POSIX timestamp

	try
	{
		return utc_j2000_to_posix(
			tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string).epoch<double>()
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to POSIX timestamp: " << e.what() << "\n";

		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::utc_iso_to_utc_j2000(const std::string& iso_string) const
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
double TimeConverterTudat::utc_iso_to_tai_j2000(const std::string& iso_string) const
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

double TimeConverterTudat::utc_iso_to_tt_j2000(const std::string& iso_string) const
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

double TimeConverterTudat::utc_iso_to_tdb_j2000(const std::string& iso_string) const
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

std::string TimeConverterTudat::posix_to_utc_iso(
	const double posix_time,
	bool use_t_separator,
	int fractional_second_places
) const
{
	try
	{
		const double utc_j2000_time = posix_to_utc_j2000(posix_time);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_j2000_time)
			.isoString(use_t_separator, fractional_second_places);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to ISO string: " << e.what() << "\n";
		return "";
	}
}

double TimeConverterTudat::posix_to_tai_j2000(const double posix_time) const
{
	try
	{
		const double utc_j2000_time = posix_to_utc_j2000(posix_time);

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			utc_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::posix_to_tt_j2000(const double posix_time) const
{
	try
	{
		const double utc_j2000_time = posix_to_utc_j2000(posix_time);

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			utc_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::posix_to_tdb_j2000(const double posix_time) const
{
	try
	{
		const double utc_j2000_time = posix_to_utc_j2000(posix_time);

		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			utc_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

//
// utc_j2000_to_*() functions
//

std::string TimeConverterTudat::utc_j2000_to_utc_iso(
	const double utc_j2000_time,
	bool use_t_separator,
	int fractional_second_places
) const
{
	try
	{
		return tudat::basic_astrodynamics::DateTime::fromTime(utc_j2000_time)
			.isoString(use_t_separator, fractional_second_places);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to ISO string: " << e.what() << "\n";
		return "";
	}
}

double TimeConverterTudat::utc_j2000_to_tai_j2000(const double utc_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			utc_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::utc_j2000_to_tt_j2000(const double utc_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			utc_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::utc_j2000_to_tdb_j2000(const double utc_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			utc_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

//
// tai_j2000_to_*() functions
//

std::string TimeConverterTudat::tai_j2000_to_utc_iso(
	const double tai_j2000_time,
	bool use_t_separator,
	int fractional_second_places
) const
{
	try
	{
		const double utc_j2000_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tai_j2000_time
		);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_j2000_time)
			.isoString(use_t_separator, fractional_second_places);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT UTC ISO timestamp: " << e.what() << "\n";
		return "";
	}
}

double TimeConverterTudat::tai_j2000_to_posix(const double tai_j2000_time) const
{
	try
	{
		const double utc_j2000_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tai_j2000_time
		);

		return utc_j2000_to_posix(utc_j2000_time);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to POSIX timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::tai_j2000_to_utc_j2000(const double tai_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tai_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT UTC timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::tai_j2000_to_tt_j2000(const double tai_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tai_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::tai_j2000_to_tdb_j2000(const double tai_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tai_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TAI timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

//
// tt_j2000_to_*() functions
//

std::string TimeConverterTudat::tt_j2000_to_utc_iso(
	const double tt_j2000_time,
	bool use_t_separator,
	int fractional_second_places
) const
{
	try
	{
		const double utc_j2000_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tt_j2000_time
		);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_j2000_time)
			.isoString(use_t_separator, fractional_second_places);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT UTC ISO timestamp: " << e.what() << "\n";
		return "";
	}
}

double TimeConverterTudat::tt_j2000_to_posix(const double tt_j2000_time) const
{
	try
	{
		const double utc_j2000_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tt_j2000_time
		);

		return utc_j2000_to_posix(utc_j2000_time);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to POSIX timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::tt_j2000_to_utc_j2000(const double tt_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tt_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT UTC timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::tt_j2000_to_tai_j2000(const double tt_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tt_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::tt_j2000_to_tdb_j2000(const double tt_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tt_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TT timestamp to TUDAT TDB timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

//
// tdb_j2000_to_*() functions
//

std::string TimeConverterTudat::tdb_j2000_to_utc_iso(
	const double tdb_j2000_time,
	bool use_t_separator,
	int fractional_second_places
) const
{
	try
	{
		const double utc_j2000_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tdb_j2000_time
		);

		return tudat::basic_astrodynamics::DateTime::fromTime(utc_j2000_time)
			.isoString(use_t_separator, fractional_second_places);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT UTC ISO timestamp: " << e.what() << "\n";
		return "";
	}
}

double TimeConverterTudat::tdb_j2000_to_posix(const double tdb_j2000_time) const
{
	try
	{
		const double utc_j2000_time = get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tdb_j2000_time
		);

		return utc_j2000_to_posix(utc_j2000_time);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to POSIX timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::tdb_j2000_to_utc_j2000(const double tdb_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tdb_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT UTC timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::tdb_j2000_to_tai_j2000(const double tdb_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::tai_scale,
			tdb_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double TimeConverterTudat::tdb_j2000_to_tt_j2000(const double tdb_j2000_time) const
{
	try
	{
		return get_tudat_time_scale_converter()->getCurrentTime(
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
			tudat::basic_astrodynamics::TimeScales::tt_scale,
			tdb_j2000_time
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT TDB timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}
