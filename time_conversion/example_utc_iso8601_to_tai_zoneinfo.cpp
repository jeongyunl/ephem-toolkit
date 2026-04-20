#include "utc_iso8601_to_tai_zoneinfo.h"

#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

#ifdef _LIBCPP_STD_VER
#include <tzfile.h>
#endif

#ifdef TZDIR
// System tzdata directory is available at compile time.
#define ZONEINFO_DIR TZDIR
#elif defined(_GLIBCXX_ZONEINFO_DIR)
// GNU libstdc++ provides a compile-time macro for the tzdata directory.
#define ZONEINFO_DIR _GLIBCXX_ZONEINFO_DIR
#else
// Fallback default path (may not exist on all systems)
#define ZONEINFO_DIR "/usr/share/zoneinfo"
#endif

#define LEAPSECONDS_PATH_DEFAULT ZONEINFO_DIR "/leapseconds"

int main(int argc, char* argv[])
{
	// Usage:
	//   ./example_utc_iso8601_to_tai_zoneinfo /path/to/leapseconds
	// If omitted, a common system default is used.
	const std::string leap_file = (argc > 1) ? std::string(argv[1]) : std::string(LEAPSECONDS_PATH_DEFAULT);

	struct ExampleCase
	{
		std::string utc_iso;
		std::string label;
	};

	const std::vector<ExampleCase> cases = {
		{ "1970-01-01 00:00:00", "Unix epoch in UTC" },
		{ "1971-01-01 00:00:00", "" },
		{ "1971-06-01 00:00:00", "" },
		{ "1971-11-01 00:00:00", "" },
		{ "1971-12-01 00:00:00", "" },
		{ "1972-01-01 00:00:00", "" },
		{ "2000-01-01 12:00:00", "UTC J2000 epoch" },
		{ "2000-01-01T11:59:28", "TAI epoch in UTC (expect 0)" },
		{ "2016-12-31 23:59:59", "Second before leap-second instant" },
		{ "2016-12-31T23:59:59.5", "A half second before leap-second instant" },
		{ "2016-12-31T23:59:60", "Leap-second instant" },
		{ "2016-12-31T23:59:60.5", "Halfway through leap second" },
		{ "2017-01-01T00:00:00", "Immediately after leap second" },
		{ "2017-01-01T00:00:00.5", "A half second after leap second" },
	};

	std::cout << "Using leap-second file: " << leap_file << "\n\n";
	std::cout << std::fixed << std::setprecision(3);

	try
	{
		for(const auto& c : cases)
		{
			const double tai_seconds =
				utc_tai_zoneinfo::utc_iso8601_to_tai_seconds_since_epoch(c.utc_iso, leap_file);

			std::cout << c.label << "\n";
			std::cout << "  UTC ISO-8601: " << c.utc_iso << "\n";
			std::cout << "  TAI seconds since 2000-01-01 12:00:00 TAI: " << tai_seconds << "\n";
			std::cout << "  POSIX epoch seconds: " << utc_tai_zoneinfo::utc_iso8601_to_posix_epoch(c.utc_iso)
					  << "\n";
			std::cout << "  Sys time: " << utc_tai_zoneinfo::utc_iso8601_to_sys_time(c.utc_iso)
					  << "\n"; // Also test that sys_time conversion works without exceptions

			std::cout << "\n";
		}
	}
	catch(const std::exception& e)
	{
		std::cerr << "Conversion failed: " << e.what() << "\n";
		return 1;
	}

	return 0;
}
