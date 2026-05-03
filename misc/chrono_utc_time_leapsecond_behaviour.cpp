#include <chrono>
#include <iostream>

int main()
{
	using namespace std::chrono;

	struct TestCase
	{
		const char* iso;
	};

	const TestCase cases[] = {
		{ "2016-12-31 23:59:59" },
		{ "2016-12-31 23:59:60" },
		{ "2017-01-01 00:00:00" },
	};

	for(const auto& tc : cases)
	{
		try
		{
			for(int i = 0; i < 10; ++i)
			{
				std::chrono::utc_clock::time_point utc_tp;
				std::chrono::system_clock::time_point sys_tp;

				{
					std::string iso_string = tc.iso;

					iso_string += "." + std::to_string(i);

					std::istringstream(iso_string) >> std::chrono::parse("%F %T", utc_tp);
					std::istringstream(iso_string) >> std::chrono::parse("%F %T", sys_tp);

					auto leap_second_info = std::chrono::get_leap_second_info(utc_tp);

					std::chrono::system_clock::time_point sys_tp_from_utc;

					if(leap_second_info.is_leap_second)
					{
						// For any time point during a leap second, std::chrono::utc_clock::to_sys() returns
						// 23:59:59.999999999.
						// e.g. The time points: 2016-12-31 23:59:60.0, 2016-12-31 23:59:60.1, 2016-12-31
						// 23:59:60.999 all map to 2016-12-31 23:59:59.999999999 in sys_time. To get the
						// correct POSIX epoch, we must subtract one second from the UTC time point before
						// conversion, then add it back afterward.

						sys_tp_from_utc = std::chrono::utc_clock::to_sys(utc_tp - std::chrono::seconds{ 1 });

						sys_tp_from_utc += std::chrono::seconds{ 1 };
					}
					else
					{
						sys_tp_from_utc = std::chrono::utc_clock::to_sys(utc_tp);
					}

					std::cout << "Parsed '" << iso_string << "'\n";
					std::cout << "as utc_time: " << utc_tp << "\n";
					std::cout << "as sys_time: " << sys_tp << "\n";
					std::cout << "utc to sys : " << sys_tp_from_utc << "\n";
					std::cout << "\n";
				}
			}
		}
		catch(const std::exception& ex)
		{
			std::cerr << "Error parsing '" << tc.iso << "': " << ex.what() << "\n";
		}
	}

	return 0;
}
