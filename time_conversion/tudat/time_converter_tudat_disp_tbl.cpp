#include "time_converter_tudat.h"
#include "../convert_time_common.h"

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

	using WrappedCallable = std::function<TimeValue(const TimeValue&, const TimeConverterTudat*)>;

	Handler() = default;

	template <typename Obj, typename Arg, typename Ret>
	Handler(Ret (Obj::*func)(Arg) const)
		: callable_([func](const TimeValue& input_time, const TimeConverterTudat* tc_ptr) -> TimeValue {
			using BareArg = std::remove_cvref_t<Arg>;
			Arg arg = static_cast<Arg>(std::get<BareArg>(input_time));
			Ret out = (tc_ptr->*func)(arg);
			return TimeValue{ std::in_place_type<Ret>, std::move(out) };
		})
		, input_type_(std::is_same_v<Arg, std::string> ? InputType::STRING : InputType::DOUBLE)
	{
	}

	template <typename Obj, typename Arg, typename Ret>
	Handler(Ret (Obj::*func)(const Arg&) const)
		: callable_([func](const TimeValue& input_time, const TimeConverterTudat* tc_ptr) -> TimeValue {
			using BareArg = std::remove_cvref_t<Arg>;
			const auto& arg = std::get<BareArg>(input_time);
			Ret out = (tc_ptr->*func)(arg);
			return TimeValue{ std::in_place_type<Ret>, std::move(out) };
		})
		, input_type_(
			  std::is_same_v<std::remove_cvref_t<Arg>, std::string> ? InputType::STRING : InputType::DOUBLE
		  )
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
				  const TimeConverterTudat* tc_ptr
			  ) -> TimeValue {
				  using BareArg = std::remove_cvref_t<Arg>;
				  Arg arg = static_cast<Arg>(std::get<BareArg>(input_time));
				  Ret out = (tc_ptr->*func)(arg, use_t_separator, fractional_second_places);
				  return TimeValue{ std::in_place_type<Ret>, std::move(out) };
			  }
		  )
		, input_type_(std::is_same_v<Arg, std::string> ? InputType::STRING : InputType::DOUBLE)
	{
	}

	TimeValue operator()(const TimeValue& input_time, const TimeConverterTudat* tc_ptr) const
	{
		return callable_(input_time, tc_ptr);
	}

	explicit operator bool() const { return static_cast<bool>(callable_); }

	InputType getInputType() const { return input_type_; }

private:
	WrappedCallable callable_;
	InputType input_type_ = InputType::DOUBLE;
};

std::map<DispatchKey, Handler> dispatchTable{
	{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_ISO8601 }, &TimeConverterTudat::utc_iso_to_utc_iso },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::POSIX }, &TimeConverterTudat::utc_iso_to_posix },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_J2000 }, &TimeConverterTudat::utc_iso_to_utc_j2000 },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::TAI_J2000 }, &TimeConverterTudat::utc_iso_to_tai_j2000 },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::TT_J2000 }, &TimeConverterTudat::utc_iso_to_tt_j2000 },
	{ { TimeFormat::UTC_ISO8601, TimeFormat::TDB_J2000 }, &TimeConverterTudat::utc_iso_to_tdb_j2000 },

	{ { TimeFormat::POSIX, TimeFormat::UTC_ISO8601 }, &TimeConverterTudat::posix_to_utc_iso },
	{ { TimeFormat::POSIX, TimeFormat::POSIX }, &TimeConverterTudat::posix_to_posix },
	{ { TimeFormat::POSIX, TimeFormat::UTC_J2000 }, &TimeConverterTudat::posix_to_utc_j2000 },
	{ { TimeFormat::POSIX, TimeFormat::TAI_J2000 }, &TimeConverterTudat::posix_to_tai_j2000 },
	{ { TimeFormat::POSIX, TimeFormat::TT_J2000 }, &TimeConverterTudat::posix_to_tt_j2000 },

	{ { TimeFormat::UTC_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterTudat::utc_j2000_to_utc_iso },
	{ { TimeFormat::UTC_J2000, TimeFormat::POSIX }, &TimeConverterTudat::utc_j2000_to_posix },
	{ { TimeFormat::UTC_J2000, TimeFormat::UTC_J2000 }, &TimeConverterTudat::utc_j2000_to_utc_j2000 },
	{ { TimeFormat::UTC_J2000, TimeFormat::TAI_J2000 }, &TimeConverterTudat::utc_j2000_to_tai_j2000 },
	{ { TimeFormat::UTC_J2000, TimeFormat::TT_J2000 }, &TimeConverterTudat::utc_j2000_to_tt_j2000 },

	{ { TimeFormat::TAI_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterTudat::tai_j2000_to_utc_iso },
	{ { TimeFormat::TAI_J2000, TimeFormat::POSIX }, &TimeConverterTudat::tai_j2000_to_posix },
	{ { TimeFormat::TAI_J2000, TimeFormat::UTC_J2000 }, &TimeConverterTudat::tai_j2000_to_utc_j2000 },
	{ { TimeFormat::TAI_J2000, TimeFormat::TAI_J2000 }, &TimeConverterTudat::tai_j2000_to_tai_j2000 },
	{ { TimeFormat::TAI_J2000, TimeFormat::TT_J2000 }, &TimeConverterTudat::tai_j2000_to_tt_j2000 },

	{ { TimeFormat::TT_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterTudat::tt_j2000_to_utc_iso },
	{ { TimeFormat::TT_J2000, TimeFormat::POSIX }, &TimeConverterTudat::tt_j2000_to_posix },
	{ { TimeFormat::TT_J2000, TimeFormat::UTC_J2000 }, &TimeConverterTudat::tt_j2000_to_utc_j2000 },
	{ { TimeFormat::TT_J2000, TimeFormat::TAI_J2000 }, &TimeConverterTudat::tt_j2000_to_tai_j2000 },
	{ { TimeFormat::TT_J2000, TimeFormat::TT_J2000 }, &TimeConverterTudat::tt_j2000_to_tt_j2000 },
};

TimeValue TimeConverterTudat::convert_time(
	const TimeValue& input,
	TimeFormat input_format,
	TimeFormat output_format
) const
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
		return handler(input, this);
	}
	else
	{
		throw std::invalid_argument("Unsupported combination of input and output TimeFormat");
	}
}
