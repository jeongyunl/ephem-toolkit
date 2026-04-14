#include "tudat.h"

double round_to_decimal_places(double value, int decimal_places)
{
	const double multiplier = std::pow(10.0, decimal_places);
	return std::round(value * multiplier) / multiplier;
}

// CSPICE APIs used:
// et2utc_c, unitim_c, str2et_c

static std::string spiceConvertTdbToUtcIsoString(double epoch_tdb, int precision)
{
	std::string utc_iso_string; // eg 2025-11-10T16:00:27.123456
	utc_iso_string.reserve(30);
	utc_iso_string.resize(30);

	// et2utc_c ( Ephemeris Time to UTC )
	::et2utc_c(
		epoch_tdb, // SpiceDouble
		"ISOC", // "ISOC"   "1987-04-12T16:31:12.814"
		precision, // SpiceInt prec
		utc_iso_string.capacity() - 1, // SpiceInt lenout
		utc_iso_string.data() // SpiceChar * utcstr
	);

	utc_iso_string.resize(std::strlen(utc_iso_string.c_str()));

	return utc_iso_string;
}

static double spiceConvertUtcIsoStringToTdb(std::string utc_iso_string)
{
	try
	{
		int year, month, days, hours, minutes;
		long double seconds;

		tudat::basic_astrodynamics::decomposedDateTimeFromIsoString(
			utc_iso_string,
			year,
			month,
			days,
			hours,
			minutes,
			seconds
		);
	}
	catch(const std::exception& e)
	{
		std::cerr << e.what() << '\n';

		return 0;
	}

	double epoch_tdb = 0.0;
	::str2et_c(utc_iso_string.c_str(), &epoch_tdb);

	return epoch_tdb;
}

static double spiceTdbToTt(double epoch_tdb)
{
	return ::unitim_c(epoch_tdb, "TDB", "TT"); // TDB to TT
}

static double spiceTtToTdb(double epoch_tt)
{
	return ::unitim_c(epoch_tt, "TT", "TDB"); // TT to TDB
}

static double estimateTdbToTtOffset(double epoch)
{
	// g = 6.24 + 0.017202 × (JDtt − 2451545)
	const double jd_tt = tudat::basic_astrodynamics::convertSecondsSinceEpochToJulianDay(epoch);
	const double g = 6.24 + 0.017202 * (jd_tt - tudat::basic_astrodynamics::JULIAN_DAY_ON_J2000);

	// TDB ~= TT + 0.001657* sin(g)

	return 0.001657 * std::sin(g);
}

static double estimateTdbToTt(double epoch_tdb)
{
	return epoch_tdb - estimateTdbToTtOffset(epoch_tdb);
}

static double estimateTtToTdb(double epoch_tt)
{
	return epoch_tt + estimateTdbToTtOffset(epoch_tt);
}

void test_tdb(
	const double initial_epoch_tdb,
	const double duration_seconds,
	const double step_size_seconds = 1.0
)
{
	std::cout << "initial_epoch_tdb:  " << initial_epoch_tdb << "\n";

	for(double epoch_tdb = initial_epoch_tdb; epoch_tdb <= initial_epoch_tdb + duration_seconds;
		epoch_tdb += step_size_seconds)
	{
		std::cout << "TDB: " << epoch_tdb << "\n";

		const auto spice_converted_epoch_tt = spiceTdbToTt(epoch_tdb); // TDB to TTs
		std::cout << "TT:  " << spice_converted_epoch_tt << "\n";

		{
			const auto estimated_epoch_tt = estimateTdbToTt(epoch_tdb); // TDB to TTs
			std::cout << "TT:  " << estimated_epoch_tt << "\n";

			double time_difference = std::abs(spice_converted_epoch_tt - estimated_epoch_tt);
			if(time_difference > 1.5e-6)
			{
				std::cout << "Mismatch: "
						  << "TT(SPICE): " << spice_converted_epoch_tt << ", "
						  << "TT(Estim): " << estimated_epoch_tt << ", "
						  << "Difference = " << time_difference << " sec\n";
			}
		}

		std::string iso_string_utc = spiceConvertTdbToUtcIsoString(epoch_tdb, 6);
		std::cout << "ISO String (UTC) = '" << iso_string_utc << "'\n";

		double spice_converted_from_iso_string_epoch_tdb = spiceConvertUtcIsoStringToTdb(iso_string_utc);

		double time_difference = std::abs(epoch_tdb - spice_converted_from_iso_string_epoch_tdb);
		if(time_difference > 1.0e-6)
		{
			std::cout << "Mismatch: "
					  << "TDB = " << epoch_tdb << ", "
					  << "ISO String (UTC) = '" << iso_string_utc << "', "
					  << "Converted TDB = " << spice_converted_from_iso_string_epoch_tdb << ", "
					  << "Difference = " << time_difference << " sec\n";
		}

		std::cout << "\n";
	}
}

void test_tt(
	const double initial_epoch_tt,
	const double duration_seconds,
	const double step_size_seconds = 1.0
)
{
	std::cout << "initial_epoch_tt:  " << initial_epoch_tt << "\n";

	for(double epoch_tt = initial_epoch_tt; epoch_tt <= initial_epoch_tt + duration_seconds;
		epoch_tt += step_size_seconds)
	{
		std::cout << "TT:  " << epoch_tt << "\n";

		const auto spice_converted_epoch_tdb = spiceTtToTdb(epoch_tt); // TT to TDB
		std::cout << "TDB: " << spice_converted_epoch_tdb << "\n";

		{
			const auto estimated_epoch_tdb = estimateTtToTdb(epoch_tt); // TT to TDB
			std::cout << "TDB: " << estimated_epoch_tdb << "\n";

			double time_difference = std::abs(spice_converted_epoch_tdb - estimated_epoch_tdb);
			if(time_difference > 1.5e-6)
			{
				std::cout << "Mismatch: "
						  << "TDB(SPICE): " << spice_converted_epoch_tdb << ", "
						  << "TDB(Estim): " << estimated_epoch_tdb << ", "
						  << "Difference = " << time_difference << " sec\n";
			}
		}

		std::string iso_string_utc = spiceConvertTdbToUtcIsoString(spice_converted_epoch_tdb, 6);
		std::cout << "ISO String (UTC) = '" << iso_string_utc << "'\n";

		double spice_converted_from_iso_string_epoch_tdb = spiceConvertUtcIsoStringToTdb(iso_string_utc);

		double time_difference =
			std::abs(spice_converted_epoch_tdb - spice_converted_from_iso_string_epoch_tdb);
		if(time_difference > 1.0e-6)
		{
			std::cout << "Mismatch: "
					  << "TDB = " << spice_converted_epoch_tdb << ", "
					  << "ISO String (UTC) = '" << iso_string_utc << "', "
					  << "Converted TDB = " << spice_converted_from_iso_string_epoch_tdb << ", "
					  << "Difference = " << time_difference << " sec\n";
		}

		std::cout << "\n";
	}
}

void batch_time_conversion()
{
	std::cout << std::fixed;

	// TDB driven conversion test
	{
		struct
		{
			double initial_epoch;
			double duration;
		} tdb_test_cases[] = {
			{ 0.0, 30 },
			{ spiceConvertUtcIsoStringToTdb("2016-12-31T23:59:59"), 30 },
		};

		for(const auto& test_case : tdb_test_cases)
		{
			test_tdb(test_case.initial_epoch, test_case.duration);
		}
	}

	// TT driven conversion test
	{
		struct
		{
			double initial_epoch;
			double duration;
		} tt_test_cases[] = {
			{ 0.0, 30 },
			{ spiceTdbToTt(spiceConvertUtcIsoStringToTdb("2000-01-01T12:00:00")), 30 },
			{ spiceTdbToTt(spiceConvertUtcIsoStringToTdb("2016-12-31T23:59:59")), 30 },

		};

		for(const auto& test_case : tt_test_cases)
		{
			test_tt(test_case.initial_epoch, test_case.duration);
		}
	}
}

int main()
{
	tudat::spice_interface::loadSpiceKernelInTudat(tudat::paths::getSpiceKernelPath() + "/naif0012.tls");

	batch_time_conversion();

	return 0;
}
