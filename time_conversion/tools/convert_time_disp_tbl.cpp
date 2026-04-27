#include "convert_time_disp_tbl.h"

#include <functional>
#include <map>
#include <stdexcept>
#include <variant>

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

	template <typename Arg, typename Ret>
	Handler(Ret (*func)(Arg, bool, int), bool use_t_separator = false, int fractional_second_places = 3)
		: callable_(
			  [func, use_t_separator, fractional_second_places](const TimeValue& input_time) -> TimeValue {
				  Arg arg = std::get<Arg>(input_time);
				  Ret out = func(arg, use_t_separator, fractional_second_places);
				  return TimeValue{ std::in_place_type<Ret>, std::move(out) };
			  }
		  )
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
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_ISO_TUDAT }, utc_iso_to_utc_iso },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_POSIX }, utc_iso_to_posix },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_TUDAT }, utc_iso_to_utc_j2000 },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::TAI_TUDAT }, utc_iso_to_tai_j2000 },
	{ { TimeFormat::UTC_ISO_TUDAT, TimeFormat::TT_TUDAT }, utc_iso_to_tt_j2000 },

	{ { TimeFormat::UTC_POSIX, TimeFormat::UTC_ISO_TUDAT }, posix_to_utc_iso },
	{ { TimeFormat::UTC_POSIX, TimeFormat::UTC_POSIX }, posix_to_posix },
	{ { TimeFormat::UTC_POSIX, TimeFormat::UTC_TUDAT }, posix_to_utc_j2000 },
	{ { TimeFormat::UTC_POSIX, TimeFormat::TAI_TUDAT }, posix_to_tai_j2000 },
	{ { TimeFormat::UTC_POSIX, TimeFormat::TT_TUDAT }, posix_to_tt_j2000 },

	{ { TimeFormat::UTC_TUDAT, TimeFormat::UTC_ISO_TUDAT }, utc_j2000_to_utc_iso },
	{ { TimeFormat::UTC_TUDAT, TimeFormat::UTC_POSIX }, utc_j2000_to_posix },
	{ { TimeFormat::UTC_TUDAT, TimeFormat::UTC_TUDAT }, utc_j2000_to_utc_j2000 },
	{ { TimeFormat::UTC_TUDAT, TimeFormat::TAI_TUDAT }, utc_j2000_to_tai_j2000 },
	{ { TimeFormat::UTC_TUDAT, TimeFormat::TT_TUDAT }, utc_j2000_to_tt_j2000 },

	{ { TimeFormat::TAI_TUDAT, TimeFormat::UTC_ISO_TUDAT }, tai_j2000_to_utc_iso },
	{ { TimeFormat::TAI_TUDAT, TimeFormat::UTC_POSIX }, tai_j2000_to_posix },
	{ { TimeFormat::TAI_TUDAT, TimeFormat::UTC_TUDAT }, tai_j2000_to_utc_j2000 },
	{ { TimeFormat::TAI_TUDAT, TimeFormat::TAI_TUDAT }, tai_j2000_to_tai_j2000 },
	{ { TimeFormat::TAI_TUDAT, TimeFormat::TT_TUDAT }, tai_j2000_to_tt_j2000 },

	{ { TimeFormat::TT_TUDAT, TimeFormat::UTC_ISO_TUDAT }, tt_j2000_to_utc_iso },
	{ { TimeFormat::TT_TUDAT, TimeFormat::UTC_POSIX }, tt_j2000_to_posix },
	{ { TimeFormat::TT_TUDAT, TimeFormat::UTC_TUDAT }, tt_j2000_to_utc_j2000 },
	{ { TimeFormat::TT_TUDAT, TimeFormat::TAI_TUDAT }, tt_j2000_to_tai_j2000 },
	{ { TimeFormat::TT_TUDAT, TimeFormat::TT_TUDAT }, tt_j2000_to_tt_j2000 },
};

std::variant<std::string, double> convert_time(
	const std::variant<std::string, double>& input,
	TimeFormat input_format,
	TimeFormat output_format
)
{
	DispatchKey key{ input_format, output_format };
	auto it = dispatchTable.find(key);
	if(it != dispatchTable.end())
	{
		const Handler& handler = it->second;
		if(handler.getInputType() == Handler::InputType::STRING
		   && !std::holds_alternative<std::string>(input))
		{
			throw std::invalid_argument("Expected input of type std::string for the given input TimeFormat");
		}
		else if(
			handler.getInputType() == Handler::InputType::DOUBLE && !std::holds_alternative<double>(input)
		)
		{
			throw std::invalid_argument("Expected input of type double for the given input TimeFormat");
		}
		return handler(input);
	}
	else
	{
		throw std::invalid_argument("Unsupported combination of input and output TimeFormat");
	}
}
