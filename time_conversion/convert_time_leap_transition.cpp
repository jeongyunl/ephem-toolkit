#include "convert_time_leap_transition.h"

#include "convert_time_common.h"
#include "convert_time_iso8601.h"

#include <algorithm>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>

namespace
{
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
		const std::int64_t transition_posix_epoch =
			calendar_date_to_posix_days(year, static_cast<unsigned>(month), static_cast<unsigned>(day))
				* SECONDS_PER_DAY
			+ sec_of_day;

		out.push_back(LeapTransition{ transition_posix_epoch, sign == '+' ? 1 : -1 });
	}

	std::sort(out.begin(), out.end(), [](const LeapTransition& a, const LeapTransition& b) {
		return a.transition_posix_epoch < b.transition_posix_epoch;
	});

	return out;
}

namespace
{
static std::vector<LeapTransition> transitions = load_zoneinfo_leap_transitions(LEAPSECONDS_PATH_DEFAULT);
}

const std::vector<LeapTransition>& get_zoneinfo_leap_transitions()
{
	if(transitions.empty())
	{
		transitions = load_zoneinfo_leap_transitions(LEAPSECONDS_PATH_DEFAULT);
	}
	return transitions;
}

double cumulative_leap_correction(
	const std::vector<LeapTransition>& transitions,
	double posix_time,
	bool include_transition_at_equal
)
{
	constexpr double TRANSITION_COMPARISON_EPSILON_SECONDS = 1.0e-12;

	// Before UTC and TAI synchronization in 1972, UTC drifted relative to TAI.
	// Over 1970-01-01 <= UTC < 1972-01-01, use the historical linear segment
	constexpr std::int64_t posix_1970_01_01 = calendar_date_to_posix_days(1970, 1, 1) * SECONDS_PER_DAY;
	constexpr std::int64_t posix_1972_01_01 = calendar_date_to_posix_days(1972, 1, 1) * SECONDS_PER_DAY;

	double tai_minus_utc_seconds = POST_1972_TAI_MINUS_UTC;
	if(posix_time < static_cast<double>(posix_1972_01_01))
	{
		const double elapsed_days_since_1970 =
			(posix_time - static_cast<double>(posix_1970_01_01)) / static_cast<double>(SECONDS_PER_DAY);
		tai_minus_utc_seconds =
			PRE_1972_TAI_MINUS_UTC_AT_1970 + elapsed_days_since_1970 * PRE_1972_DRIFT_RATE;
	}

	for(const LeapTransition& t : transitions)
	{
		const double transition = static_cast<double>(t.transition_posix_epoch);
		const double delta = transition - posix_time;

		if(delta > TRANSITION_COMPARISON_EPSILON_SECONDS)
		{
			break;
		}

		if(std::abs(delta) <= TRANSITION_COMPARISON_EPSILON_SECONDS)
		{
			if(include_transition_at_equal)
			{
				tai_minus_utc_seconds += static_cast<double>(t.correction_seconds);
			}
			break;
		}

		if(delta < -TRANSITION_COMPARISON_EPSILON_SECONDS)
		{
			tai_minus_utc_seconds += static_cast<double>(t.correction_seconds);
		}
	}

	return tai_minus_utc_seconds;
}
