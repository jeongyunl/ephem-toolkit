#include <chrono>
#include <iostream>

int main()
{
	using namespace std::chrono;

	std::cout << " sys_time epoch: " << system_clock::time_point{} << "\n";
	std::cout << " sys_time epoch as chrono::duration: " << system_clock::time_point{}.time_since_epoch()
			  << "\n";
	std::cout << "\n";

	std::cout << " utc_time epoch: " << utc_clock::time_point{} << "\n";
	std::cout << " utc_time epoch as chrono::duration: " << utc_clock::time_point{}.time_since_epoch()
			  << "\n";
	std::cout << "\n";

	// tai_time epoch is 1958-01-01 00:00:00 TAI = 1957-12-31 23:59:50 UTC
	std::cout << " tai_time epoch is 1958-01-01 00:00:00 TAI = 1957-12-31 23:59:50 UTC\n";

	std::cout << " tai_time epoch: " << tai_clock::time_point{} << "\n";
	std::cout << " tai_time epoch as chrono::duration: " << tai_clock::time_point{}.time_since_epoch()
			  << "\n";
	std::cout << " tai_time epoch as utc_time: " << tai_clock::to_utc(tai_clock::time_point{}) << "\n";
	std::cout << "\n";

	auto tai_from_utc = std::chrono::tai_clock::from_utc(utc_clock::time_point{});
	std::cout << " tai_from_utc (utc_time epoch): " << tai_from_utc << "\n";
	std::cout << " tai_from_utc as chrono::duration: " << tai_from_utc.time_since_epoch();
	std::cout << " tai_from_utc as utc_time: " << tai_clock::to_utc(tai_from_utc) << "\n";
	std::cout << "\n";

	return 0;
}
