#pragma once

#include "time_converter.h"

#include <functional>
#include <map>
#include <type_traits>
#include <variant>

class TimeConverterChrono;

using DispatchKey = std::pair<TimeFormat, TimeFormat>;

class Handler
{
public:
	enum class BackendType
	{
		BASE,
		CHRONO
	};

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

	using WrappedCallable = std::function<TimeValue(const TimeValue&, const TimeConverterBase*)>;

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

	template <typename Obj>
	static constexpr BackendType deduceBackendType()
	{
		if constexpr(std::is_same_v<Obj, TimeConverterChrono>)
		{
			return BackendType::CHRONO;
		}
		else
		{
			return BackendType::BASE;
		}
	}

	template <
		typename Obj,
		typename Arg,
		typename Ret,
		std::enable_if_t<!IsChronoTimePoint<Ret>::value, int> = 0>
	Handler(Ret (Obj::*func)(Arg) const)
		: callable_([func](const TimeValue& input_time, const TimeConverterBase* tc_ptr) -> TimeValue {
			const auto* obj_ptr = static_cast<const Obj*>(tc_ptr);
			using BareArg = std::remove_cvref_t<Arg>;
			Arg arg = static_cast<Arg>(std::get<BareArg>(input_time));
			Ret out = (obj_ptr->*func)(arg);
			return TimeValue{ std::in_place_type<Ret>, std::move(out) };
		})
		, backend_type_(deduceBackendType<Obj>())
		, input_type_(deduceInputType<Arg>())
	{
	}

	template <
		typename Obj,
		typename Arg,
		typename Ret,
		std::enable_if_t<!IsChronoTimePoint<Ret>::value, int> = 0>
	Handler(Ret (Obj::*func)(const Arg&) const)
		: callable_([func](const TimeValue& input_time, const TimeConverterBase* tc_ptr) -> TimeValue {
			const auto* obj_ptr = static_cast<const Obj*>(tc_ptr);
			const auto& arg = std::get<std::remove_cvref_t<Arg>>(input_time);
			Ret out = (obj_ptr->*func)(arg);
			return TimeValue{ std::in_place_type<Ret>, std::move(out) };
		})
		, backend_type_(deduceBackendType<Obj>())
		, input_type_(deduceInputType<Arg>())
	{
	}

	template <typename Obj, typename Arg, typename Clock>
	Handler(std::chrono::time_point<Clock, typename Clock::duration> (Obj::*func)(Arg) const)
		: callable_([func](const TimeValue& input_time, const TimeConverterBase* tc_ptr) -> TimeValue {
			const auto* obj_ptr = static_cast<const Obj*>(tc_ptr);
			using BareArg = std::remove_cvref_t<Arg>;
			Arg arg = static_cast<Arg>(std::get<BareArg>(input_time));
			auto out = (obj_ptr->*func)(arg);
			using Ret = std::chrono::time_point<Clock, typename Clock::duration>;
			return TimeValue{ std::in_place_type<Ret>, std::move(out) };
		})
		, backend_type_(deduceBackendType<Obj>())
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
				const TimeConverterBase* tc_ptr
			) -> TimeValue {
				const auto* obj_ptr = static_cast<const Obj*>(tc_ptr);
				using BareArg = std::remove_cvref_t<Arg>;
				Arg arg = static_cast<Arg>(std::get<BareArg>(input_time));
				Ret out = (obj_ptr->*func)(arg, use_t_separator, fractional_second_places);
				return TimeValue{ std::in_place_type<Ret>, std::move(out) };
			}
		)
		, backend_type_(deduceBackendType<Obj>())
		, input_type_(deduceInputType<Arg>())
	{
	}

	TimeValue operator()(const TimeValue& input_time, const TimeConverterBase* tc_ptr) const
	{
		return callable_(input_time, tc_ptr);
	}

	explicit operator bool() const { return static_cast<bool>(callable_); }

	BackendType getBackendType() const { return backend_type_; }

	InputType getInputType() const { return input_type_; }

private:
	WrappedCallable callable_;
	BackendType backend_type_ = BackendType::BASE;
	InputType input_type_ = InputType::DOUBLE;
};
