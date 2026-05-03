#include "time_converter_chrono.h"

void TimeConverterChrono::make_dispatch_table()
{
	TimeConverterBase::make_dispatch_table();

	dispatchTable.merge(std::map<DispatchKey, ConversionWrapper>{
		{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_ISO8601 }, &TimeConverterChrono::utc_iso_to_utc_iso },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::POSIX }, &TimeConverterChrono::utc_iso_to_posix },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_J2000 }, &TimeConverterChrono::utc_iso_to_utc_j2000 },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::TAI_J2000 }, &TimeConverterChrono::utc_iso_to_tai_j2000 },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::TT_J2000 }, &TimeConverterChrono::utc_iso_to_tt_j2000 },

		{ { TimeFormat::POSIX, TimeFormat::UTC_ISO8601 }, &TimeConverterChrono::posix_to_utc_iso },
		{ { TimeFormat::POSIX, TimeFormat::POSIX }, &TimeConverterChrono::posix_to_posix },
		{ { TimeFormat::POSIX, TimeFormat::UTC_J2000 }, &TimeConverterChrono::posix_to_utc_j2000 },
		{ { TimeFormat::POSIX, TimeFormat::TAI_J2000 }, &TimeConverterChrono::posix_to_tai_j2000 },
		{ { TimeFormat::POSIX, TimeFormat::TT_J2000 }, &TimeConverterChrono::posix_to_tt_j2000 },

		{ { TimeFormat::UTC_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterChrono::utc_j2000_to_utc_iso },
		{ { TimeFormat::UTC_J2000, TimeFormat::POSIX }, &TimeConverterChrono::utc_j2000_to_posix },
		{ { TimeFormat::UTC_J2000, TimeFormat::UTC_J2000 }, &TimeConverterChrono::utc_j2000_to_utc_j2000 },
		{ { TimeFormat::UTC_J2000, TimeFormat::TAI_J2000 }, &TimeConverterChrono::utc_j2000_to_tai_j2000 },
		{ { TimeFormat::UTC_J2000, TimeFormat::TT_J2000 }, &TimeConverterChrono::utc_j2000_to_tt_j2000 },

		{ { TimeFormat::TAI_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterChrono::tai_j2000_to_utc_iso },
		{ { TimeFormat::TAI_J2000, TimeFormat::POSIX }, &TimeConverterChrono::tai_j2000_to_posix },
		{ { TimeFormat::TAI_J2000, TimeFormat::UTC_J2000 }, &TimeConverterChrono::tai_j2000_to_utc_j2000 },
		{ { TimeFormat::TAI_J2000, TimeFormat::TAI_J2000 }, &TimeConverterChrono::tai_j2000_to_tai_j2000 },
		{ { TimeFormat::TAI_J2000, TimeFormat::TT_J2000 }, &TimeConverterChrono::tai_j2000_to_tt_j2000 },

		{ { TimeFormat::TT_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterChrono::tt_j2000_to_utc_iso },
		{ { TimeFormat::TT_J2000, TimeFormat::POSIX }, &TimeConverterChrono::tt_j2000_to_posix },
		{ { TimeFormat::TT_J2000, TimeFormat::UTC_J2000 }, &TimeConverterChrono::tt_j2000_to_utc_j2000 },
		{ { TimeFormat::TT_J2000, TimeFormat::TAI_J2000 }, &TimeConverterChrono::tt_j2000_to_tai_j2000 },
		{ { TimeFormat::TT_J2000, TimeFormat::TT_J2000 }, &TimeConverterChrono::tt_j2000_to_tt_j2000 },

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

		{ { TimeFormat::CHRONO_SYS_TIME, TimeFormat::POSIX }, &TimeConverterChrono::sys_time_to_posix<> },
		{ { TimeFormat::CHRONO_SYS_TIME, TimeFormat::UTC_ISO8601 },
		  &TimeConverterChrono::sys_time_to_utc_iso<> },

		{ { TimeFormat::CHRONO_UTC_TIME, TimeFormat::UTC_ISO8601 },
		  &TimeConverterChrono::utc_time_to_utc_iso<> },

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
	});
}
