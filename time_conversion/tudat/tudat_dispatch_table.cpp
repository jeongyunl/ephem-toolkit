#include "conversion_wrapper.h"
#include "time_converter_tudat.h"
#include "../time_conversion_common.h"

#include <functional>
#include <map>
#include <stdexcept>
#include <variant>

void TimeConverterTudat::make_dispatch_table()
{
	dispatchTable = {
		{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_ISO8601 }, &TimeConverterTudat::utc_iso_to_utc_iso },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::POSIX }, &TimeConverterTudat::utc_iso_to_posix },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::UTC_J2000 }, &TimeConverterTudat::utc_iso_to_utc_j2000 },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::TAI_J2000 }, &TimeConverterTudat::utc_iso_to_tai_j2000 },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::TT_J2000 }, &TimeConverterTudat::utc_iso_to_tt_j2000 },
		{ { TimeFormat::UTC_ISO8601, TimeFormat::TDB_J2000 }, &TimeConverterTudat::utc_iso_to_tdb_j2000 },

		{ { TimeFormat::POSIX, TimeFormat::UTC_ISO8601 }, &TimeConverterTudat::posix_to_utc_iso },
		{ { TimeFormat::POSIX, TimeFormat::POSIX }, &TimeConverterTudat::posix_to_posix },
		{ { TimeFormat::POSIX, TimeFormat::UTC_J2000 }, &TimeConverterTudat::posix_to_utc_j2000 },
		{ { TimeFormat::POSIX, TimeFormat::TAI_J2000 }, &TimeConverterTudat::posix_to_tai_j2000 },
		{ { TimeFormat::POSIX, TimeFormat::TT_J2000 }, &TimeConverterTudat::posix_to_tt_j2000 },

		{ { TimeFormat::UTC_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterTudat::utc_j2000_to_utc_iso },
		{ { TimeFormat::UTC_J2000, TimeFormat::POSIX }, &TimeConverterTudat::utc_j2000_to_posix },
		{ { TimeFormat::UTC_J2000, TimeFormat::UTC_J2000 }, &TimeConverterTudat::utc_j2000_to_utc_j2000 },
		{ { TimeFormat::UTC_J2000, TimeFormat::TAI_J2000 }, &TimeConverterTudat::utc_j2000_to_tai_j2000 },
		{ { TimeFormat::UTC_J2000, TimeFormat::TT_J2000 }, &TimeConverterTudat::utc_j2000_to_tt_j2000 },

		{ { TimeFormat::TAI_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterTudat::tai_j2000_to_utc_iso },
		{ { TimeFormat::TAI_J2000, TimeFormat::POSIX }, &TimeConverterTudat::tai_j2000_to_posix },
		{ { TimeFormat::TAI_J2000, TimeFormat::UTC_J2000 }, &TimeConverterTudat::tai_j2000_to_utc_j2000 },
		{ { TimeFormat::TAI_J2000, TimeFormat::TAI_J2000 }, &TimeConverterTudat::tai_j2000_to_tai_j2000 },
		{ { TimeFormat::TAI_J2000, TimeFormat::TT_J2000 }, &TimeConverterTudat::tai_j2000_to_tt_j2000 },

		{ { TimeFormat::TT_J2000, TimeFormat::UTC_ISO8601 }, &TimeConverterTudat::tt_j2000_to_utc_iso },
		{ { TimeFormat::TT_J2000, TimeFormat::POSIX }, &TimeConverterTudat::tt_j2000_to_posix },
		{ { TimeFormat::TT_J2000, TimeFormat::UTC_J2000 }, &TimeConverterTudat::tt_j2000_to_utc_j2000 },
		{ { TimeFormat::TT_J2000, TimeFormat::TAI_J2000 }, &TimeConverterTudat::tt_j2000_to_tai_j2000 },
		{ { TimeFormat::TT_J2000, TimeFormat::TT_J2000 }, &TimeConverterTudat::tt_j2000_to_tt_j2000 },
	};
}
