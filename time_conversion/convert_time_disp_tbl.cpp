#include "time_converter.h"

#include <functional>
#include <map>
#include <stdexcept>
#include <type_traits>
#include <variant>

using DispatchKey = std::pair<TimeFormat, TimeFormat>;

class Handler
{
public:
	enum class InputType
	{
		DOUBLE,
		STRING,
		SYS_TIME,
#ifdef HAS_CHRONO_UTC_CLOCK
		UTC_TIME,
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
		TAI_TIME
#endif
	};

	using WrappedCallable = std::function<TimeValue(const TimeValue&, const TimeConverter*)>;

	template <typename T>
	struct IsChronoTimePoint : std::false_type
	{
	};

	template <typename Clock, typename Duration>
	struct IsChronoTimePoint<std::chrono::time_point<Clock, Duration>> : std::true_type
	{
	};

	Handler() = default;

	template <typename Arg>
	static constexpr InputType deduceInputType()
	{
		using BareArg = std::remove_cvref_t<Arg>;
		if constexpr(std::is_same_v<BareArg, std::string>)
		{
			return InputType::STRING;
		}
		else if constexpr(std::is_same_v<BareArg, std::chrono::system_clock::time_point>)
		{
			return InputType::SYS_TIME;
		}
#ifdef HAS_CHRONO_UTC_CLOCK
		else if constexpr(std::is_same_v<BareArg, std::chrono::utc_clock::time_point>)
		{
			return InputType::UTC_TIME;
		}
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
		else if constexpr(std::is_same_v<BareArg, std::chrono::tai_clock::time_point>)
		{
			return InputType::TAI_TIME;
		}
#endif
		else
		{
			return InputType::DOUBLE;
		}
	}

	template <
		typename Obj,
		typename Arg,
		typename Ret,
		std::enable_if_t<!IsChronoTimePoint<Ret>::value, int> = 0>
	Handler(Ret (Obj::*func)(Arg) const)
		: callable_([func](const TimeValue& input_time, const TimeConverter* tc_ptr) -> TimeValue {
			using BareArg = std::remove_cvref_t<Arg>;
			Arg arg = static_cast<Arg>(std::get<BareArg>(input_time));
			Ret out = (tc_ptr->*func)(arg);
			return TimeValue{ std::in_place_type<Ret>, std::move(out) };
		})
		, input_type_(deduceInputType<Arg>())
	{
	}

	template <
		typename Obj,
		typename Arg,
		typename Ret,
		std::enable_if_t<!IsChronoTimePoint<Ret>::value, int> = 0>
	Handler(Ret (Obj::*func)(const Arg&) const)
		: callable_([func](const TimeValue& input_time, const TimeConverter* tc_ptr) -> TimeValue {
			const auto& arg = std::get<std::remove_cvref_t<Arg>>(input_time);
			Ret out = (tc_ptr->*func)(arg);
			return TimeValue{ std::in_place_type<Ret>, std::move(out) };
		})
		, input_type_(deduceInputType<Arg>())
	{
	}

	template <typename Obj, typename Arg, typename Clock>
	Handler(std::chrono::time_point<Clock, typename Clock::duration> (Obj::*func)(Arg) const)
		: callable_([func](const TimeValue& input_time, const TimeConverter* tc_ptr) -> TimeValue {
			using BareArg = std::remove_cvref_t<Arg>;
			Arg arg = static_cast<Arg>(std::get<BareArg>(input_time));
			auto out = (tc_ptr->*func)(arg);
			using Ret = std::chrono::time_point<Clock, typename Clock::duration>;
			return TimeValue{ std::in_place_type<Ret>, std::move(out) };
		})
		, input_type_(deduceInputType<Arg>())
	{
	}

	template <typename Obj, typename Arg, typename Ret>
	Handler(
		Ret (Obj::*func)(Arg, bool, int) const,
		bool use_t_separator = false,
		int fractional_second_places = 3
	)
		: callable_(
			  [func, use_t_separator, fractional_second_places](
				  const TimeValue& input_time,
				  const TimeConverter* tc_ptr
			  ) -> TimeValue {
				  using BareArg = std::remove_cvref_t<Arg>;
				  Arg arg = static_cast<Arg>(std::get<BareArg>(input_time));
				  Ret out = (tc_ptr->*func)(arg, use_t_separator, fractional_second_places);
				  return TimeValue{ std::in_place_type<Ret>, std::move(out) };
			  }
		  )
		, input_type_(deduceInputType<Arg>())
	{
	}

	TimeValue operator()(const TimeValue& input_time, const TimeConverter* tc_ptr) const
	{
		return callable_(input_time, tc_ptr);
	}

	explicit operator bool() const { return static_cast<bool>(callable_); }

	InputType getInputType() const { return input_type_; }

private:
	WrappedCallable callable_;
	InputType input_type_ = InputType::DOUBLE;
};

namespace
{
} // namespace

std::map<DispatchKey, Handler> dispatchTable{
	{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_ISO8601 }, &TimeConverter::utc_iso_to_utc_iso },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::POSIX }, &TimeConverter::utc_iso_to_posix },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_J2000 }, &TimeConverter::utc_iso_to_utc_j2000 },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::TAI_J2000 }, &TimeConverter::utc_iso_to_tai_j2000 },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::TT_J2000 }, &TimeConverter::utc_iso_to_tt_j2000 },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverter::utc_iso_to_sys_time<> },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_SYS_TIME }, &TimeConverter::utc_iso_to_sys_time<> },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_UTC_TIME_ISO }, &TimeConverter::utc_iso_to_utc_time<> },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_UTC_TIME }, &TimeConverter::utc_iso_to_utc_time<> },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_TAI_TIME_ISO }, &TimeConverter::utc_iso_to_tai_time<> },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_TAI_TIME }, &TimeConverter::utc_iso_to_tai_time<> },
#endif

	{ { TimeFormat::POSIX, TimeFormat::UTC_ISO8601 }, &TimeConverter::posix_to_utc_iso },
	{ { TimeFormat::POSIX, TimeFormat::POSIX }, &TimeConverter::posix_to_posix },
	{ { TimeFormat::POSIX, TimeFormat::UTC_J2000 }, &TimeConverter::posix_to_utc_j2000 },
	{ { TimeFormat::POSIX, TimeFormat::TAI_J2000 }, &TimeConverter::posix_to_tai_j2000 },
	{ { TimeFormat::POSIX, TimeFormat::TT_J2000 }, &TimeConverter::posix_to_tt_j2000 },
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverter::posix_to_sys_time<> },
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_SYS_TIME }, &TimeConverter::posix_to_sys_time<> },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_UTC_TIME_ISO }, &TimeConverter::posix_to_utc_time<> },
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_UTC_TIME }, &TimeConverter::posix_to_utc_time<> },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_TAI_TIME_ISO }, &TimeConverter::posix_to_tai_time<> },
	{ { TimeFormat::POSIX, TimeFormat::CHRONO_TAI_TIME }, &TimeConverter::posix_to_tai_time<> },
#endif

	{ { TimeFormat::UTC_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverter::utc_j2000_to_utc_iso },
	{ { TimeFormat::UTC_J2000, TimeFormat::POSIX }, &TimeConverter::utc_j2000_to_posix },
	{ { TimeFormat::UTC_J2000, TimeFormat::UTC_J2000 }, &TimeConverter::utc_j2000_to_utc_j2000 },
	{ { TimeFormat::UTC_J2000, TimeFormat::TAI_J2000 }, &TimeConverter::utc_j2000_to_tai_j2000 },
	{ { TimeFormat::UTC_J2000, TimeFormat::TT_J2000 }, &TimeConverter::utc_j2000_to_tt_j2000 },
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverter::utc_j2000_to_sys_time<> },
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_SYS_TIME }, &TimeConverter::utc_j2000_to_sys_time<> },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_UTC_TIME_ISO }, &TimeConverter::utc_j2000_to_utc_time<> },
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_UTC_TIME }, &TimeConverter::utc_j2000_to_utc_time<> },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_TAI_TIME_ISO }, &TimeConverter::utc_j2000_to_tai_time<> },
	{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_TAI_TIME }, &TimeConverter::utc_j2000_to_tai_time<> },
#endif

	{ { TimeFormat::TAI_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverter::tai_j2000_to_utc_iso },
	{ { TimeFormat::TAI_J2000, TimeFormat::POSIX }, &TimeConverter::tai_j2000_to_posix },
	{ { TimeFormat::TAI_J2000, TimeFormat::UTC_J2000 }, &TimeConverter::tai_j2000_to_utc_j2000 },
	{ { TimeFormat::TAI_J2000, TimeFormat::TAI_J2000 }, &TimeConverter::tai_j2000_to_tai_j2000 },
	{ { TimeFormat::TAI_J2000, TimeFormat::TT_J2000 }, &TimeConverter::tai_j2000_to_tt_j2000 },
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverter::tai_j2000_to_sys_time<> },
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_SYS_TIME }, &TimeConverter::tai_j2000_to_sys_time<> },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_UTC_TIME_ISO }, &TimeConverter::tai_j2000_to_utc_time<> },
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_UTC_TIME }, &TimeConverter::tai_j2000_to_utc_time<> },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_TAI_TIME_ISO }, &TimeConverter::tai_j2000_to_tai_time<> },
	{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_TAI_TIME }, &TimeConverter::tai_j2000_to_tai_time<> },
#endif

	{ { TimeFormat::TT_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverter::tt_j2000_to_utc_iso },
	{ { TimeFormat::TT_J2000, TimeFormat::POSIX }, &TimeConverter::tt_j2000_to_posix },
	{ { TimeFormat::TT_J2000, TimeFormat::UTC_J2000 }, &TimeConverter::tt_j2000_to_utc_j2000 },
	{ { TimeFormat::TT_J2000, TimeFormat::TAI_J2000 }, &TimeConverter::tt_j2000_to_tai_j2000 },
	{ { TimeFormat::TT_J2000, TimeFormat::TT_J2000 }, &TimeConverter::tt_j2000_to_tt_j2000 },
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverter::tt_j2000_to_sys_time<> },
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_SYS_TIME }, &TimeConverter::tt_j2000_to_sys_time<> },
#ifdef HAS_CHRONO_UTC_CLOCK
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_UTC_TIME_ISO }, &TimeConverter::tt_j2000_to_utc_time<> },
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_UTC_TIME }, &TimeConverter::tt_j2000_to_utc_time<> },
#endif
#ifdef HAS_CHRONO_TAI_CLOCK
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_TAI_TIME_ISO }, &TimeConverter::tt_j2000_to_tai_time<> },
	{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_TAI_TIME }, &TimeConverter::tt_j2000_to_tai_time<> },
#endif
};

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
		return handler(input, this);
	}
	else
	{
		throw std::invalid_argument("Unsupported combination of input and output TimeFormat");
	}
}
