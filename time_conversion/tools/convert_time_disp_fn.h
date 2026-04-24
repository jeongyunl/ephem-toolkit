#pragma once

#include "convert_time.h"

#include <stdexcept>
#include <variant>

// Runtime-based time conversion (input and output formats are not template arguments)
// Returns std::variant that can hold either std::string or double
// Input must be std::string if input_format is UTC_ISO_TUDAT, otherwise double

constexpr std::variant<std::string, double> convert_time(
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
				return utc_iso_to_utc_iso(iso_string);
			case TimeFormat::UTC_POSIX:
				return utc_iso_to_posix(iso_string);
			case TimeFormat::UTC_TUDAT:
				return utc_iso_to_utc_j2000(iso_string);
			case TimeFormat::TAI_TUDAT:
				return utc_iso_to_tai_j2000(iso_string);
			case TimeFormat::TT_TUDAT:
				return utc_iso_to_tt_j2000(iso_string);
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
					return posix_to_utc_iso(epoch);
				case TimeFormat::UTC_POSIX:
					return posix_to_posix(epoch);
				case TimeFormat::UTC_TUDAT:
					return posix_to_utc_j2000(epoch);
				case TimeFormat::TAI_TUDAT:
					return posix_to_tai_j2000(epoch);
				case TimeFormat::TT_TUDAT:
					return posix_to_tt_j2000(epoch);
				default:
					throw std::invalid_argument("Unsupported output TimeFormat");
			}
		case TimeFormat::UTC_TUDAT:
			switch(output_format)
			{
				case TimeFormat::UTC_ISO_TUDAT:
					return utc_j2000_to_utc_iso(epoch);
				case TimeFormat::UTC_POSIX:
					return utc_j2000_to_posix(epoch);
				case TimeFormat::UTC_TUDAT:
					return utc_j2000_to_utc_j2000(epoch);
				case TimeFormat::TAI_TUDAT:
					return utc_j2000_to_tai_j2000(epoch);
				case TimeFormat::TT_TUDAT:
					return utc_j2000_to_tt_j2000(epoch);
				default:
					throw std::invalid_argument("Unsupported output TimeFormat");
			}
		case TimeFormat::TAI_TUDAT:
			switch(output_format)
			{
				case TimeFormat::UTC_ISO_TUDAT:
					return tai_j2000_to_utc_iso(epoch);
				case TimeFormat::UTC_POSIX:
					return tai_j2000_to_posix(epoch);
				case TimeFormat::UTC_TUDAT:
					return tai_j2000_to_utc_j2000(epoch);
				case TimeFormat::TAI_TUDAT:
					return tai_j2000_to_tai_j2000(epoch);
				case TimeFormat::TT_TUDAT:
					return tai_j2000_to_tt_j2000(epoch);
				default:
					throw std::invalid_argument("Unsupported output TimeFormat");
			}
		case TimeFormat::TT_TUDAT:
			switch(output_format)
			{
				case TimeFormat::UTC_ISO_TUDAT:
					return tt_j2000_to_utc_iso(epoch);
				case TimeFormat::UTC_POSIX:
					return tt_j2000_to_posix(epoch);
				case TimeFormat::UTC_TUDAT:
					return tt_j2000_to_utc_j2000(epoch);
				case TimeFormat::TAI_TUDAT:
					return tt_j2000_to_tai_j2000(epoch);
				case TimeFormat::TT_TUDAT:
					return tt_j2000_to_tt_j2000(epoch);
				default:
					throw std::invalid_argument("Unsupported output TimeFormat");
			}
		default:
			throw std::invalid_argument("Unsupported input TimeFormat");
	}
}
