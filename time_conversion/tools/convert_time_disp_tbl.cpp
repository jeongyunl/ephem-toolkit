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

	// Overload to accept functions returning std::chrono::system_clock::time_point (e.g. posix_to_sys_time).
	Handler(std::chrono::system_clock::time_point (*func)(double))
		: callable_([func](const TimeValue& input_time) -> TimeValue {
			double arg = std::get<double>(input_time);
			auto out = func(arg);
			return TimeValue{ std::in_place_type<std::chrono::system_clock::time_point>, std::move(out) };
		})
		, input_type_(InputType::DOUBLE)
	{
	}

	// Overload to accept functions returning std::chrono::system_clock::time_point (e.g.
	// utc_iso_to_sys_time).
	Handler(std::chrono::system_clock::time_point (*func)(const std::string&))
		: callable_([func](const TimeValue& input_time) -> TimeValue {
			const auto& arg = std::get<std::string>(input_time);
			auto out = func(arg);
			return TimeValue{ std::in_place_type<std::chrono::system_clock::time_point>, std::move(out) };
		})
		, input_type_(InputType::STRING)
	{
	}

#ifdef HAS_CHRONO_UTC_CLOCK
	// Overload to accept functions returning std::chrono::utc_clock::time_point (e.g. posix_to_utc_time).
	Handler(std::chrono::utc_clock::time_point (*func)(double))
		: callable_([func](const TimeValue& input_time) -> TimeValue {
			double arg = std::get<double>(input_time);
			auto out = func(arg);
			return TimeValue{ std::in_place_type<std::chrono::utc_clock::time_point>, std::move(out) };
		})
		, input_type_(InputType::DOUBLE)
	{
	}

	// Overload to accept functions returning std::chrono::utc_clock::time_point (e.g.
	// utc_iso_to_utc_time).
	Handler(std::chrono::utc_clock::time_point (*func)(const std::string&))
		: callable_([func](const TimeValue& input_time) -> TimeValue {
			const auto& arg = std::get<std::string>(input_time);
			auto out = func(arg);
			return TimeValue{ std::in_place_type<std::chrono::utc_clock::time_point>, std::move(out) };
		})
		, input_type_(InputType::STRING)
	{
	}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
	// Overload to accept functions returning std::chrono::tai_clock::time_point (e.g. posix_to_tai_time).
	Handler(std::chrono::tai_clock::time_point (*func)(double))
		: callable_([func](const TimeValue& input_time) -> TimeValue {
			double arg = std::get<double>(input_time);
			auto out = func(arg);
			return TimeValue{ std::in_place_type<std::chrono::tai_clock::time_point>, std::move(out) };
		})
		, input_type_(InputType::DOUBLE)
	{
	}

	// Overload to accept functions returning std::chrono::tai_clock::time_point (e.g.
	// utc_iso_to_tai_time).
	Handler(std::chrono::tai_clock::time_point (*func)(const std::string&))
		: callable_([func](const TimeValue& input_time) -> TimeValue {
			const auto& arg = std::get<std::string>(input_time);
			auto out = func(arg);
			return TimeValue{ std::in_place_type<std::chrono::tai_clock::time_point>, std::move(out) };
		})
		, input_type_(InputType::STRING)
	{
	}
#endif

	TimeValue operator()(const TimeValue& input_time) const { return callable_(input_time); }

	explicit operator bool() const { return static_cast<bool>(callable_); }

	InputType getInputType() const { return input_type_; }

private:
	WrappedCallable callable_;
	InputType input_type_ = InputType::DOUBLE;
};

std::map<DispatchKey, Handler> dispatchTable{
	{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_ISO8601 }, utc_iso_to_utc_iso },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::POSIX }, utc_iso_to_posix },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_J2000 }, utc_iso_to_utc_j2000 },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::TAI_J2000 }, utc_iso_to_tai_j2000 },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::TT_J2000 }, utc_iso_to_tt_j2000 },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_SYS_TIME_ISO }, utc_iso_to_sys_time },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_SYS_TIME }, utc_iso_to_sys_time },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_UTC_TIME_ISO }, utc_iso_to_utc_time },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_UTC_TIME }, utc_iso_to_utc_time },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_TAI_TIME_ISO }, utc_iso_to_tai_time },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_TAI_TIME }, utc_iso_to_tai_time },
#endif

	{ { TimeFormat::POSIX, TimeFormat::UTC_ISO8601 }, posix_to_utc_iso },
	{ { TimeFormat::POSIX, TimeFormat::POSIX }, posix_to_posix },
	{ { TimeFormat::POSIX, TimeFormat::UTC_J2000 }, posix_to_utc_j2000 },
	{ { TimeFormat::POSIX, TimeFormat::TAI_J2000 }, posix_to_tai_j2000 },
	{ { TimeFormat::POSIX, TimeFormat::TT_J2000 }, posix_to_tt_j2000 },
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_SYS_TIME_ISO }, posix_to_sys_time },
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_SYS_TIME }, posix_to_sys_time },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_UTC_TIME_ISO }, posix_to_utc_time },
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_UTC_TIME }, posix_to_utc_time },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_TAI_TIME_ISO }, posix_to_tai_time },
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_TAI_TIME }, posix_to_tai_time },
#endif

	{ { TimeFormat::UTC_J2000, TimeFormat::UTC_ISO8601 }, utc_j2000_to_utc_iso },
	{ { TimeFormat::UTC_J2000, TimeFormat::POSIX }, utc_j2000_to_posix },
	{ { TimeFormat::UTC_J2000, TimeFormat::UTC_J2000 }, utc_j2000_to_utc_j2000 },
	{ { TimeFormat::UTC_J2000, TimeFormat::TAI_J2000 }, utc_j2000_to_tai_j2000 },
	{ { TimeFormat::UTC_J2000, TimeFormat::TT_J2000 }, utc_j2000_to_tt_j2000 },
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_SYS_TIME_ISO }, utc_j2000_to_sys_time },
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_SYS_TIME }, utc_j2000_to_sys_time },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_UTC_TIME_ISO }, utc_j2000_to_utc_time },
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_UTC_TIME }, utc_j2000_to_utc_time },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_TAI_TIME_ISO }, utc_j2000_to_tai_time },
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_TAI_TIME }, utc_j2000_to_tai_time },
#endif

	{ { TimeFormat::TAI_J2000, TimeFormat::UTC_ISO8601 }, tai_j2000_to_utc_iso },
	{ { TimeFormat::TAI_J2000, TimeFormat::POSIX }, tai_j2000_to_posix },
	{ { TimeFormat::TAI_J2000, TimeFormat::UTC_J2000 }, tai_j2000_to_utc_j2000 },
	{ { TimeFormat::TAI_J2000, TimeFormat::TAI_J2000 }, tai_j2000_to_tai_j2000 },
	{ { TimeFormat::TAI_J2000, TimeFormat::TT_J2000 }, tai_j2000_to_tt_j2000 },
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_SYS_TIME_ISO }, tai_j2000_to_sys_time },
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_SYS_TIME }, tai_j2000_to_sys_time },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_UTC_TIME_ISO }, tai_j2000_to_utc_time },
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_UTC_TIME }, tai_j2000_to_utc_time },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_TAI_TIME_ISO }, tai_j2000_to_tai_time },
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_TAI_TIME }, tai_j2000_to_tai_time },
#endif

	{ { TimeFormat::TT_J2000, TimeFormat::UTC_ISO8601 }, tt_j2000_to_utc_iso },
	{ { TimeFormat::TT_J2000, TimeFormat::POSIX }, tt_j2000_to_posix },
	{ { TimeFormat::TT_J2000, TimeFormat::UTC_J2000 }, tt_j2000_to_utc_j2000 },
	{ { TimeFormat::TT_J2000, TimeFormat::TAI_J2000 }, tt_j2000_to_tai_j2000 },
	{ { TimeFormat::TT_J2000, TimeFormat::TT_J2000 }, tt_j2000_to_tt_j2000 },
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_SYS_TIME_ISO }, tt_j2000_to_sys_time },
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_SYS_TIME }, tt_j2000_to_sys_time },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_UTC_TIME_ISO }, tt_j2000_to_utc_time },
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_UTC_TIME }, tt_j2000_to_utc_time },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_TAI_TIME_ISO }, tt_j2000_to_tai_time },
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_TAI_TIME }, tt_j2000_to_tai_time },
#endif
};

TimeValue convert_time(const TimeValue& input, TimeFormat input_format, TimeFormat output_format)
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
		else if(handler.getInputType() == Handler::InputType::DOUBLE && !std::holds_alternative<double>(input))
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
