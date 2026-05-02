#include "conversion_wrapper.h"
#include "base/time_converter_base.h"
#include "chrono/time_converter_chrono.h"

#include <stdexcept>

void TimeConverterBase::make_dispatch_table()
{
	dispatchTable = {
		{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_ISO8601 }, &TimeConverterBase::utc_iso_to_utc_iso },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::POSIX }, &TimeConverterBase::utc_iso_to_posix },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_J2000 }, &TimeConverterBase::utc_iso_to_utc_j2000 },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::TAI_J2000 }, &TimeConverterBase::utc_iso_to_tai_j2000 },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::TT_J2000 }, &TimeConverterBase::utc_iso_to_tt_j2000 },

		{ { TimeFormat::POSIX, TimeFormat::UTC_ISO8601 }, &TimeConverterBase::posix_to_utc_iso },
		{ { TimeFormat::POSIX, TimeFormat::POSIX }, &TimeConverterBase::posix_to_posix },
		{ { TimeFormat::POSIX, TimeFormat::UTC_J2000 }, &TimeConverterBase::posix_to_utc_j2000 },
		{ { TimeFormat::POSIX, TimeFormat::TAI_J2000 }, &TimeConverterBase::posix_to_tai_j2000 },
		{ { TimeFormat::POSIX, TimeFormat::TT_J2000 }, &TimeConverterBase::posix_to_tt_j2000 },

		{ { TimeFormat::UTC_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterBase::utc_j2000_to_utc_iso },
		{ { TimeFormat::UTC_J2000, TimeFormat::POSIX }, &TimeConverterBase::utc_j2000_to_posix },
		{ { TimeFormat::UTC_J2000, TimeFormat::UTC_J2000 }, &TimeConverterBase::utc_j2000_to_utc_j2000 },
		{ { TimeFormat::UTC_J2000, TimeFormat::TAI_J2000 }, &TimeConverterBase::utc_j2000_to_tai_j2000 },
		{ { TimeFormat::UTC_J2000, TimeFormat::TT_J2000 }, &TimeConverterBase::utc_j2000_to_tt_j2000 },

		{ { TimeFormat::TAI_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterBase::tai_j2000_to_utc_iso },
		{ { TimeFormat::TAI_J2000, TimeFormat::POSIX }, &TimeConverterBase::tai_j2000_to_posix },
		{ { TimeFormat::TAI_J2000, TimeFormat::UTC_J2000 }, &TimeConverterBase::tai_j2000_to_utc_j2000 },
		{ { TimeFormat::TAI_J2000, TimeFormat::TAI_J2000 }, &TimeConverterBase::tai_j2000_to_tai_j2000 },
		{ { TimeFormat::TAI_J2000, TimeFormat::TT_J2000 }, &TimeConverterBase::tai_j2000_to_tt_j2000 },

		{ { TimeFormat::TT_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterBase::tt_j2000_to_utc_iso },
		{ { TimeFormat::TT_J2000, TimeFormat::POSIX }, &TimeConverterBase::tt_j2000_to_posix },
		{ { TimeFormat::TT_J2000, TimeFormat::UTC_J2000 }, &TimeConverterBase::tt_j2000_to_utc_j2000 },
		{ { TimeFormat::TT_J2000, TimeFormat::TAI_J2000 }, &TimeConverterBase::tt_j2000_to_tai_j2000 },
		{ { TimeFormat::TT_J2000, TimeFormat::TT_J2000 }, &TimeConverterBase::tt_j2000_to_tt_j2000 },
	};
}
