#include "convert_time.h"

#include "convert_time_leap_transition.h"
#include "convert_time_tudat.h"
#include "convert_time_utc_iso.h" // Leap-second table + ISO parser based UTC<->TAI logic

#include <iostream>

double utc_posix_to_utc_posix(const double utc_posix_epoch)
{
	return utc_posix_epoch;
}

double utc_posix_to_utc_tudat(const double utc_posix_epoch)
{
	return utc_posix_epoch - POSIX_EPOCH_MINUS_UTC_J200_EPOCH;
}

double utc_posix_to_tai_tudat(const double utc_posix_epoch)
{
	// Convert POSIX UTC seconds -> TUDAT TAI seconds without using Tudat's time scale converter.
	//
	// TUDAT epochs:
	// - UTC TUDAT epoch is J2000: 2000-01-01 12:00:00 UTC
	// - TAI TUDAT epoch is J2000: 2000-01-01 12:00:00 TAI
	//
	// Therefore, for any instant:
	//   tai_tudat = utc_tudat + (TAI-UTC)(instant)
	// where (TAI-UTC) includes the pre-1972 linear segment and post-1972 leap seconds.
	try
	{
		// Convert POSIX epoch seconds to UTC seconds since the TUDAT epoch.
		const double utc_tudat_epoch = utc_posix_epoch - POSIX_EPOCH_MINUS_UTC_J200_EPOCH;

		// Compute TAI-UTC at this instant using the same leap-second table logic as the ISO parser.
		// The leap-second transitions are defined in POSIX time at the *end* of the day.
		// For exact equality at a transition instant, the new leap second is already in effect
		// for the following second, so include_transition_at_equal=true is appropriate here.
		const double tai_minus_utc =
			cumulative_leap_correction(get_zoneinfo_leap_transitions(), utc_posix_epoch, true);

		return utc_tudat_epoch + tai_minus_utc;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_posix_to_tt_tudat(const double utc_posix_epoch)
{
	// Convert POSIX UTC seconds -> TUDAT TT seconds without using Tudat's time scale converter.
	//
	// For any instant:
	//   tt = tai + (TT-TAI)
	//   tai = utc + (TAI-UTC)
	// Therefore:
	//   tt_tudat = utc_tudat + (TAI-UTC)(instant) + (TT-TAI)
	try
	{
		const double utc_tudat_epoch = utc_posix_epoch - POSIX_EPOCH_MINUS_UTC_J200_EPOCH;
		const double tai_minus_utc =
			cumulative_leap_correction(get_zoneinfo_leap_transitions(), utc_posix_epoch, true);

		return utc_tudat_epoch + tai_minus_utc + TT_EPOCH_MINUS_TAI_EPOCH;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting POSIX timestamp to TUDAT TT timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_posix_to_tdb_tudat(const double utc_posix_epoch)
{
	return utc_posix_to_tt_tudat(utc_posix_epoch);
}

double utc_tudat_to_utc_posix(const double utc_tudat_epoch)
{
	return utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_J200_EPOCH;
}

double utc_tudat_to_utc_tudat(const double utc_tudat_epoch)
{
	return utc_tudat_epoch;
}

double utc_tudat_to_tai_tudat(const double utc_tudat_epoch)
{
	// Convert TUDAT UTC seconds -> TUDAT TAI seconds without using Tudat's time scale converter.
	//
	// For any instant:
	//   tai_tudat = utc_tudat + (TAI-UTC)(instant)
	// where (TAI-UTC) includes the pre-1972 linear segment and post-1972 leap seconds.
	try
	{
		const double utc_posix_epoch = utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_J200_EPOCH;
		const double tai_minus_utc =
			cumulative_leap_correction(get_zoneinfo_leap_transitions(), utc_posix_epoch, true);
		return utc_tudat_epoch + tai_minus_utc;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting TUDAT UTC timestamp to TUDAT TAI timestamp: " << e.what() << "\n";
		return std::numeric_limits<double>::quiet_NaN();
	}
}

double utc_tudat_to_tt_tudat(const double utc_tudat_epoch)
{
	return utc_tudat_to_tai_tudat(utc_tudat_epoch) + TT_EPOCH_MINUS_TAI_EPOCH;
}

double utc_tudat_to_tdb_tudat(const double utc_tudat_epoch)
{
	return utc_tudat_to_tt_tudat(utc_tudat_epoch);
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

		return utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_J200_EPOCH;
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

		return utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_J200_EPOCH;
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
#ifdef TUDAT_BUGGY_TDB_TO_UTC_CONVERSIONS
			tudat::basic_astrodynamics::TimeScales::tt_scale,
#else
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
#endif
			tudat::basic_astrodynamics::TimeScales::utc_scale,
			tdb_tudat_epoch
		);

		return utc_tudat_epoch + POSIX_EPOCH_MINUS_UTC_J200_EPOCH;
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
#ifdef TUDAT_BUGGY_TDB_TO_UTC_CONVERSIONS
			tudat::basic_astrodynamics::TimeScales::tt_scale,
#else
			tudat::basic_astrodynamics::TimeScales::tdb_scale,
#endif
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
