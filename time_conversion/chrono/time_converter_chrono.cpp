#include "time_converter_chrono.h"

#include "chrono_dispatch_entries.h"
#include "../base/base_dispatch_entries.h"
#include "../dispatch_handler.h"

#include <stdexcept>

namespace
{
std::map<DispatchKey, Handler> make_chrono_dispatch_table()
{
	std::map<DispatchKey, Handler> dispatch_table;
	register_base_dispatch_entries(dispatch_table);
	register_chrono_dispatch_entries(dispatch_table);
	return dispatch_table;
}
} // namespace

std::map<DispatchKey, Handler> chronoDispatchTable = make_chrono_dispatch_table();

TimeValue
TimeConverterChrono::convert_time(const TimeValue& input, TimeFormat input_format, TimeFormat output_format)
	const
{
	DispatchKey key{ input_format, output_format };
	auto it = chronoDispatchTable.find(key);
	if(it != chronoDispatchTable.end())
	{
		const Handler& handler = it->second;
		switch(handler.getInputType())
		{
			case Handler::InputType::STRING:
				if(!std::holds_alternative<std::string>(input))
				{
					throw std::invalid_argument(
						"Expected input of type std::string for the given input TimeFormat"
					);
				}
				break;
			case Handler::InputType::DOUBLE:
				if(!std::holds_alternative<double>(input))
				{
					throw std::invalid_argument("Expected input of type double for the given input TimeFormat"
					);
				}
				break;
			case Handler::InputType::SYS_TIME:
				if(!std::holds_alternative<std::chrono::system_clock::time_point>(input))
				{
					throw std::invalid_argument(
						"Expected input of type std::chrono::system_clock::time_point for the given input "
						"TimeFormat"
					);
				}
				break;
#ifdef HAS_CHRONO_UTC_CLOCK
			case Handler::InputType::UTC_TIME:
				if(!std::holds_alternative<std::chrono::utc_clock::time_point>(input))
				{
					throw std::invalid_argument(
						"Expected input of type std::chrono::utc_clock::time_point for the given input "
						"TimeFormat"
					);
				}
				break;
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
			case Handler::InputType::TAI_TIME:
				if(!std::holds_alternative<std::chrono::tai_clock::time_point>(input))
				{
					throw std::invalid_argument(
						"Expected input of type std::chrono::tai_clock::time_point for the given input "
						"TimeFormat"
					);
				}
				break;
#endif
		}

		return handler(input, this);
	}

	throw std::invalid_argument("Unsupported combination of input and output TimeFormat");
}

#ifdef HAS_CHRONO_UTC_CLOCK
double TimeConverterChrono::posix_to_tai_j2000(double posix_time) const
{
	const auto utc_time = posix_to_utc_time(posix_time);
	return std::chrono::duration<
			   double>(utc_time - epochs::TAI_J2000_EPOCH_IN_UTC_TIME<decltype(utc_time)::duration>)
		.count();
}

double TimeConverterChrono::parsed_utc_iso_to_tai_j2000(const ParsedUtcIso& parsed_utc_iso) const
{
	const auto utc_time = parsed_utc_iso_to_utc_time(parsed_utc_iso);
	return std::chrono::duration<
			   double>(utc_time - epochs::TAI_J2000_EPOCH_IN_UTC_TIME<decltype(utc_time)::duration>)
		.count();
}

ParsedUtcIso TimeConverterChrono::tai_j2000_to_parsed_utc_iso(double tai_j2000_time) const
{
	const auto utc_time = tai_j2000_to_utc_time(tai_j2000_time);
	auto leap_second_info = std::chrono::get_leap_second_info(utc_time);

	std::chrono::system_clock::time_point sys_time;
	if(!leap_second_info.is_leap_second)
	{
		sys_time = std::chrono::utc_clock::to_sys(utc_time);
	}
	else
	{
		sys_time = std::chrono::utc_clock::to_sys(utc_time - std::chrono::seconds{ 1 });
	}

	const auto sys_days = std::chrono::floor<std::chrono::days>(sys_time);
	std::chrono::year_month_day ymd{ sys_days };
	std::chrono::hh_mm_ss time_of_day{ sys_time - sys_days };

	return ParsedUtcIso{
		.year = int(ymd.year()),
		.month = unsigned(ymd.month()),
		.day = unsigned(ymd.day()),
		.hour = static_cast<int>(time_of_day.hours().count()),
		.minute = static_cast<int>(time_of_day.minutes().count()),
		.second = static_cast<int>(time_of_day.seconds().count() + (leap_second_info.is_leap_second ? 1 : 0)),
		.nanos = time_of_day.subseconds().count(),
		.tz_offset_seconds = 0
	};
}
#endif
