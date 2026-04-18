#pragma once

#include <algorithm>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace utc_tai_zoneinfo
{

struct LeapTransition
{
	std::int64_t unix_transition_seconds;
	int correction_seconds;
};

struct ParsedIsoUtc
{
	int year = 0;
	unsigned month = 0;
	unsigned day = 0;
	int hour = 0;
	int minute = 0;
	int second = 0;
	std::int64_t nanos = 0;
	int tz_offset_seconds = 0;
};

inline constexpr std::int64_t days_from_civil(int y, unsigned m, unsigned d) noexcept
{
	y -= m <= 2;
	const int era = (y >= 0 ? y : y - 399) / 400;
	const unsigned yoe = static_cast<unsigned>(y - era * 400);
	const unsigned doy = (153 * (m + (m > 2 ? -3 : 9)) + 2) / 5 + d - 1;
	const unsigned doe = yoe * 365 + yoe / 4 - yoe / 100 + doy;
	return static_cast<std::int64_t>(era) * 146097 + static_cast<std::int64_t>(doe) - 719468;
}

inline bool is_digit(char c)
{
	return c >= '0' && c <= '9';
}

inline std::string trim(const std::string& s)
{
	std::size_t first = 0;
	while(first < s.size() && std::isspace(static_cast<unsigned char>(s[first])))
	{
		++first;
	}

	std::size_t last = s.size();
	while(last > first && std::isspace(static_cast<unsigned char>(s[last - 1])))
	{
		--last;
	}

	return s.substr(first, last - first);
}

inline int parse_2(const std::string& s, std::size_t pos)
{
	if(pos + 2 > s.size() || !is_digit(s[pos]) || !is_digit(s[pos + 1]))
	{
		throw std::runtime_error("Invalid 2-digit ISO field at position " + std::to_string(pos));
	}
	return (s[pos] - '0') * 10 + (s[pos + 1] - '0');
}

inline int parse_4(const std::string& s, std::size_t pos)
{
	if(pos + 4 > s.size())
	{
		throw std::runtime_error("Invalid 4-digit ISO field at position " + std::to_string(pos));
	}
	for(std::size_t i = 0; i < 4; ++i)
	{
		if(!is_digit(s[pos + i]))
		{
			throw std::runtime_error("Invalid 4-digit ISO field at position " + std::to_string(pos));
		}
	}
	return (s[pos] - '0') * 1000 + (s[pos + 1] - '0') * 100 + (s[pos + 2] - '0') * 10 + (s[pos + 3] - '0');
}

inline ParsedIsoUtc parse_iso8601_utc(const std::string& iso)
{
	if(iso.size() < 19)
	{
		throw std::runtime_error("ISO-8601 input too short: " + iso);
	}

	ParsedIsoUtc out;

	out.year = parse_4(iso, 0);
	if(iso[4] != '-')
	{
		throw std::runtime_error("Expected '-' at position 4");
	}

	out.month = static_cast<unsigned>(parse_2(iso, 5));
	if(iso[7] != '-')
	{
		throw std::runtime_error("Expected '-' at position 7");
	}

	out.day = static_cast<unsigned>(parse_2(iso, 8));

	const char sep = iso[10];
	if(sep != 'T' && sep != ' ')
	{
		throw std::runtime_error("Expected 'T' or space at position 10");
	}

	out.hour = parse_2(iso, 11);
	if(iso[13] != ':')
	{
		throw std::runtime_error("Expected ':' at position 13");
	}

	out.minute = parse_2(iso, 14);
	if(iso[16] != ':')
	{
		throw std::runtime_error("Expected ':' at position 16");
	}

	out.second = parse_2(iso, 17);

	if(out.month < 1 || out.month > 12 || out.day < 1 || out.day > 31 || out.hour < 0 || out.hour > 23
	   || out.minute < 0 || out.minute > 59 || out.second < 0 || out.second > 60)
	{
		throw std::runtime_error("ISO-8601 field out of range: " + iso);
	}

	std::size_t pos = 19;
	if(pos < iso.size() && iso[pos] == '.')
	{
		++pos;
		std::size_t digits = 0;
		while(pos < iso.size() && is_digit(iso[pos]) && digits < 9)
		{
			out.nanos = out.nanos * 10 + (iso[pos] - '0');
			++pos;
			++digits;
		}
		while(pos < iso.size() && is_digit(iso[pos]))
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
	if(pos < iso.size() && iso[pos] == 'Z')
	{
		++pos;
	}
	else if(pos < iso.size() && (iso[pos] == '+' || iso[pos] == '-'))
	{
		const int sign = (iso[pos] == '-') ? -1 : 1;
		++pos;
		const int tzh = parse_2(iso, pos);
		pos += 2;
		if(pos >= iso.size() || iso[pos] != ':')
		{
			throw std::runtime_error("Expected ':' in timezone offset");
		}
		++pos;
		const int tzm = parse_2(iso, pos);
		pos += 2;

		if(tzh > 23 || tzm > 59)
		{
			throw std::runtime_error("Timezone offset out of range");
		}

		out.tz_offset_seconds = sign * (tzh * 3600 + tzm * 60);
	}

	while(pos < iso.size() && std::isspace(static_cast<unsigned char>(iso[pos])))
	{
		++pos;
	}
	if(pos != iso.size())
	{
		throw std::runtime_error("Unexpected trailing characters in ISO-8601 string: " + iso);
	}

	if(out.second == 60 && !(out.hour == 23 && out.minute == 59))
	{
		throw std::runtime_error("Leap-second notation is only valid at 23:59:60");
	}

	return out;
}

inline double iso_utc_to_unix_seconds_non_leap(const ParsedIsoUtc& p)
{
	const std::int64_t day_index = days_from_civil(p.year, p.month, p.day);

	std::int64_t sec_of_day = static_cast<std::int64_t>(p.hour) * 3600
		+ static_cast<std::int64_t>(p.minute) * 60 + static_cast<std::int64_t>(p.second);

	if(p.second == 60)
	{
		sec_of_day = 86400;
	}

	const std::int64_t unix_seconds = day_index * 86400 + sec_of_day - p.tz_offset_seconds;
	return static_cast<double>(unix_seconds) + static_cast<double>(p.nanos) * 1.0e-9;
}

inline int month_name_to_number(const std::string& month_name)
{
	static const std::array<const char*, 12> names = { "Jan", "Feb", "Mar", "Apr", "May", "Jun",
													   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec" };

	for(std::size_t i = 0; i < names.size(); ++i)
	{
		if(month_name == names[i])
		{
			return static_cast<int>(i) + 1;
		}
	}

	throw std::runtime_error("Invalid month token in leap-second file: " + month_name);
}

inline std::vector<LeapTransition> load_zoneinfo_leap_transitions(const std::string& leapseconds_path)
{
	std::ifstream in(leapseconds_path);
	if(!in)
	{
		throw std::runtime_error("Failed to open leap-second file: " + leapseconds_path);
	}

	std::vector<LeapTransition> out;
	std::string raw;
	while(std::getline(in, raw))
	{
		const std::string line = trim(raw);
		if(line.empty() || line[0] == '#')
		{
			continue;
		}

		std::istringstream iss(line);
		std::string keyword;
		iss >> keyword;
		if(keyword != "Leap")
		{
			continue;
		}

		int year = 0;
		std::string mon;
		int day = 0;
		std::string hhmmss;
		char sign = '\0';
		std::string unit;

		iss >> year >> mon >> day >> hhmmss >> sign >> unit;
		if(iss.fail())
		{
			throw std::runtime_error("Malformed Leap line: " + line);
		}
		if(sign != '+' && sign != '-')
		{
			throw std::runtime_error("Leap line must contain '+' or '-': " + line);
		}
		if(unit != "S")
		{
			throw std::runtime_error("Leap line unit must be 'S': " + line);
		}

		if(hhmmss.size() != 8 || hhmmss[2] != ':' || hhmmss[5] != ':')
		{
			throw std::runtime_error("Invalid Leap time field: " + line);
		}

		const int hh = (hhmmss[0] - '0') * 10 + (hhmmss[1] - '0');
		const int mm = (hhmmss[3] - '0') * 10 + (hhmmss[4] - '0');
		const int ss = (hhmmss[6] - '0') * 10 + (hhmmss[7] - '0');

		if(hh < 0 || hh > 23 || mm < 0 || mm > 59 || ss < 0 || ss > 60)
		{
			throw std::runtime_error("Leap line time out of range: " + line);
		}

		std::int64_t sec_of_day = static_cast<std::int64_t>(hh) * 3600 + static_cast<std::int64_t>(mm) * 60
			+ static_cast<std::int64_t>(ss);
		if(ss == 60)
		{
			sec_of_day = 86400;
		}

		const int month = month_name_to_number(mon);
		const std::int64_t unix_transition =
			days_from_civil(year, static_cast<unsigned>(month), static_cast<unsigned>(day)) * 86400
			+ sec_of_day;

		out.push_back(LeapTransition{ unix_transition, sign == '+' ? 1 : -1 });
	}

	std::sort(out.begin(), out.end(), [](const LeapTransition& a, const LeapTransition& b) {
		return a.unix_transition_seconds < b.unix_transition_seconds;
	});

	return out;
}

inline int cumulative_leap_correction(
	const std::vector<LeapTransition>& transitions,
	double utc_unix_seconds,
	bool include_transition_at_equal
)
{
	int sum = 0;
	for(const LeapTransition& t : transitions)
	{
		const double transition = static_cast<double>(t.unix_transition_seconds);
		if(transition < utc_unix_seconds || (include_transition_at_equal && transition == utc_unix_seconds))
		{
			sum += t.correction_seconds;
		}
	}
	return sum;
}

inline double utc_iso8601_to_tai_seconds_since_epoch(
	const std::string& utc_iso8601,
	const std::string& zoneinfo_leapseconds_path
)
{
	// Required epoch mapping:
	// TAI epoch = 2000-01-01 12:00:00 TAI = 2000-01-01 11:59:28 UTC
	constexpr std::int64_t tai_epoch_utc_unix =
		days_from_civil(2000, 1, 1) * 86400 + 11 * 3600 + 59 * 60 + 28;

	const ParsedIsoUtc utc = parse_iso8601_utc(utc_iso8601);
	const double utc_unix_seconds = iso_utc_to_unix_seconds_non_leap(utc);

	const std::vector<LeapTransition> transitions = load_zoneinfo_leap_transitions(zoneinfo_leapseconds_path);

	// At 23:59:60, UTC maps to the same Unix second as 00:00:00 next day.
	// For correct boundary behavior, that leap transition must not be counted yet.
	const bool include_transition_now = (utc.second != 60);
	const double utc_unix_for_leap_lookup =
		(utc.second == 60) ? std::floor(utc_unix_seconds) : utc_unix_seconds;
	const int leap_now = cumulative_leap_correction(
		transitions,
		utc_unix_for_leap_lookup,
		include_transition_now
	);
	const int leap_epoch =
		cumulative_leap_correction(transitions, static_cast<double>(tai_epoch_utc_unix), true);

	const double utc_elapsed_non_leap = utc_unix_seconds - static_cast<double>(tai_epoch_utc_unix);
	const int leap_delta = leap_now - leap_epoch;

	return utc_elapsed_non_leap + static_cast<double>(leap_delta);
}

} // namespace utc_tai_zoneinfo
