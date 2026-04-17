#pragma once

#include "convert_time.h"

#include <variant>

typedef std::variant<std::string, double> TimeValue;

std::variant<std::string, double> convert_time(
	const std::variant<std::string, double>& input,
	TimeFormat input_format,
	TimeFormat output_format
);