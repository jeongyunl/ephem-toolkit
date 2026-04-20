#include "convert_time.h"

#include <tudat/astro/basic_astro/dateTime.h>
#include <tudat/astro/earth_orientation/terrestrialTimeScaleConverter.h>

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
