// #include "tudat.h"

#include <tudat/astro/basic_astro/dateTime.h>
#include <tudat/astro/earth_orientation/terrestrialTimeScaleConverter.h>
#include <array>
#include <cmath>
#include <functional>
#include <iostream>
#include <list>
#include <ranges>
#include <string_view>
#include <variant>
#include <getopt.h>

// POSIX epoch (1970-01-01 00:00:00 UTC) minus TUDAT UTC J2000 epoch (2000-01-01 12:00:00 UTC)
constexpr auto POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH = 946728000.0;

// TT epoch (2000-01-01 12:00:00 TT) minus TAI epoch (2000-01-01 12:00:00 TAI)
constexpr auto TT_EPOCH_MINUS_TAI_EPOCH = 32.184;

enum class TimeFormat
{
	UNKNOWN = -1,
	UTC_POSIX = 0, // POSIX timestamp; in seconds since 1970-01-01 00:00:00 UTC
	UTC_ISO_TUDAT, // ISO 8601 format in UTC: "YYYY-MM-DDTHH:MM:SS.sss"
	UTC_TUDAT, // Time in UTC; in seconds since UTC J2000 epoch (2000-01-01 12:00:00.000 UTC)
	TAI_TUDAT, // Time in TAI; in seconds since TAI J2000 epoch (2000-01-01 12:00:00.000 TAI =
			   // 2000-01-01 11:59:28 UTC)
	TT_TUDAT, // Terrestial Time; in seconds since TT J2000 epoch (2000-01-01 12:00:00.000 TT =
			  // 2000-01-01 11:58:55.816 UTC)
	TDB_TUDAT, // Barycentric Dynamical Time; in seconds since TDB J2000 epoch (2000-01-01
			   // 12:00:00.000 TDB ≈ 2000-01-01 11:58:55.816 UTC)
	TDB_APX_TUDAT, // Approximate TDB J2000 epoch
};

constexpr auto TimeFormatNames =
	std::array<const char*, 7>{ "posix", "iso", "utc", "tai", "tt", "tdb", "tdb_apx" };

TimeFormat parse_time_format(const std::string& format_str)
{
	for(size_t i = 0; i < TimeFormatNames.size(); ++i)
	{
		if(format_str == TimeFormatNames[i])
		{
			return static_cast<TimeFormat>(i);
		}
	}

	return TimeFormat::UNKNOWN;
}

typedef std::variant<double, std::string> TimeValue;

using DispatchKey = std::pair<TimeFormat, TimeFormat>;
using Handler = std::function<TimeValue(const TimeValue&)>;

std::shared_ptr<tudat::earth_orientation::TerrestrialTimeScaleConverter> tudat_time_converter = nullptr;

TimeValue utc_iso_tudat_to_utc_posix(const TimeValue& input_time)
{
	// Convert ISO 8601 string to POSIX timestamp
	const auto iso_string = std::get<std::string>(input_time);
	// ... (conversion logic here)

	double utc_posix_epoch = std::nan("0");

	// Unforunately, tudat::basic_astrodynamics::DateTime::timePoint() and
	// tudat::basic_astrodynamics::DateTime::fromTimePoint() use std::localtime() and std::mktime()
	// internally, which are affected by the system's local timezone settings. To ensure that the
	// conversion is correct, we need to account for the local time offset.
	// The code below handles both C++20 and earlier versions, using the appropriate APIs to get the
	// local time offset.

	try
	{
#if __cplusplus >= 202002L && defined(_LIBCPP_HAS_TIME_ZONE_DATABASE) && _LIBCPP_HAS_TIME_ZONE_DATABASE
		// Code for C++20 and later
		utc_posix_epoch =
			std::chrono::duration<double>(
				std::chrono::current_zone()
					->to_local(tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string).timePoint())
					.time_since_epoch()
			)
				.count();
#else
		// Code for C++17 and earlier
		long local_time_offset = 0;
		{
			const std::time_t posix_epoch_zero = 0;
			std::tm local_tm = *std::localtime(&posix_epoch_zero);
			std::tm utc_tm = *std::gmtime(&posix_epoch_zero);

			local_time_offset = std::mktime(&local_tm) - std::mktime(&utc_tm); // seconds
		}
		utc_posix_epoch =
			std::chrono::duration<double>(
				tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string).timePoint().time_since_epoch()
			)
				.count()
			+ local_time_offset;
#endif
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to POSIX timestamp: " << e.what() << "\n";
	}

	return TimeValue{ std::in_place_type<double>, utc_posix_epoch };
}

TimeValue utc_iso_tudat_to_utc_tudat(const TimeValue& input_time)
{
	const auto iso_string = std::get<std::string>(input_time);
	double utc_tudat_epoch = std::nan("0");

	try
	{
		utc_tudat_epoch = tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string).epoch<double>();
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to TUDAT UTC timestamp: " << e.what() << "\n";
	}

	return TimeValue{ std::in_place_type<double>, utc_tudat_epoch };
}

TimeValue utc_iso_tudat_to_tai_tudat(const TimeValue& input_time)
{
	const auto iso_string = std::get<std::string>(input_time);
	double utc_tudat_epoch = std::nan("0");
	double tai_tudat_epoch = std::nan("0");

	{
		tudat::basic_astrodynamics::DateTime tudat_date_time;

		try
		{
			tudat_date_time = tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string);
			utc_tudat_epoch = tudat_date_time.epoch<double>();
		}
		catch(const std::exception& e)
		{
			std::cerr << "Error converting ISO string to TUDAT TAI timestamp: " << e.what() << "\n";
			return TimeValue{ std::in_place_type<double>, tai_tudat_epoch };
		}

		double leap_second = 0.0;
		if(tudat_date_time.getSeconds() >= 60.0)
		{
			leap_second = 1.0;
		}
		else
		{
			leap_second = 0.0;
		}

		tai_tudat_epoch = tudat_time_converter->getCurrentTime(
							  tudat::basic_astrodynamics::TimeScales::utc_scale,
							  tudat::basic_astrodynamics::TimeScales::tai_scale,
							  utc_tudat_epoch
						  )
			- leap_second;
	}
	return TimeValue{ std::in_place_type<double>, tai_tudat_epoch };
}

std::map<DispatchKey, Handler> dispatchTable{
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_POSIX }, utc_iso_tudat_to_utc_posix },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_TUDAT }, utc_iso_tudat_to_utc_tudat },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::TAI_TUDAT }, utc_iso_tudat_to_tai_tudat },
	// ... (other conversions)
};

int main(int argc, char* argv[])
{
	std::string input_format_str;
	std::list<std::string> output_format_list;
	std::list<std::string> input_time_list;

	for(;;)
	{
		int opt_char = 0;
		int option_index = 0;
		static struct option long_options[] = { { "help", no_argument, 0, 'h' },
												{ "input-format", required_argument, 0, 'i' },
												{ "output-format", required_argument, 0, 'o' },
												{ 0, 0, 0, 0 } };

		opt_char = getopt_long(argc, argv, "hi:o:t:", long_options, &option_index);

		if(opt_char == -1)
		{
			break;
		}

		switch(opt_char)
		{
			case 'h':
				std::cout << "Usage: " << argv[0] << " [OPTIONS]\n"
						  << "Options:\n"
						  << "  -h, --help                Show this help message and exit\n"
						  << "  -i, --input-format FORMAT Specify the input time format (posix, iso, utc, "
							 "tai, tt, tdb, tdb_apx)\n"
						  << "  -o, --output-format FORMAT Specify the output time format (posix, iso, utc, "
							 "tai, tt, tdb, tdb_apx)\n"
						  << "  -t, --time TIME           Specify the time value to convert\n";
				return 0;
			case 'i':
				input_format_str = optarg;
				break;
			case 'o':
			{
				for(const auto word : std::views::split(std::string_view(optarg), ','))
				{
					output_format_list.emplace_back(std::string(word.begin(), word.end()));
				}
			}
			break;
			default:
				std::cerr << "Unknown option: " << opt_char << "\n";
				return 1;
		}
	}

	if(optind < argc)
	{
		while(optind < argc)
		{
			input_time_list.emplace_back(argv[optind]);
			optind++;
		}
	}

	// Your code here

	tudat_time_converter = tudat::earth_orientation::createDefaultTimeConverter();

	std::cout << "Input format: " << input_format_str << "\n";
	auto input_time_format = parse_time_format(input_format_str);
	if(input_time_format == TimeFormat::UNKNOWN)
	{
		std::cerr << "Unknown input time format: " << input_format_str << "\n";
		return 1;
	}

	for(const auto& input_time_str : input_time_list)
	{
		std::cout << input_time_str;

		// Convert input_time from input_format to output_format_list
		// ...

		for(const auto& output_format_str : output_format_list)
		{
			auto output_format = parse_time_format(output_format_str);

			if(output_format == TimeFormat::UNKNOWN)
			{
				std::cerr << "Unknown output time format: " << output_format_str << "\n";
				return 1;
			}

			if(dispatchTable.contains({ input_time_format, output_format }))
			{
				auto handler = dispatchTable[{ input_time_format, output_format }];

				TimeValue input_time_value;
				if(input_time_format == TimeFormat::UTC_ISO_TUDAT)
				{
					input_time_value = TimeValue{ std::in_place_type<std::string>, input_time_str };
				}
				else
				{
					input_time_value = TimeValue{ std::in_place_type<double>, std::stod(input_time_str) };
				}

				TimeValue result = handler(input_time_value);

				std::cout << '\t';

				if(std::holds_alternative<double>(result))
				{
					std::cout << std::format("{:.3f}", std::get<double>(result));
				}
				else if(std::holds_alternative<std::string>(result))
				{
					std::cout << std::get<std::string>(result);
				}
			}
			else
			{
				std::cerr << "Conversion from " << input_format_str << " to " << output_format_str
						  << " is not supported.\n";
			}
		}
		std::cout << '\n';
	}

	return 0;
}
