#include "time_converter.h"
#include "dispatch_handler.h"
#include "base_dispatch_entries.h"
#include "chrono_utc/chrono_dispatch_entries.h"
#include "chrono_utc/time_converter_chrono_utc.h"

#include <stdexcept>
namespace
{
std::map<DispatchKey, Handler> make_dispatch_table()
{
	std::map<DispatchKey, Handler> dispatch_table;
	register_base_dispatch_entries(dispatch_table);
	register_chrono_dispatch_entries(dispatch_table);
	return dispatch_table;
}
} // namespace

namespace
{
std::map<DispatchKey, Handler> dispatchTable = make_dispatch_table();
}

TimeValue
TimeConverter::convert_time(const TimeValue& input, TimeFormat input_format, TimeFormat output_format) const
{
	DispatchKey key{ input_format, output_format };
	auto it = dispatchTable.find(key);
	if(it != dispatchTable.end())
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
					throw std::invalid_argument(
						"Expected input of type double for the given input TimeFormat"
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
		const TimeConverterBase* converter_backend = this;
		if(handler.getBackendType() == Handler::BackendType::CHRONO_UTC)
		{
			converter_backend = &TimeConverterChronoUtc::instance();
		}

		return handler(input, converter_backend);
	}
	else
	{
		throw std::invalid_argument("Unsupported combination of input and output TimeFormat");
	}
}
