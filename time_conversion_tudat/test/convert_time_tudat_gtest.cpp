#include "convert_time_tudat.h"
#include "test/convert_time_gtest_common.h"

#include <gtest/gtest.h>
#include <chrono>
#include <cmath>
#include <unordered_map>

namespace
{

using convert_time_test::EpochRecord;

class ConvertTimeTudatTest : public ::testing::Test
{
protected:
	static void SetUpTestSuite() { }
};

} // namespace

using namespace convert_time_tudat;

// utc_posix_to_*() functions are tested here
TEST_F(ConvertTimeTudatTest, PosixToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		// POSIX timestamps during leap seconds are ambiguous and cannot be reliably tested against reference
		// data, so skip those rows.
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		EXPECT_NEAR(posix_to_utc_tudat(record.posix), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(posix_to_tai_tudat(record.posix), record.tai, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(posix_to_tt_tudat(record.posix), record.tt, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(posix_to_tdb_tudat(record.posix), record.tdb, convert_time_test::kTolTdb) << record.iso;
	}
}

// utc_tudat_to_*() functions are tested here
TEST_F(ConvertTimeTudatTest, UtcToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		// TUDAT UTC timestamps during leap seconds are ambiguous and cannot be reliably tested against
		// reference data, so skip those rows.
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		EXPECT_NEAR(utc_tudat_to_posix(record.utc), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_tudat_to_tai_tudat(record.utc), record.tai, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_tudat_to_tt_tudat(record.utc), record.tt, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_tudat_to_tdb_tudat(record.utc), record.tdb, convert_time_test::kTolTdb) << record.iso;
	}
}

TEST_F(ConvertTimeTudatTest, TaiToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(tai_tudat_to_posix(record.tai), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tai_tudat_to_utc_tudat(record.tai), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tai_tudat_to_tt_tudat(record.tai), record.tt, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tai_tudat_to_tdb_tudat(record.tai), record.tdb, convert_time_test::kTolTdb) << record.iso;
	}
}

TEST_F(ConvertTimeTudatTest, TtToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(tt_tudat_to_posix(record.tt), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tt_tudat_to_utc_tudat(record.tt), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tt_tudat_to_tai_tudat(record.tt), record.tai, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tt_tudat_to_tdb_tudat(record.tt), record.tdb, convert_time_test::kTolTdb) << record.iso;
	}
}

TEST_F(ConvertTimeTudatTest, TdbToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(tdb_tudat_to_posix(record.tdb), record.posix, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(tdb_tudat_to_utc_tudat(record.tdb), record.utc, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(tdb_tudat_to_tai_tudat(record.tdb), record.tai, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(tdb_tudat_to_tt_tudat(record.tdb), record.tt, convert_time_test::kTolTdb) << record.iso;
	}
}

TEST_F(ConvertTimeTudatTest, NumericRoundTripUsingUtcIsStableForNonLeapSecondRows)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		const double utc_from_posix = posix_to_utc_tudat(record.posix);
		const double posix_from_utc = utc_tudat_to_posix(utc_from_posix);
		EXPECT_NEAR(posix_from_utc, record.posix, convert_time_test::kTolExactLike) << record.iso;

		const double tai_from_utc = utc_tudat_to_tai_tudat(record.utc);
		const double utc_from_tai = tai_tudat_to_utc_tudat(tai_from_utc);
		EXPECT_NEAR(utc_from_tai, record.utc, convert_time_test::kTolExactLike) << record.iso;
	}
}
