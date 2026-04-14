// #include "tudat.h"

#include <tudat/astro/basic_astro/dateTime.h>
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
	TAI_TUDAT, // Time in TAI; in seconds since TAI J2000 epoch (2000-01-01 12:00:00.000 TAI = 2000-01-01
			   // 11:59:28 UTC)
	TT_TUDAT, // Terrestial Time; in seconds since TT J2000 epoch (2000-01-01 12:00:00.000 TT = 2000-01-01
			  // 11:58:55.816 UTC)
	TDB_TUDAT, // Barycentric Dynamical Time; in seconds since TDB J2000 epoch (2000-01-01 12:00:00.000 TDB ≈
			   // 2000-01-01 11:58:55.816 UTC)
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

TimeValue utc_iso_tudat_to_utc_posix(const TimeValue& input_time)
{
	// Convert ISO 8601 string to POSIX timestamp
	const auto iso_string = std::get<std::string>(input_time);
	// ... (conversion logic here)

	double utc_posix_epoch = std::nan("0");

	try
	{
		utc_posix_epoch =
			std::chrono::duration<double>(
				std::chrono::current_zone()
					->to_local(tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string).timePoint())
					.time_since_epoch()
			)
				.count();
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to POSIX timestamp: " << e.what() << "\n";
	}

	std::cout << "Converted '" << iso_string
			  << "' to POSIX timestamp: " << std::format("{:.3f}", utc_posix_epoch) << "\n";
	return utc_posix_epoch;
}

std::map<DispatchKey, Handler> dispatchTable{
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_POSIX }, utc_iso_to_utc_posix },
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

	std::cout << "Input format: " << input_format_str << "\n";
	auto input_time_format = parse_time_format(input_format_str);
	if(input_time_format == TimeFormat::UNKNOWN)
	{
		std::cerr << "Unknown input time format: " << input_format_str << "\n";
		return 1;
	}

	for(const auto& output_format_str : output_format_list)
	{
		std::cout << "Output format: " << output_format_str << "\n";
		auto output_format = parse_time_format(output_format_str);

		if(output_format == TimeFormat::UNKNOWN)
		{
			std::cerr << "Unknown output time format: " << output_format_str << "\n";
			return 1;
		}

		for(const auto& input_time_str : input_time_list)
		{
			std::cout << "Input time: " << input_time_str << "\n";

			// Convert input_time from input_format to output_format_list
			// ...

			utc_iso_to_utc_posix(input_time_str);
		}
	}

	return 0;
}
