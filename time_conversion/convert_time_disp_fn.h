#pragma once

#include "convert_time.h"

#include <stdexcept>
#include <variant>

// Runtime-based time conversion (input and output formats are not template arguments)
// Returns std::variant that can hold either std::string or double
// Input must be std::string if input_format is UTC_ISO_TUDAT, otherwise double

inline constexpr std::variant<std::string, double> convert_time(
	const std::variant<std::string, double>& input,
	TimeFormat input_format,
	TimeFormat output_format
)
{
	// Handle UTC_ISO_TUDAT input (string type)
	if(input_format == TimeFormat::UTC_ISO_TUDAT)
	{
		const auto& iso_string = std::get<std::string>(input);

		switch(output_format)
		{
			case TimeFormat::UTC_ISO_TUDAT:
				return utc_iso_tudat_to_utc_iso_tudat(iso_string);
			case TimeFormat::UTC_POSIX:
				return utc_iso_to_utc_posix(iso_string);
			case TimeFormat::UTC_TUDAT:
				return utc_iso_to_utc_tudat(iso_string);
			case TimeFormat::TAI_TUDAT:
				return utc_iso_to_tai_tudat(iso_string);
			case TimeFormat::TT_TUDAT:
				return utc_iso_to_tt_tudat(iso_string);
			default:
				throw std::invalid_argument("Unsupported output TimeFormat");
		}
	}

	// Handle all other input formats (double type)
	const double epoch = std::get<double>(input);

	switch(input_format)
	{
		case TimeFormat::UTC_POSIX:
			switch(output_format)
			{
				case TimeFormat::UTC_ISO_TUDAT:
					return utc_posix_to_utc_iso_tudat(epoch);
				case TimeFormat::UTC_POSIX:
					return utc_posix_to_utc_posix(epoch);
				case TimeFormat::UTC_TUDAT:
					return utc_posix_to_utc_tudat(epoch);
				case TimeFormat::TAI_TUDAT:
					return utc_posix_to_tai_tudat(epoch);
				case TimeFormat::TT_TUDAT:
					return utc_posix_to_tt_tudat(epoch);
				default:
					throw std::invalid_argument("Unsupported output TimeFormat");
			}
		case TimeFormat::UTC_TUDAT:
			switch(output_format)
			{
				case TimeFormat::UTC_ISO_TUDAT:
					return utc_tudat_to_utc_iso_tudat(epoch);
				case TimeFormat::UTC_POSIX:
					return utc_tudat_to_utc_posix(epoch);
				case TimeFormat::UTC_TUDAT:
					return utc_tudat_to_utc_tudat(epoch);
				case TimeFormat::TAI_TUDAT:
					return utc_tudat_to_tai_tudat(epoch);
				case TimeFormat::TT_TUDAT:
					return utc_tudat_to_tt_tudat(epoch);
				default:
					throw std::invalid_argument("Unsupported output TimeFormat");
			}
		case TimeFormat::TAI_TUDAT:
			switch(output_format)
			{
				case TimeFormat::UTC_ISO_TUDAT:
					return tai_tudat_to_utc_iso_tudat(epoch);
				case TimeFormat::UTC_POSIX:
					return tai_tudat_to_utc_posix(epoch);
				case TimeFormat::UTC_TUDAT:
					return tai_tudat_to_utc_tudat(epoch);
				case TimeFormat::TAI_TUDAT:
					return tai_tudat_to_tai_tudat(epoch);
				case TimeFormat::TT_TUDAT:
					return tai_tudat_to_tt_tudat(epoch);
				default:
					throw std::invalid_argument("Unsupported output TimeFormat");
			}
		case TimeFormat::TT_TUDAT:
			switch(output_format)
			{
				case TimeFormat::UTC_ISO_TUDAT:
					return tt_tudat_to_utc_iso_tudat(epoch);
				case TimeFormat::UTC_POSIX:
					return tt_tudat_to_utc_posix(epoch);
				case TimeFormat::UTC_TUDAT:
					return tt_tudat_to_utc_tudat(epoch);
				case TimeFormat::TAI_TUDAT:
					return tt_tudat_to_tai_tudat(epoch);
				case TimeFormat::TT_TUDAT:
					return tt_tudat_to_tt_tudat(epoch);
				default:
					throw std::invalid_argument("Unsupported output TimeFormat");
			}
		default:
			throw std::invalid_argument("Unsupported input TimeFormat");
	}
}
