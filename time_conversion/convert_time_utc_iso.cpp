#include "convert_time.h"

#include <tudat/astro/basic_astro/dateTime.h>
#include <tudat/astro/earth_orientation/terrestrialTimeScaleConverter.h>
#include <chrono>

namespace
{
static const std::vector<LeapTransition> transitions =
	load_zoneinfo_leap_transitions(LEAPSECONDS_PATH_DEFAULT);

inline constexpr std::int64_t days_from_civil(int year, unsigned month, unsigned day) noexcept
{
	// Shift January and February to months 13 and 14 of the previous year so that
	// the leap day (Feb 29) always falls at the end of the shifted year, simplifying
	// the day-of-year calculation below.
	year -= (month <= 2 ? 1 : 0);

	// A 400-year Gregorian era contains exactly 146097 days. This gives the era index
	// and keeps subsequent offsets in the range [0, 146096].
	const int era = (year >= 0 ? year : year - 399) / 400;

	// Year within the era [0, 399].
	const unsigned year_of_era = static_cast<unsigned>(year - era * 400);

	// Day within the shifted year [0, 365].
	// The factor (153 * m + 2) / 5 encodes the non-uniform month lengths for
	// March–February layout without any branching beyond the month shift above.
	const unsigned day_of_year = (MONTH_LENGTH_ENCODING * (month + (month > 2 ? -3 : 9)) + 2) / 5 + day - 1;

	// Day within the era [0, 146096].
	// Adds one leap day per 4 years, subtracts the century non-leap years,
	// and the century-of-era correction is already embedded in year_of_era / 100.
	const unsigned day_of_era = year_of_era * 365 + year_of_era / 4 - year_of_era / 100 + day_of_year;

	// GREGORIAN_ERA_DAYS = days per 400-year era.
	// UNIX_EPOCH_DAY_OFFSET = days from the proleptic Gregorian epoch (0000-03-01) to the
	//                        Unix epoch (1970-01-01), used to produce a Unix day count.
	return static_cast<std::int64_t>(era) * GREGORIAN_ERA_DAYS + static_cast<std::int64_t>(day_of_era)
		- UNIX_EPOCH_DAY_OFFSET;
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
} // namespace

ParsedIsoUtc parse_iso8601_utc(const std::string& iso)
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

		out.tz_offset_seconds = sign * (tzh * SECONDS_PER_HOUR + tzm * SECONDS_PER_MINUTE);
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

std::vector<LeapTransition> load_zoneinfo_leap_transitions(const std::string& leapseconds_path)
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

		std::int64_t sec_of_day = 0;
		if(ss < 60)
		{
			sec_of_day = static_cast<std::int64_t>(hh) * SECONDS_PER_HOUR
				+ static_cast<std::int64_t>(mm) * SECONDS_PER_MINUTE + static_cast<std::int64_t>(ss);
		}
		else
		{
			sec_of_day = SECONDS_PER_DAY;
		}

		const int month = month_name_to_number(mon);
		const std::int64_t unix_transition =
			days_from_civil(year, static_cast<unsigned>(month), static_cast<unsigned>(day)) * SECONDS_PER_DAY
			+ sec_of_day;

		out.push_back(LeapTransition{ unix_transition, sign == '+' ? 1 : -1 });
	}

	std::sort(out.begin(), out.end(), [](const LeapTransition& a, const LeapTransition& b) {
		return a.unix_transition_seconds < b.unix_transition_seconds;
	});

	return out;
}

inline double cumulative_leap_correction(
	const std::vector<LeapTransition>& transitions,
	double utc_unix_seconds,
	bool include_transition_at_equal
)
{
	// Before UTC and TAI synchronization in 1972, UTC drifted relative to TAI.
	// Over 1970-01-01 <= UTC < 1972-01-01, use the historical linear segment
	constexpr std::int64_t unix_1970_01_01 = days_from_civil(1970, 1, 1) * SECONDS_PER_DAY;
	constexpr std::int64_t unix_1972_01_01 = days_from_civil(1972, 1, 1) * SECONDS_PER_DAY;

	double tai_minus_utc_seconds = POST_1972_TAI_MINUS_UTC;
	if(utc_unix_seconds < static_cast<double>(unix_1972_01_01))
	{
		const double elapsed_days_since_1970 =
			(utc_unix_seconds - static_cast<double>(unix_1970_01_01)) / static_cast<double>(SECONDS_PER_DAY);
		tai_minus_utc_seconds =
			PRE_1972_TAI_MINUS_UTC_AT_1970 + elapsed_days_since_1970 * PRE_1972_DRIFT_RATE;
	}

	for(const LeapTransition& t : transitions)
	{
		const double transition = static_cast<double>(t.unix_transition_seconds);
		if(transition < utc_unix_seconds || (include_transition_at_equal && transition == utc_unix_seconds))
		{
			tai_minus_utc_seconds += static_cast<double>(t.correction_seconds);
		}
	}
	return tai_minus_utc_seconds;
}
double iso_to_utc_tudat(const std::string& utc_iso8601)
{
	const ParsedIsoUtc utc = parse_iso8601_utc(utc_iso8601);
	const auto utc_unix_tp = iso_utc_to_unix_seconds_non_leap(utc);
	const double utc_unix_seconds = std::chrono::duration<double>(utc_unix_tp.time_since_epoch()).count();

	return utc_unix_seconds - POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
}

double iso_to_tai_tudat(const std::string& utc_iso8601)
{
	// Required epoch mapping:
	// TAI epoch = 2000-01-01 12:00:00 TAI = 2000-01-01 11:59:28 UTC
	constexpr std::int64_t tai_epoch_utc_unix =
		days_from_civil(2000, 1, 1) * SECONDS_PER_DAY + 11 * SECONDS_PER_HOUR + 59 * SECONDS_PER_MINUTE + 28;

	const ParsedIsoUtc utc = parse_iso8601_utc(utc_iso8601);
	const auto utc_unix_tp = iso_utc_to_unix_seconds_non_leap(utc);
	const double utc_unix_seconds = std::chrono::duration<double>(utc_unix_tp.time_since_epoch()).count();

	// At 23:59:60, UTC maps to the same Unix second as 00:00:00 next day.
	// For correct boundary behavior, that leap transition must not be counted yet.
	const bool include_transition_now = (utc.second != 60);
	const double utc_unix_for_leap_lookup = (utc.second == 60)
		? static_cast<double>(
			std::chrono::time_point_cast<std::chrono::seconds>(utc_unix_tp).time_since_epoch().count()
		)
		: utc_unix_seconds;
	const double leap_now =
		cumulative_leap_correction(transitions, utc_unix_for_leap_lookup, include_transition_now);
	const double leap_epoch =
		cumulative_leap_correction(transitions, static_cast<double>(tai_epoch_utc_unix), true);

	const double utc_elapsed_non_leap = utc_unix_seconds - static_cast<double>(tai_epoch_utc_unix);
	const double leap_delta = leap_now - leap_epoch;

	return utc_elapsed_non_leap + leap_delta;
}

// Tudat DateTime based implementations

double utc_iso_tudat_to_utc_posix(const std::string& iso_string)
{
	// Convert ISO 8601 string to POSIX timestamp

	try
	{
		return tudat::basic_astrodynamics::DateTime::fromIsoString(iso_string).epoch<double>()
			+ POSIX_EPOCH_MINUS_UTC_TUDAT_EPOCH;
	}
	catch(const std::exception& e)
	{
		std::cerr << "Error converting ISO string to POSIX timestamp: " << e.what() << "\n";

		return std::numeric_limits<double>::quiet_NaN();
	}
}
