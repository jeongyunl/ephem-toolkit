#include "time_converter_tudat.h"
#include "base/time_converter_base.h"
#include "chrono/time_converter_chrono.h"

#include <format>
#include <iostream>
#include <list>
#include <map>
#include <ranges>
#include <string_view>
#include <variant>
#include <getopt.h>

namespace
{
enum class BackendType
{
	BASE,
	TUDAT,
	CHRONO,
	UNKNOWN
};

const std::map<std::string_view, TimeFormat> BaseTimeFormatNames = {
	{ "iso", TimeFormat::UTC_ISO8601 }, { "posix", TimeFormat::POSIX }, { "utc", TimeFormat::UTC_J2000 },
	{ "tai", TimeFormat::TAI_J2000 },   { "tt", TimeFormat::TT_J2000 },
};

const std::map<std::string_view, TimeFormat> ChronoUtcTimeFormatNames = {
	{ "iso", TimeFormat::UTC_ISO8601 },
	{ "posix", TimeFormat::POSIX },
	{ "utc", TimeFormat::UTC_J2000 },
	{ "tai", TimeFormat::TAI_J2000 },
	{ "tt", TimeFormat::TT_J2000 },
	{ "chrono_sys_iso", TimeFormat::CHRONO_SYS_TIME_ISO },
	{ "chrono_sys", TimeFormat::CHRONO_SYS_TIME },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ "chrono_utc_iso", TimeFormat::CHRONO_UTC_TIME_ISO },
	{ "chrono_utc", TimeFormat::CHRONO_UTC_TIME },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ "chrono_tai_iso", TimeFormat::CHRONO_TAI_TIME_ISO },
	{ "chrono_tai", TimeFormat::CHRONO_TAI_TIME },
#endif
};

const std::map<std::string_view, TimeFormat> TudatTimeFormatNames = {
	{ "iso", TimeFormat::UTC_ISO8601 }, { "posix", TimeFormat::POSIX }, { "utc", TimeFormat::UTC_J2000 },
	{ "tai", TimeFormat::TAI_J2000 },   { "tt", TimeFormat::TT_J2000 }, { "tdb", TimeFormat::TDB_J2000 },
};

BackendType parse_backend(const std::string& backend_str)
{
	if(backend_str == "base")
	{
		return BackendType::BASE;
	}
	if(backend_str == "tudat")
	{
		return BackendType::TUDAT;
	}
	if(backend_str == "chrono")
	{
		return BackendType::CHRONO;
	}
	return BackendType::UNKNOWN;
}

const std::map<std::string_view, TimeFormat>& get_format_names(BackendType backend)
{
	if(backend == BackendType::TUDAT)
	{
		return TudatTimeFormatNames;
	}
	if(backend == BackendType::CHRONO)
	{
		return ChronoUtcTimeFormatNames;
	}
	return BaseTimeFormatNames;
}

TimeFormat parse_time_format(const std::string& format_str, BackendType backend)
{
	const auto& format_names = get_format_names(backend);
	const auto it = format_names.find(format_str);
	if(it != format_names.end())
	{
		return it->second;
	}
	return TimeFormat::UNKNOWN;
}

void print_formats(const std::map<std::string_view, TimeFormat>& format_names)
{
	int i = 0;

	for(const auto& [name, format] : format_names)
	{
		(void)format;
		std::cout << "  " << name;
		if(++i % 4 == 0)
		{
			std::cout << '\n';
		}
		else
		{
			std::cout << '\t';
		}
	}
	std::cout << '\n';
}

void print_usage(const char* program_name)
{
	std::cout << "Usage: " << program_name << " [OPTIONS] input_time ...\n"
			  << "Options:\n"
			  << "  -h, --help                Show this help message and exit\n"
			  << "  -b, --backend BACKEND     Select backend (base, chrono, or tudat)\n"
			  << "  -i, --input-format FORMAT Specify the input time format\n"
			  << "  -o, --output-format FORMAT Specify the output time format\n";

	std::cout << "\nBase backend formats:\n";
	print_formats(BaseTimeFormatNames);

	std::cout << "\nChrono UTC backend formats:\n";
	print_formats(ChronoUtcTimeFormatNames);

	std::cout << "\nTudat backend formats:\n";
	print_formats(TudatTimeFormatNames);
}

TimeValue
run_conversion(BackendType backend, const TimeValue& input, TimeFormat input_format, TimeFormat output_format)
{
	if(backend == BackendType::TUDAT)
	{
		return TimeConverterTudat::instance().convert_time(input, input_format, output_format);
	}
	if(backend == BackendType::CHRONO)
	{
		return TimeConverterChrono::instance().convert_time(input, input_format, output_format);
	}
	return TimeConverterBase::instance().convert_time(input, input_format, output_format);
}
} // namespace

int main(int argc, char* argv[])
{
	std::string backend_str = "base";
	std::string input_format_str;
	std::list<std::string> output_format_list;
	std::list<std::string> input_time_list;

	for(;;)
	{
		int opt_char = 0;
		int option_index = 0;
		static struct option long_options[] = { { "help", no_argument, 0, 'h' },
												{ "backend", required_argument, 0, 'b' },
												{ "input-format", required_argument, 0, 'i' },
												{ "output-format", required_argument, 0, 'o' },
												{ 0, 0, 0, 0 } };

		opt_char = getopt_long(argc, argv, "hb:i:o:", long_options, &option_index);

		if(opt_char == -1)
		{
			break;
		}

		switch(opt_char)
		{
			case 'h':
				print_usage(argv[0]);
				return 0;
			case 'b':
				backend_str = optarg;
				break;
			case 'i':
				input_format_str = optarg;
				break;
			case 'o':
			{
				for(const auto word : std::views::split(std::string_view(optarg), std::string_view(",")))
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

	const BackendType backend = parse_backend(backend_str);
	if(backend == BackendType::UNKNOWN)
	{
		std::cerr << "Unknown backend: " << backend_str << "\n";
		return 1;
	}

	if(optind < argc)
	{
		while(optind < argc)
		{
			input_time_list.emplace_back(argv[optind]);
			optind++;
		}
	}
	else
	{
		std::cerr << "No input times provided\n";
		print_usage(argv[0]);
		return 1;
	}

	auto input_time_format = parse_time_format(input_format_str, backend);
	if(input_time_format == TimeFormat::UNKNOWN)
	{
		std::cerr << "Unknown input time format for selected backend: " << input_format_str << "\n";
		return 1;
	}

	TimeConverterBase::instance().make_dispatch_table();
	TimeConverterChrono::instance().make_dispatch_table();
	TimeConverterTudat::instance().make_dispatch_table();

	for(const auto& input_time_str : input_time_list)
	{
		std::cout << input_time_str;

		TimeValue input_time_value;
		if(input_time_format == TimeFormat::UTC_ISO8601)
		{
			input_time_value = input_time_str;
		}
		else
		{
			input_time_value = std::stod(input_time_str);
		}

		for(const auto& output_format_str : output_format_list)
		{
			const auto output_format = parse_time_format(output_format_str, backend);

			if(output_format == TimeFormat::UNKNOWN)
			{
				std::cerr << "Unknown output time format for selected backend: " << output_format_str << "\n";
				return 1;
			}

			const auto result = run_conversion(backend, input_time_value, input_time_format, output_format);

			std::cout << '\t';

			if(std::holds_alternative<double>(result))
			{
				std::cout << std::format("{:.3f}", std::get<double>(result));
			}
			else if(std::holds_alternative<std::string>(result))
			{
				std::cout << std::get<std::string>(result);
			}
			else if(std::holds_alternative<std::chrono::system_clock::time_point>(result))
			{
				const auto& sys_time = std::get<std::chrono::system_clock::time_point>(result);
				switch(output_format)
				{
					case TimeFormat::CHRONO_SYS_TIME:
						std::cout << std::format(
							"{:.3f} (since {} UTC)",
							std::chrono::duration<double>(sys_time.time_since_epoch()).count(),
							std::chrono::floor<std::chrono::seconds>(std::chrono::system_clock::time_point{})
						);
						break;
					case TimeFormat::CHRONO_SYS_TIME_ISO:
					default:
						std::cout
							<< std::format("{} UTC", std::chrono::floor<std::chrono::milliseconds>(sys_time));
						break;
				}
			}
#ifdef HAS_CHRONO_UTC_CLOCK
			else if(std::holds_alternative<std::chrono::utc_clock::time_point>(result))
			{
				const auto& utc_time = std::get<std::chrono::utc_clock::time_point>(result);
				switch(output_format)
				{
					case TimeFormat::CHRONO_UTC_TIME:
						std::cout << std::format(
							"{:.3f} (since {} UTC)",
							std::chrono::duration<double>(utc_time.time_since_epoch()).count(),
							std::chrono::floor<std::chrono::seconds>(std::chrono::utc_clock::time_point{})
						);
						break;
					case TimeFormat::CHRONO_UTC_TIME_ISO:
					default:
						std::cout
							<< std::format("{} UTC", std::chrono::floor<std::chrono::milliseconds>(utc_time));
						break;
				}
			}
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
			else if(std::holds_alternative<std::chrono::tai_clock::time_point>(result))
			{
				const auto& tai_time = std::get<std::chrono::tai_clock::time_point>(result);
				switch(output_format)
				{
					case TimeFormat::CHRONO_TAI_TIME:
						std::cout << std::format(
							"{:.3f} (since {} UTC)",
							std::chrono::duration<double>(tai_time.time_since_epoch()).count(),
							std::chrono::floor<std::chrono::seconds>(
								std::chrono::tai_clock::to_utc(std::chrono::tai_clock::time_point{})
							)
						);
						break;
					case TimeFormat::CHRONO_TAI_TIME_ISO:
					default:
						std::cout << std::format(
							"{} UTC",
							std::chrono::floor<std::chrono::milliseconds>(
								std::chrono::tai_clock::to_utc(tai_time)
							)
						);
						break;
				}
			}
#endif
			else
			{
				std::cerr << "Unimplemented output type in result variant\n";
				return 1;
			}
		}
		std::cout << '\n';
	}

	return 0;
}
