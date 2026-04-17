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
