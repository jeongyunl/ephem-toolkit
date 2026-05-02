#include "chrono_dispatch_entries.h"

#include "time_converter_chrono.h"

void register_chrono_dispatch_entries(std::map<DispatchKey, Handler>& dispatch_table)
{
	std::map<DispatchKey, Handler> chrono_dispatch_table{
		{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_SYS_TIME_ISO },
		  &TimeConverterChrono::utc_iso_to_sys_time<> },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_SYS_TIME },
		  &TimeConverterChrono::utc_iso_to_sys_time<> },
		{ { TimeFormat::POSIX, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverterChrono::posix_to_sys_time<> },
		{ { TimeFormat::POSIX, TimeFormat::CHRONO_SYS_TIME }, &TimeConverterChrono::posix_to_sys_time<> },
		{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_SYS_TIME_ISO },
		  &TimeConverterChrono::utc_j2000_to_sys_time<> },
		{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_SYS_TIME },
		  &TimeConverterChrono::utc_j2000_to_sys_time<> },
		{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_SYS_TIME_ISO },
		  &TimeConverterChrono::tai_j2000_to_sys_time<> },
		{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_SYS_TIME },
		  &TimeConverterChrono::tai_j2000_to_sys_time<> },
		{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_SYS_TIME_ISO },
		  &TimeConverterChrono::tt_j2000_to_sys_time<> },
		{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_SYS_TIME },
		  &TimeConverterChrono::tt_j2000_to_sys_time<> },

#ifdef HAS_CHRONO_UTC_CLOCK
		{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_UTC_TIME_ISO },
		  &TimeConverterChrono::utc_iso_to_utc_time<> },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_UTC_TIME },
		  &TimeConverterChrono::utc_iso_to_utc_time<> },
		{ { TimeFormat::POSIX, TimeFormat::CHRONO_UTC_TIME_ISO }, &TimeConverterChrono::posix_to_utc_time<> },
		{ { TimeFormat::POSIX, TimeFormat::CHRONO_UTC_TIME }, &TimeConverterChrono::posix_to_utc_time<> },
		{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_UTC_TIME_ISO },
		  &TimeConverterChrono::utc_j2000_to_utc_time<> },
		{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_UTC_TIME },
		  &TimeConverterChrono::utc_j2000_to_utc_time<> },
		{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_UTC_TIME_ISO },
		  &TimeConverterChrono::tai_j2000_to_utc_time<> },
		{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_UTC_TIME },
		  &TimeConverterChrono::tai_j2000_to_utc_time<> },
		{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_UTC_TIME_ISO },
		  &TimeConverterChrono::tt_j2000_to_utc_time<> },
		{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_UTC_TIME },
		  &TimeConverterChrono::tt_j2000_to_utc_time<> },
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
		{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_TAI_TIME_ISO },
		  &TimeConverterChrono::utc_iso_to_tai_time<> },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_TAI_TIME },
		  &TimeConverterChrono::utc_iso_to_tai_time<> },
		{ { TimeFormat::POSIX, TimeFormat::CHRONO_TAI_TIME_ISO }, &TimeConverterChrono::posix_to_tai_time<> },
		{ { TimeFormat::POSIX, TimeFormat::CHRONO_TAI_TIME }, &TimeConverterChrono::posix_to_tai_time<> },
		{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_TAI_TIME_ISO },
		  &TimeConverterChrono::utc_j2000_to_tai_time<> },
		{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_TAI_TIME },
		  &TimeConverterChrono::utc_j2000_to_tai_time<> },
		{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_TAI_TIME_ISO },
		  &TimeConverterChrono::tai_j2000_to_tai_time<> },
		{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_TAI_TIME },
		  &TimeConverterChrono::tai_j2000_to_tai_time<> },
		{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_TAI_TIME_ISO },
		  &TimeConverterChrono::tt_j2000_to_tai_time<> },
		{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_TAI_TIME },
		  &TimeConverterChrono::tt_j2000_to_tai_time<> },
#endif
	};

	dispatch_table.insert(chrono_dispatch_table.begin(), chrono_dispatch_table.end());
}
