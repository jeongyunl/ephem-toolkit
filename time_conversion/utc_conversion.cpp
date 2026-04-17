#include "utc_conversion.h"

#include <cctype>
#include <chrono>
#include <cstdint>
#include <stdexcept>
#include <string>
// C++20 or later
#if __cplusplus >= 202002L

// If GNU C++ library, version 14 or later includes std::chrono::parse
#if(!defined(_GLIBCXX_RELEASE)) || (defined(_GLIBCXX_RELEASE) && _GLIBCXX_RELEASE >= 14)
std::chrono::utc_time<std::chrono::nanoseconds> parse_iso8601_utc(const std::string& s)
{
	// Accepts e.g. "2026-04-17T12:34:56Z" or "2026-04-17 12:34:56Z"
	// %FT%T  -> YYYY-MM-DD'T'HH:MM:SS
	// %Ez    -> ISO 8601 offset / 'Z'
	std::chrono::utc_time<std::chrono::nanoseconds> tp;

	std::istringstream in(s);

	in >> std::chrono::parse("%FT%T%Ez", tp);

	if(in.fail())
	{
		// Try a slightly more permissive variant (space instead of 'T')
		in.clear();
		in.str(s);
		in >> std::chrono::parse("%F %T%Ez", tp);
	}

	if(in.fail())
	{
		throw std::runtime_error("Failed to parse ISO-8601 UTC time: " + s);
	}

	return tp;
}
#endif
#else
// Custom ISO-8601 parser for C++17 and earlier (does not model leap seconds
namespace
{

// Days-from-civil algorithm by Howard Hinnant (public domain)
// Returns number of days since 1970-01-01 (Unix epoch), for a proleptic Gregorian calendar.
constexpr std::int64_t days_from_civil(int y, unsigned m, unsigned d) noexcept
{
	y -= m <= 2;
	const int era = (y >= 0 ? y : y - 399) / 400;
	const unsigned yoe = static_cast<unsigned>(y - era * 400); // [0, 399]
	const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1; // [0, 365]
	const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy; // [0, 146096]
	return static_cast<std::int64_t>(era) * 146097 + static_cast<std::int64_t>(doe) - 719468;
}

inline bool is_digit(char c)
{
	return c >= '0' && c <= '9';
}

int parse_2(const std::string& s, std::size_t pos)
{
	if(pos + 2 > s.size() || !is_digit(s[pos]) || !is_digit(s[pos + 1]))
	{
		throw std::runtime_error("Invalid ISO-8601 field at position " + std::to_string(pos));
	}
	return (s[pos] - '0') * 10 + (s[pos + 1] - '0');
}

int parse_4(const std::string& s, std::size_t pos)
{
	if(pos + 4 > s.size())
	{
		throw std::runtime_error("Invalid ISO-8601 year at position " + std::to_string(pos));
	}
	for(std::size_t i = 0; i < 4; ++i)
	{
		if(!is_digit(s[pos + i]))
		{
			throw std::runtime_error("Invalid ISO-8601 year at position " + std::to_string(pos));
		}
	}
	return (s[pos] - '0') * 1000 + (s[pos + 1] - '0') * 100 + (s[pos + 2] - '0') * 10 + (s[pos + 3] - '0');
}

// Parses: YYYY-MM-DD[ T]HH:MM:SS[.fffffffff](Z|(+|-)HH:MM)
// Returns sys_time<nanoseconds> (Unix time). This does NOT model leap seconds.
std::chrono::sys_time<std::chrono::nanoseconds> parse_iso8601_sys_ns(const std::string& s)
{
	// Minimal length: "YYYY-MM-DDTHH:MM:SSZ" => 20
	if(s.size() < 20)
	{
		throw std::runtime_error("ISO-8601 string too short: " + s);
	}

	const int year = parse_4(s, 0);
	if(s[4] != '-')
	{
		throw std::runtime_error("Expected '-' at pos 4");
	}
	const unsigned month = static_cast<unsigned>(parse_2(s, 5));
	if(s[7] != '-')
	{
		throw std::runtime_error("Expected '-' at pos 7");
	}
	const unsigned day = static_cast<unsigned>(parse_2(s, 8));

	const char sep = s[10];
	if(sep != 'T' && sep != ' ')
	{
		throw std::runtime_error("Expected 'T' or space at pos 10");
	}

	const int hour = parse_2(s, 11);
	if(s[13] != ':')
	{
		throw std::runtime_error("Expected ':' at pos 13");
	}
	const int minute = parse_2(s, 14);
	if(s[16] != ':')
	{
		throw std::runtime_error("Expected ':' at pos 16");
	}
	const int second = parse_2(s, 17);

	// Fractional seconds
	std::size_t pos = 19;
	std::int64_t nanos = 0;
	if(pos < s.size() && s[pos] == '.')
	{
		++pos;
		std::size_t digits = 0;
		while(pos < s.size() && is_digit(s[pos]) && digits < 9)
		{
			nanos = nanos * 10 + (s[pos] - '0');
			++pos;
			++digits;
		}
		// Skip any extra fractional digits beyond nanoseconds (truncate)
		while(pos < s.size() && is_digit(s[pos]))
		{
			++pos;
		}
		while(digits < 9)
		{
			nanos *= 10;
			++digits;
		}
	}

	// Time zone
	int tz_offset_seconds = 0;
	if(pos >= s.size())
	{
		throw std::runtime_error("Missing timezone designator in: " + s);
	}

	if(s[pos] == 'Z')
	{
		++pos;
	}
	else if(s[pos] == '+' || s[pos] == '-')
	{
		const int sign = (s[pos] == '-') ? -1 : 1;
		++pos;
		const int tzh = parse_2(s, pos);
		pos += 2;
		if(pos >= s.size() || s[pos] != ':')
		{
			throw std::runtime_error("Expected ':' in timezone offset");
		}
		++pos;
		const int tzm = parse_2(s, pos);
		pos += 2;
		tz_offset_seconds = sign * (tzh * 3600 + tzm * 60);
	}
	else
	{
		throw std::runtime_error("Unsupported timezone designator in: " + s);
	}

	// Allow trailing whitespace only
	while(pos < s.size() && std::isspace(static_cast<unsigned char>(s[pos])))
	{
		++pos;
	}
	if(pos != s.size())
	{
		throw std::runtime_error("Unexpected trailing characters in: " + s);
	}

	// Build sys_time
	const std::int64_t days = days_from_civil(year, month, day);
	const std::int64_t sec_of_day = static_cast<std::int64_t>(hour) * 3600
		+ static_cast<std::int64_t>(minute) * 60 + static_cast<std::int64_t>(second);
	const std::int64_t total_seconds = days * 86400 + sec_of_day - tz_offset_seconds;

	return std::chrono::sys_time<std::chrono::nanoseconds>{ std::chrono::seconds{ total_seconds }
															+ std::chrono::nanoseconds{ nanos } };
}

} // namespace

// If your standard library lacks std::chrono::parse/from_stream, you can still parse ISO-8601
// manually and then convert to utc_time.
//
// NOTE: Converting sys_time -> utc_time requires C++20 chrono UTC support. If your library
// also lacks utc_clock support, keep sys_time as your canonical UTC representation.
std::chrono::utc_time<std::chrono::nanoseconds> parse_iso8601_utc(const std::string& s)
{
	const auto sys_tp = parse_iso8601_sys_ns(s);
	return std::chrono::utc_clock::from_sys(sys_tp);
}
#endif

int main()
{
	return 0;
}
