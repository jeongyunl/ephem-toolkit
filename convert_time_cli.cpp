#include "convert_time.h"

#include <array>
#include <cmath>
#include <functional>
#include <iostream>
#include <list>
#include <map>
#include <ranges>
#include <string_view>
#include <variant>
#include <getopt.h>

enum class TimeFormat
{
	UNKNOWN = -1,
	UTC_ISO_TUDAT = 0, // ISO 8601 format in UTC: "YYYY-MM-DDTHH:MM:SS.sss"
	UTC_POSIX, // POSIX timestamp; in seconds since 1970-01-01 00:00:00 UTC
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
class Handler
{
public:
	enum class InputType
	{
		DOUBLE,
		STRING
	};

	using WrappedCallable = std::function<TimeValue(const TimeValue&)>;

	Handler() = default;

	explicit Handler(WrappedCallable callable, InputType input_type = InputType::DOUBLE)
		: callable_(std::move(callable))
		, input_type_(input_type)
	{
	}

	template <typename Arg, typename Ret>
	Handler(Ret (*func)(Arg))
		: callable_([func](const TimeValue& input_time) -> TimeValue {
			Arg arg = std::get<Arg>(input_time);
			Ret out = func(arg);
			return TimeValue{ std::in_place_type<Ret>, std::move(out) };
		})
		, input_type_(std::is_same_v<Arg, std::string> ? InputType::STRING : InputType::DOUBLE)
	{
	}

	template <typename Arg, typename Ret>
	Handler(Ret (*func)(const Arg&))
		: callable_([func](const TimeValue& input_time) -> TimeValue {
			const auto& arg = std::get<Arg>(input_time);
			Ret out = func(arg);
			return TimeValue{ std::in_place_type<Ret>, std::move(out) };
		})
		, input_type_(std::is_same_v<Arg, std::string> ? InputType::STRING : InputType::DOUBLE)
	{
	}

	TimeValue operator()(const TimeValue& input_time) const { return callable_(input_time); }

	explicit operator bool() const { return static_cast<bool>(callable_); }

	InputType getInputType() const { return input_type_; }

private:
	WrappedCallable callable_;
	InputType input_type_ = InputType::DOUBLE;
};

std::map<DispatchKey, Handler> dispatchTable{
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_ISO_TUDAT }, utc_iso_tudat_to_utc_iso_tudat },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_POSIX }, utc_iso_tudat_to_utc_posix },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_TUDAT }, utc_iso_tudat_to_utc_tudat },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::TAI_TUDAT }, utc_iso_tudat_to_tai_tudat },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::TT_TUDAT }, utc_iso_tudat_to_tt_tudat },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::TDB_TUDAT }, utc_iso_tudat_to_tdb_tudat },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::TDB_APX_TUDAT }, utc_iso_tudat_to_tdb_apx_tudat },

	{ { TimeFormat::UTC_POSIX, TimeFormat::UTC_ISO_TUDAT }, utc_posix_to_utc_iso_tudat },
	{ { TimeFormat::UTC_POSIX, TimeFormat::UTC_POSIX }, utc_posix_to_utc_posix },
	{ { TimeFormat::UTC_POSIX, TimeFormat::UTC_TUDAT }, utc_posix_to_utc_tudat },
	{ { TimeFormat::UTC_POSIX, TimeFormat::TAI_TUDAT }, utc_posix_to_tai_tudat },
	{ { TimeFormat::UTC_POSIX, TimeFormat::TT_TUDAT }, utc_posix_to_tt_tudat },
	{ { TimeFormat::UTC_POSIX, TimeFormat::TDB_TUDAT }, utc_posix_to_tdb_tudat },
	{ { TimeFormat::UTC_POSIX, TimeFormat::TDB_APX_TUDAT }, utc_posix_to_tdb_apx_tudat },

	{ { TimeFormat::UTC_TUDAT, TimeFormat::UTC_ISO_TUDAT }, utc_tudat_to_utc_iso_tudat },
	{ { TimeFormat::UTC_TUDAT, TimeFormat::UTC_POSIX }, utc_tudat_to_utc_posix },
	{ { TimeFormat::UTC_TUDAT, TimeFormat::UTC_TUDAT }, utc_tudat_to_utc_tudat },
	{ { TimeFormat::UTC_TUDAT, TimeFormat::TAI_TUDAT }, utc_tudat_to_tai_tudat },
	{ { TimeFormat::UTC_TUDAT, TimeFormat::TT_TUDAT }, utc_tudat_to_tt_tudat },
	{ { TimeFormat::UTC_TUDAT, TimeFormat::TDB_TUDAT }, utc_tudat_to_tdb_tudat },
	{ { TimeFormat::UTC_TUDAT, TimeFormat::TDB_APX_TUDAT }, utc_tudat_to_tdb_apx_tudat },

	{ { TimeFormat::TAI_TUDAT, TimeFormat::UTC_ISO_TUDAT }, tai_tudat_to_utc_iso_tudat },
	{ { TimeFormat::TAI_TUDAT, TimeFormat::UTC_POSIX }, tai_tudat_to_utc_posix },
	{ { TimeFormat::TAI_TUDAT, TimeFormat::UTC_TUDAT }, tai_tudat_to_utc_tudat },
	{ { TimeFormat::TAI_TUDAT, TimeFormat::TAI_TUDAT }, tai_tudat_to_tai_tudat },
	{ { TimeFormat::TAI_TUDAT, TimeFormat::TT_TUDAT }, tai_tudat_to_tt_tudat },
	{ { TimeFormat::TAI_TUDAT, TimeFormat::TDB_TUDAT }, tai_tudat_to_tdb_tudat },
	{ { TimeFormat::TAI_TUDAT, TimeFormat::TDB_APX_TUDAT }, tai_tudat_to_tdb_apx_tudat },

	{ { TimeFormat::TT_TUDAT, TimeFormat::UTC_ISO_TUDAT }, tt_tudat_to_utc_iso_tudat },
	{ { TimeFormat::TT_TUDAT, TimeFormat::UTC_POSIX }, tt_tudat_to_utc_posix },
	{ { TimeFormat::TT_TUDAT, TimeFormat::UTC_TUDAT }, tt_tudat_to_utc_tudat },
	{ { TimeFormat::TT_TUDAT, TimeFormat::TAI_TUDAT }, tt_tudat_to_tai_tudat },
	{ { TimeFormat::TT_TUDAT, TimeFormat::TT_TUDAT }, tt_tudat_to_tt_tudat },
	{ { TimeFormat::TT_TUDAT, TimeFormat::TDB_TUDAT }, tt_tudat_to_tdb_tudat },
	{ { TimeFormat::TT_TUDAT, TimeFormat::TDB_APX_TUDAT }, tt_tudat_to_tdb_apx_tudat },

	{ { TimeFormat::TDB_TUDAT, TimeFormat::UTC_ISO_TUDAT }, tdb_tudat_to_utc_iso_tudat },
	{ { TimeFormat::TDB_TUDAT, TimeFormat::UTC_POSIX }, tdb_tudat_to_utc_posix },
	{ { TimeFormat::TDB_TUDAT, TimeFormat::UTC_TUDAT }, tdb_tudat_to_utc_tudat },
	{ { TimeFormat::TDB_TUDAT, TimeFormat::TAI_TUDAT }, tdb_tudat_to_tai_tudat },
	{ { TimeFormat::TDB_TUDAT, TimeFormat::TT_TUDAT }, tdb_tudat_to_tt_tudat },
	{ { TimeFormat::TDB_TUDAT, TimeFormat::TDB_TUDAT }, tdb_tudat_to_tdb_tudat },
	{ { TimeFormat::TDB_TUDAT, TimeFormat::TDB_APX_TUDAT }, tdb_tudat_to_tt_tudat },

	{ { TimeFormat::TDB_APX_TUDAT, TimeFormat::UTC_ISO_TUDAT }, tdb_apx_tudat_to_utc_iso_tudat },
	{ { TimeFormat::TDB_APX_TUDAT, TimeFormat::UTC_POSIX }, tdb_apx_tudat_to_utc_posix },
	{ { TimeFormat::TDB_APX_TUDAT, TimeFormat::UTC_TUDAT }, tdb_apx_tudat_to_utc_tudat },
	{ { TimeFormat::TDB_APX_TUDAT, TimeFormat::TAI_TUDAT }, tdb_apx_tudat_to_tai_tudat },
	{ { TimeFormat::TDB_APX_TUDAT, TimeFormat::TT_TUDAT }, tdb_apx_tudat_to_tt_tudat },
	{ { TimeFormat::TDB_APX_TUDAT, TimeFormat::TDB_TUDAT }, tdb_apx_tudat_to_tdb_tudat },
	{ { TimeFormat::TDB_APX_TUDAT, TimeFormat::TDB_APX_TUDAT }, tdb_apx_tudat_to_tdb_apx_tudat },
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
				if(handler.getInputType() == Handler::InputType::STRING)
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
