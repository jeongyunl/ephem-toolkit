#include "convert_time.h"

#include <format>
#include <iostream>
#include <stdexcept>

int main()
{
#ifdef HAS_CHRONO_UTC_CLOCK
	std::chrono::utc_time<std::chrono::milliseconds> utc_tp;
	std::chrono::tai_time<std::chrono::milliseconds> tai_tp;
	std::chrono::gps_time<std::chrono::milliseconds> gps_tp;
#endif

	std::chrono::system_clock::time_point sys_time_epoch;
	{
		std::cout << std::format("sys_time_epoch {}\t(sys_time_epoch)\n", sys_time_epoch);
		std::cout << std::format(
			"sys_time_epoch {}\t(sys_time_to_time_t_std(sys_time_epoch))\n",
			sys_time_to_time_t_std(sys_time_epoch)
		);
		std::cout << std::format(
			"sys_time_epoch {}\t(sys_time_to_time_t_std(sys_time_epoch))\n",
			sys_time_to_time_t_std(sys_time_epoch)
		);
		std::cout << std::format(
			"sys_time_epoch {}\t(sys_time_to_posix(sys_time_epoch))\n",
			sys_time_to_posix(sys_time_epoch)
		);

		std::cout << '\n';
	}

	const auto posix_epoch_str = "1970-01-01 00:00:00.000";
	{
		std::cout << std::format("posix_epoch_str {}\n", posix_epoch_str);
		std::cout << std::format("posix_epoch {}\n", sys_time_to_posix(iso_to_sys_time(posix_epoch_str)));
		std::cout << std::format("utc_tudat_epoch {}\n", iso_to_utc_tudat(posix_epoch_str));
		std::cout << '\n';
	}

	auto posix_epoch_sys_tp = iso_to_sys_time(posix_epoch_str);
	{
		std::cout << std::format("posix_epoch_sys_tp {}\t(posix_epoch_sys_tp)\n", posix_epoch_sys_tp);
		std::cout << std::format(
			"posix_epoch_sys_tp {}\t(sys_time_to_time_t_std(posix_epoch_sys_tp))\n",
			sys_time_to_time_t_std(posix_epoch_sys_tp)
		);
		std::cout << std::format(
			"posix_epoch_sys_tp {}\t(sys_time_to_time_t_dc(posix_epoch_sys_tp))\n",
			sys_time_to_time_t_dc(posix_epoch_sys_tp)
		);
		std::cout << std::format(
			"posix_epoch_sys_tp {}\t(sys_time_to_posix(posix_epoch_sys_tp))\n",
			sys_time_to_posix(posix_epoch_sys_tp)
		);

		std::cout << '\n';
	}

	const auto utc_j2000_str = "2000-01-01 12:00:00.000";
	{
		std::cout << std::format("utc_j2000_str {}\n", utc_j2000_str);
		std::cout << std::format("utc_j2000 {}\n", sys_time_to_posix(iso_to_sys_time(utc_j2000_str)));
		std::cout << std::format("utc_tudat_j2000 {}\n", iso_to_utc_tudat(utc_j2000_str));
		std::cout << '\n';
	}

	auto utc_j2000_sys_tp = iso_to_sys_time(utc_j2000_str);
	{
		std::cout << std::format("utc_j2000_sys_tp {}\t(utc_j2000_sys_tp)\n", utc_j2000_sys_tp);
		std::cout << std::format(
			"utc_j2000_sys_tp {}\t(sys_time_to_time_t_std(utc_j2000_sys_tp))\n",
			sys_time_to_time_t_std(utc_j2000_sys_tp)
		);
		std::cout << std::format(
			"utc_j2000_sys_tp {}\t(sys_time_to_time_t_dc(utc_j2000_sys_tp))\n",
			sys_time_to_time_t_dc(utc_j2000_sys_tp)
		);
		std::cout << std::format(
			"utc_j2000_sys_tp {}\t(sys_time_to_posix(utc_j2000_sys_tp))\n",
			sys_time_to_posix(utc_j2000_sys_tp)
		);

		std::cout << '\n';
	}

	const auto utc_j2000_0_5_str = "2000-01-01 12:00:00.500";
	{
		std::cout << std::format("utc_j2000_0_5_str {}\n", utc_j2000_0_5_str);
		std::cout << std::format("utc_j2000_0_5 {}\n", sys_time_to_posix(iso_to_sys_time(utc_j2000_0_5_str)));
		std::cout << std::format("utc_tudat_j2000_0_5 {}\n", iso_to_utc_tudat(utc_j2000_0_5_str));
		std::cout << '\n';
	}

	auto utc_j2000_0_5_sys_tp = iso_to_sys_time(utc_j2000_0_5_str);
	{
		std::cout << std::format("utc_j2000_0_5_sys_tp {}\t(utc_j2000_0_5_sys_tp)\n", utc_j2000_0_5_sys_tp);
		std::cout << std::format(
			"utc_j2000_0_5_sys_tp {}\t(sys_time_to_time_t_std(utc_j2000_0_5_sys_tp))\n",
			sys_time_to_time_t_std(utc_j2000_0_5_sys_tp)
		);
		std::cout << std::format(
			"utc_j2000_0_5_sys_tp {}\t(sys_time_to_time_t_dc(utc_j2000_0_5_sys_tp))\n",
			sys_time_to_time_t_dc(utc_j2000_0_5_sys_tp)
		);
		std::cout << std::format(
			"utc_j2000_0_5_sys_tp {}\t(sys_time_to_posix(utc_j2000_0_5_sys_tp))\n",
			sys_time_to_posix(utc_j2000_0_5_sys_tp)
		);
		std::cout << std::format(
			"utc_j2000_0_5_sys_tp {}\t(sys_time_to_posix<double>(utc_j2000_0_5_sys_tp))\n",
			sys_time_to_posix<double>(utc_j2000_0_5_sys_tp)
		);
		std::cout << std::format(
			"utc_j2000_0_5_sys_tp {}\t(sys_time_to_posix<int>(utc_j2000_0_5_sys_tp))\n",
			sys_time_to_posix<int>(utc_j2000_0_5_sys_tp)
		);

		std::cout << '\n';
	}

#ifdef HAS_CHRONO_UTC_CLOCK
	std::cout << std::format("utc_tp {}\n", utc_tp);
	std::cout << std::format("tai_tp {}\n", tai_tp);
	std::cout << std::format("gps_tp {}\n", gps_tp);
#endif

	return 0;
}
