#include "time_converter.h"

#include <stdexcept>

TimeValue
TimeConverter::convert_time(const TimeValue& input, TimeFormat input_format, TimeFormat output_format) const
{
	DispatchKey key{ input_format, output_format };
	auto it = dispatchTable.find(key);
	if(it != dispatchTable.end())
	{
		const ConversionWrapper& handler = it->second;
		switch(handler.getInputType())
		{
			case ConversionWrapper::InputType::STRING:
				if(!std::holds_alternative<std::string>(input))
				{
					throw std::invalid_argument(
						"Expected input of type std::string for the given input TimeFormat"
					);
				}
				break;
			case ConversionWrapper::InputType::DOUBLE:
				if(!std::holds_alternative<double>(input))
				{
					throw std::invalid_argument("Expected input of type double for the given input TimeFormat"
					);
				}
				break;
			case ConversionWrapper::InputType::SYS_TIME:
				if(!std::holds_alternative<std::chrono::system_clock::time_point>(input))
				{
					throw std::invalid_argument(
						"Expected input of type std::chrono::system_clock::time_point for the given input "
						"TimeFormat"
					);
				}
				break;
#ifdef HAS_CHRONO_UTC_CLOCK
			case ConversionWrapper::InputType::UTC_TIME:
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
			case ConversionWrapper::InputType::TAI_TIME:
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
