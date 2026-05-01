#include "base_dispatch_entries.h"

#include "time_converter.h"

void register_base_dispatch_entries(std::map<DispatchKey, Handler>& dispatch_table)
{
	std::map<DispatchKey, Handler> base_dispatch_table{
		{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_ISO8601 }, &TimeConverter::utc_iso_to_utc_iso },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::POSIX }, &TimeConverter::utc_iso_to_posix },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_J2000 }, &TimeConverter::utc_iso_to_utc_j2000 },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::TAI_J2000 }, &TimeConverter::utc_iso_to_tai_j2000 },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::TT_J2000 }, &TimeConverter::utc_iso_to_tt_j2000 },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverter::utc_iso_to_sys_time<> },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::CHRONO_SYS_TIME }, &TimeConverter::utc_iso_to_sys_time<> },

		{ { TimeFormat::POSIX, TimeFormat::UTC_ISO8601 }, &TimeConverter::posix_to_utc_iso },
		{ { TimeFormat::POSIX, TimeFormat::POSIX }, &TimeConverter::posix_to_posix },
		{ { TimeFormat::POSIX, TimeFormat::UTC_J2000 }, &TimeConverter::posix_to_utc_j2000 },
		{ { TimeFormat::POSIX, TimeFormat::TAI_J2000 }, &TimeConverter::posix_to_tai_j2000 },
		{ { TimeFormat::POSIX, TimeFormat::TT_J2000 }, &TimeConverter::posix_to_tt_j2000 },
		{ { TimeFormat::POSIX, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverter::posix_to_sys_time<> },
		{ { TimeFormat::POSIX, TimeFormat::CHRONO_SYS_TIME }, &TimeConverter::posix_to_sys_time<> },

		{ { TimeFormat::UTC_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverter::utc_j2000_to_utc_iso },
		{ { TimeFormat::UTC_J2000, TimeFormat::POSIX }, &TimeConverter::utc_j2000_to_posix },
		{ { TimeFormat::UTC_J2000, TimeFormat::UTC_J2000 }, &TimeConverter::utc_j2000_to_utc_j2000 },
		{ { TimeFormat::UTC_J2000, TimeFormat::TAI_J2000 }, &TimeConverter::utc_j2000_to_tai_j2000 },
		{ { TimeFormat::UTC_J2000, TimeFormat::TT_J2000 }, &TimeConverter::utc_j2000_to_tt_j2000 },
		{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverter::utc_j2000_to_sys_time<> },
		{ { TimeFormat::UTC_J2000, TimeFormat::CHRONO_SYS_TIME }, &TimeConverter::utc_j2000_to_sys_time<> },

		{ { TimeFormat::TAI_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverter::tai_j2000_to_utc_iso },
		{ { TimeFormat::TAI_J2000, TimeFormat::POSIX }, &TimeConverter::tai_j2000_to_posix },
		{ { TimeFormat::TAI_J2000, TimeFormat::UTC_J2000 }, &TimeConverter::tai_j2000_to_utc_j2000 },
		{ { TimeFormat::TAI_J2000, TimeFormat::TAI_J2000 }, &TimeConverter::tai_j2000_to_tai_j2000 },
		{ { TimeFormat::TAI_J2000, TimeFormat::TT_J2000 }, &TimeConverter::tai_j2000_to_tt_j2000 },
		{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverter::tai_j2000_to_sys_time<> },
		{ { TimeFormat::TAI_J2000, TimeFormat::CHRONO_SYS_TIME }, &TimeConverter::tai_j2000_to_sys_time<> },

		{ { TimeFormat::TT_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverter::tt_j2000_to_utc_iso },
		{ { TimeFormat::TT_J2000, TimeFormat::POSIX }, &TimeConverter::tt_j2000_to_posix },
		{ { TimeFormat::TT_J2000, TimeFormat::UTC_J2000 }, &TimeConverter::tt_j2000_to_utc_j2000 },
		{ { TimeFormat::TT_J2000, TimeFormat::TAI_J2000 }, &TimeConverter::tt_j2000_to_tai_j2000 },
		{ { TimeFormat::TT_J2000, TimeFormat::TT_J2000 }, &TimeConverter::tt_j2000_to_tt_j2000 },
		{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_SYS_TIME_ISO }, &TimeConverter::tt_j2000_to_sys_time<> },
		{ { TimeFormat::TT_J2000, TimeFormat::CHRONO_SYS_TIME }, &TimeConverter::tt_j2000_to_sys_time<> },
	};

	dispatch_table.insert(base_dispatch_table.begin(), base_dispatch_table.end());
}
