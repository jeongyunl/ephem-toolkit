#include "convert_time_iso8601.h"

#include "convert_time_common.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <format>
#include <fstream>
#include <stdexcept>

namespace
{

inline int parse_2_digits(const std::string& s, std::size_t pos)
{
	if(pos + 2 > s.size() || !std::isdigit(s[pos]) || !std::isdigit(s[pos + 1]))
	{
		throw std::runtime_error("Invalid 2-digit ISO field at position " + std::to_string(pos));
	}
	return (s[pos] - '0') * 10 + (s[pos + 1] - '0');
}

inline int parse_4_digits(const std::string& s, std::size_t pos)
{
	if(pos + 4 > s.size())
	{
		throw std::runtime_error("Invalid 4-digit ISO field at position " + std::to_string(pos));
	}
	for(std::size_t i = 0; i < 4; ++i)
	{
		if(!std::isdigit(s[pos + i]))
		{
			throw std::runtime_error("Invalid 4-digit ISO field at position " + std::to_string(pos));
		}
	}
	return (s[pos] - '0') * 1000 + (s[pos + 1] - '0') * 100 + (s[pos + 2] - '0') * 10 + (s[pos + 3] - '0');
}

} // namespace

ParsedUtcIso utc_iso_to_parsed_utc_iso(const std::string& utc_iso)
{
	if(utc_iso.size() < 19)
	{
		throw std::runtime_error("ISO-8601 input too short: " + utc_iso);
	}

	ParsedUtcIso out;

	out.year = parse_4_digits(utc_iso, 0);
	if(utc_iso[4] != '-')
	{
		throw std::runtime_error("Expected '-' at position 4");
	}

	out.month = static_cast<unsigned>(parse_2_digits(utc_iso, 5));
	if(utc_iso[7] != '-')
	{
		throw std::runtime_error("Expected '-' at position 7");
	}

	out.day = static_cast<unsigned>(parse_2_digits(utc_iso, 8));

	const char sep = utc_iso[10];
	if(sep != 'T' && sep != ' ')
	{
		throw std::runtime_error("Expected 'T' or space at position 10");
	}

	out.hour = parse_2_digits(utc_iso, 11);
	if(utc_iso[13] != ':')
	{
		throw std::runtime_error("Expected ':' at position 13");
	}

	out.minute = parse_2_digits(utc_iso, 14);
	if(utc_iso[16] != ':')
	{
		throw std::runtime_error("Expected ':' at position 16");
	}

	out.second = parse_2_digits(utc_iso, 17);

	if(out.month < 1 || out.month > 12 || out.day < 1 || out.day > 31 || out.hour < 0 || out.hour > 23
	   || out.minute < 0 || out.minute > 59 || out.second < 0 || out.second > 60)
	{
		throw std::runtime_error("ISO-8601 field out of range: " + utc_iso);
	}

	std::size_t pos = 19;
	if(pos < utc_iso.size() && utc_iso[pos] == '.')
	{
		++pos;
		std::size_t digits = 0;
		while(pos < utc_iso.size() && std::isdigit(utc_iso[pos]) && digits < 9)
		{
			out.nanos = out.nanos * 10 + (utc_iso[pos] - '0');
			++pos;
			++digits;
		}
		while(pos < utc_iso.size() && std::isdigit(utc_iso[pos]))
		{
			++pos;
		}
		while(digits < 9)
		{
			out.nanos *= 10;
			++digits;
		}
	}

	out.tz_offset_seconds = 0;
	if(pos < utc_iso.size() && utc_iso[pos] == 'Z')
	{
		++pos;
	}
	else if(pos < utc_iso.size() && (utc_iso[pos] == '+' || utc_iso[pos] == '-'))
	{
		const int sign = (utc_iso[pos] == '-') ? -1 : 1;
		++pos;
		const int tzh = parse_2_digits(utc_iso, pos);
		pos += 2;
		if(pos >= utc_iso.size() || utc_iso[pos] != ':')
		{
			throw std::runtime_error("Expected ':' in timezone offset");
		}
		++pos;
		const int tzm = parse_2_digits(utc_iso, pos);
		pos += 2;

		if(tzh > 23 || tzm > 59)
		{
			throw std::runtime_error("Timezone offset out of range");
		}

		out.tz_offset_seconds = sign * (tzh * SECONDS_PER_HOUR + tzm * SECONDS_PER_MINUTE);
	}

	while(pos < utc_iso.size() && std::isspace(static_cast<unsigned char>(utc_iso[pos])))
	{
		++pos;
	}
	if(pos != utc_iso.size())
	{
		throw std::runtime_error("Unexpected trailing characters in ISO-8601 string: " + utc_iso);
	}

	if(out.second == 60 && !(out.hour == 23 && out.minute == 59))
	{
		throw std::runtime_error("Leap-second notation is only valid at 23:59:60");
	}

	return out;
}

std::string parsed_utc_iso_to_utc_iso(
	const ParsedUtcIso& parsed_utc_iso,
	bool use_t_separator,
	int fractional_second_places
)
{
	if(parsed_utc_iso.month < 1 || parsed_utc_iso.month > 12 || parsed_utc_iso.day < 1
	   || parsed_utc_iso.day > 31 || parsed_utc_iso.hour < 0 || parsed_utc_iso.hour > 23
	   || parsed_utc_iso.minute < 0 || parsed_utc_iso.minute > 59 || parsed_utc_iso.second < 0
	   || parsed_utc_iso.second > 60 || parsed_utc_iso.nanos < 0
	   || parsed_utc_iso.nanos >= NANOSECONDS_PER_SECOND)
	{
		throw std::runtime_error("ParsedUtcIso field out of range");
	}

	if(parsed_utc_iso.second == 60 && !(parsed_utc_iso.hour == 23 && parsed_utc_iso.minute == 59))
	{
		throw std::runtime_error("Leap-second notation is only valid at 23:59:60");
	}

	if(parsed_utc_iso.tz_offset_seconds <= -SECONDS_PER_DAY
	   || parsed_utc_iso.tz_offset_seconds >= SECONDS_PER_DAY
	   || std::abs(parsed_utc_iso.tz_offset_seconds) % SECONDS_PER_MINUTE != 0)
	{
		throw std::runtime_error("Timezone offset out of range");
	}

	if(fractional_second_places < 0 || fractional_second_places > 9)
	{
		throw std::runtime_error("fractional_second_places must be between 0 and 9");
	}

	const char separator = use_t_separator ? 'T' : ' ';

	std::string out = std::format(
		"{:04}-{:02}-{:02}{}{:02}:{:02}:{:02}",
		parsed_utc_iso.year,
		parsed_utc_iso.month,
		parsed_utc_iso.day,
		separator,
		parsed_utc_iso.hour,
		parsed_utc_iso.minute,
		parsed_utc_iso.second
	);

	if(fractional_second_places > 0 && parsed_utc_iso.nanos != 0)
	{
		std::string fractional = std::to_string(parsed_utc_iso.nanos + NANOSECONDS_PER_SECOND).substr(1);

		if(fractional_second_places < 9)
		{
			fractional = fractional.substr(0, fractional_second_places);
		}

		while(!fractional.empty() && fractional.back() == '0')
		{
			fractional.pop_back();
		}

		if(!fractional.empty())
		{
			out += '.' + fractional;
		}
	}

	if(parsed_utc_iso.tz_offset_seconds == 0)
	{
		// Keep UTC output without an explicit timezone suffix.
		// out += 'Z';
	}
	else
	{
		const int offset_seconds = parsed_utc_iso.tz_offset_seconds;
		const char sign = (offset_seconds < 0) ? '-' : '+';
		const int abs_offset_seconds = std::abs(offset_seconds);
		const int offset_hours = abs_offset_seconds / SECONDS_PER_HOUR;
		const int offset_minutes = (abs_offset_seconds % SECONDS_PER_HOUR) / SECONDS_PER_MINUTE;
		out += std::format("{}{:02}:{:02}", sign, offset_hours, offset_minutes);
	}

	return out;
}
