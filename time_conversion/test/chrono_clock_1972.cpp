#include <chrono>
#include <iostream>

using namespace std::chrono;

template <typename Duration = std::chrono::system_clock::duration>
constexpr std::chrono::time_point<std::chrono::system_clock, Duration> UTC_1970_EPOCH_IN_SYS_TIME{};

template <typename Duration = std::chrono::system_clock::duration>
constexpr std::chrono::time_point<std::chrono::system_clock, Duration> UTC_1972_EPOCH_IN_SYS_TIME = {
	sys_days{ 1972y / January / 1 }
};

template <typename Duration = std::chrono::utc_clock::duration>
constexpr std::chrono::time_point<std::chrono::utc_clock, Duration> UTC_1970_EPOCH_IN_UTC_TIME{};

template <typename Duration = std::chrono::system_clock::duration>
constexpr std::chrono::time_point<std::chrono::system_clock, Duration> TAI_J2000_EPOCH_IN_SYS_TIME = {
	sys_days{ 2000y / January / 1 } + hours{ 11 } + minutes{ 59 } + seconds{ 28 }
};

constexpr long TAI_J2000_EPOCH_IN_POSIX_TIME = 946727968L;
constexpr double TAI_MINUS_UTC_AT_J2000 = 32.0; // TAI-UTC at J2000 epoch (s)
constexpr double TAI_MINUS_UTC_AT_1972 = 10.0; // TAI-UTC at 1972-01-01 (s)

template <typename Duration = std::chrono::utc_clock::duration>
constexpr std::chrono::time_point<std::chrono::utc_clock, Duration> TAI_J2000_EPOCH_IN_UTC_TIME =
	std::chrono::utc_time<Duration>{ std::chrono::duration_cast<Duration>(std::chrono::duration<double>{
		static_cast<double>(TAI_J2000_EPOCH_IN_POSIX_TIME + TAI_MINUS_UTC_AT_J2000 - TAI_MINUS_UTC_AT_1972) }
	) };

int main()
{
	const auto UTC_1972_EPOCH_IN_UTC_TIME = std::chrono::utc_clock::from_sys(UTC_1972_EPOCH_IN_SYS_TIME<>);

	{
		std::cout << "UTC 1972 epoch in sys_time: " << UTC_1972_EPOCH_IN_SYS_TIME<> << "\n";

		std::cout << "UTC 1972 epoch in sys_time (POSIX seconds): "
				  << std::chrono::duration_cast<std::chrono::seconds>(
						 UTC_1972_EPOCH_IN_SYS_TIME<>.time_since_epoch()
					 )
						 .count()
				  << " seconds since POSIX epoch\n";

		std::cout << "UTC 1972 epoch in utc_time: " << UTC_1972_EPOCH_IN_UTC_TIME << "\n";
		std::cout << "UTC 1972 epoch in utc_time (POSIX seconds): "
				  << std::chrono::duration_cast<std::chrono::seconds>(
						 UTC_1972_EPOCH_IN_UTC_TIME.time_since_epoch()
					 )
						 .count()
				  << " seconds since UTC epoch\n";

		std::cout << "\n";
	}

	{
		std::cout << "TAI J2000 epoch in sys_time: " << TAI_J2000_EPOCH_IN_SYS_TIME<> << "\n";
		std::cout << "TAI J2000 epoch in sys_time (POSIX seconds): "
				  << std::chrono::duration_cast<std::chrono::seconds>(
						 TAI_J2000_EPOCH_IN_SYS_TIME<>.time_since_epoch()
					 )
						 .count()
				  << " seconds since POSIX epoch\n";
		std::cout << "TAI J2000 epoch in utc_time: " << TAI_J2000_EPOCH_IN_UTC_TIME<> << "\n";
		std::cout << "TAI J2000 epoch in utc_time (POSIX seconds): "
				  << std::chrono::duration_cast<std::chrono::seconds>(
						 TAI_J2000_EPOCH_IN_UTC_TIME<>.time_since_epoch()
					 )
						 .count()
				  << " seconds since UTC epoch\n";

		std::cout << "\n";
	}

	{
		std::cout << "Difference between UTC 1972 epoch and TAI J2000 epoch in sys_time: "
				  << std::chrono::duration_cast<
						 std::chrono::seconds>(UTC_1972_EPOCH_IN_SYS_TIME<> - TAI_J2000_EPOCH_IN_SYS_TIME<>)
				  << "\n";

		std::cout << "Difference between UTC 1972 epoch and TAI J2000 epoch in utc_time: "
				  << std::chrono::duration_cast<
						 std::chrono::seconds>(UTC_1972_EPOCH_IN_UTC_TIME - TAI_J2000_EPOCH_IN_UTC_TIME<>)
				  << "\n";
	}

	{
		std::cout << "Difference between UTC 1970 epoch and TAI J2000 epoch in sys_time: "
				  << std::chrono::duration_cast<
						 std::chrono::seconds>(UTC_1970_EPOCH_IN_SYS_TIME<> - TAI_J2000_EPOCH_IN_SYS_TIME<>)
				  << "\n";

		std::cout << "Difference between UTC 1970 epoch and TAI J2000 epoch in utc_time: "
				  << std::chrono::duration_cast<
						 std::chrono::seconds>(UTC_1970_EPOCH_IN_UTC_TIME<> - TAI_J2000_EPOCH_IN_UTC_TIME<>)
				  << "\n";
	}
	return 0;
}
