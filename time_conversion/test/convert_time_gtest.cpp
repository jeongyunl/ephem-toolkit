#include "time_converter.h"
#include "chrono/time_converter_chrono.h"
#include "test/convert_time_gtest_common.h"

#include <gtest/gtest.h>
#include <chrono>
#include <cmath>
#include <unordered_map>

namespace
{

using convert_time_test::EpochRecord;

class ConvertTimeDataDrivenTest : public ::testing::Test
{
protected:
	static void SetUpTestSuite() {}
};

} // namespace

// utc_iso_to_*() functions are tested here
TEST_F(ConvertTimeDataDrivenTest, IsoToAllNumericScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(
			TimeConverter::instance().utc_iso_to_posix(record.iso),
			record.posix,
			convert_time_test::kTolExactLike
		) << record.iso;
		EXPECT_NEAR(
			TimeConverter::instance().utc_iso_to_utc_j2000(record.iso),
			record.utc,
			convert_time_test::kTolExactLike
		) << record.iso;

		if(record.posix >= epochs::UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			EXPECT_NEAR(
				TimeConverter::instance().utc_iso_to_tai_j2000(record.iso),
				record.tai,
				convert_time_test::kTolTimeScale
			) << record.iso;
			EXPECT_NEAR(
				TimeConverter::instance().utc_iso_to_tt_j2000(record.iso),
				record.tt,
				convert_time_test::kTolTimeScale
			) << record.iso;
			EXPECT_NEAR(
				TimeConverter::instance().utc_iso_to_tdb_j2000(record.iso),
				record.tdb,
				convert_time_test::kTolTdb
			) << record.iso;
		}
	}
}

// posix_to_*() functions are tested here
TEST_F(ConvertTimeDataDrivenTest, PosixToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		// POSIX timestamps during leap seconds are ambiguous and cannot be reliably tested against reference
		// data, so skip those rows.
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		const auto iso_from_posix = TimeConverter::instance().posix_to_utc_iso(record.posix);
		EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(iso_from_posix, record.iso, 3))
			<< iso_from_posix << " != " << record.iso;

		EXPECT_NEAR(
			TimeConverter::instance().posix_to_utc_j2000(record.posix),
			record.utc,
			convert_time_test::kTolExactLike
		) << record.iso;

		if(record.posix >= epochs::UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			EXPECT_NEAR(
				TimeConverter::instance().posix_to_tai_j2000(record.posix),
				record.tai,
				convert_time_test::kTolExactLike
			) << record.iso;
			EXPECT_NEAR(
				TimeConverter::instance().posix_to_tt_j2000(record.posix),
				record.tt,
				convert_time_test::kTolExactLike
			) << record.iso;
			EXPECT_NEAR(
				TimeConverter::instance().posix_to_tdb_j2000(record.posix),
				record.tdb,
				convert_time_test::kTolTdb
			) << record.iso;
		}
	}
}

// utc_j2000_to_*() functions are tested here
TEST_F(ConvertTimeDataDrivenTest, UtcToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		// TUDAT UTC timestamps during leap seconds are ambiguous and cannot be reliably tested against
		// reference data, so skip those rows.
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		const auto iso_from_utc_j2000 = TimeConverter::instance().utc_j2000_to_utc_iso(record.utc);
		EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(iso_from_utc_j2000, record.iso, 3))
			<< iso_from_utc_j2000 << " != " << record.iso;

		EXPECT_NEAR(
			TimeConverter::instance().utc_j2000_to_posix(record.utc),
			record.posix,
			convert_time_test::kTolExactLike
		) << record.iso;

		if(record.posix >= epochs::UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			EXPECT_NEAR(
				TimeConverter::instance().utc_j2000_to_tai_j2000(record.utc),
				record.tai,
				convert_time_test::kTolExactLike
			) << record.iso;
			EXPECT_NEAR(
				TimeConverter::instance().utc_j2000_to_tt_j2000(record.utc),
				record.tt,
				convert_time_test::kTolExactLike
			) << record.iso;
			EXPECT_NEAR(
				TimeConverter::instance().utc_j2000_to_tdb_j2000(record.utc),
				record.tdb,
				convert_time_test::kTolTdb
			) << record.iso;
		}
	}
}

TEST_F(ConvertTimeDataDrivenTest, TaiToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(record.posix >= epochs::UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			EXPECT_NEAR(
				TimeConverter::instance().tai_j2000_to_posix(record.tai),
				record.posix,
				convert_time_test::kTolExactLike
			) << record.iso;
			EXPECT_NEAR(
				TimeConverter::instance().tai_j2000_to_utc_j2000(record.tai),
				record.utc,
				convert_time_test::kTolExactLike
			) << record.iso;
		}
		EXPECT_NEAR(
			TimeConverter::instance().tai_j2000_to_tt_j2000(record.tai),
			record.tt,
			convert_time_test::kTolExactLike
		) << record.iso;
		EXPECT_NEAR(
			TimeConverter::instance().tai_j2000_to_tdb_j2000(record.tai),
			record.tdb,
			convert_time_test::kTolTdb
		) << record.iso;
	}
}

TEST_F(ConvertTimeDataDrivenTest, TtToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(record.posix >= epochs::UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			EXPECT_NEAR(
				TimeConverter::instance().tt_j2000_to_posix(record.tt),
				record.posix,
				convert_time_test::kTolExactLike
			) << record.iso;
			EXPECT_NEAR(
				TimeConverter::instance().tt_j2000_to_utc_j2000(record.tt),
				record.utc,
				convert_time_test::kTolExactLike
			) << record.iso;
		}
		EXPECT_NEAR(
			TimeConverter::instance().tt_j2000_to_tai_j2000(record.tt),
			record.tai,
			convert_time_test::kTolExactLike
		) << record.iso;
		EXPECT_NEAR(
			TimeConverter::instance().tt_j2000_to_tdb_j2000(record.tt),
			record.tdb,
			convert_time_test::kTolTdb
		) << record.iso;

		// Before 1972, UTC and TAI (TT as well by proxy) were not synchronized, so the ISO string derived
		// from TT may not match the reference UTC ISO string.
		if(record.posix >= epochs::UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			const auto iso_from_tt_j2000 = TimeConverter::instance().tt_j2000_to_utc_iso(record.tt);
			EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(iso_from_tt_j2000, record.iso, 3))
				<< iso_from_tt_j2000 << " != " << record.iso;
		}
	}
}

TEST_F(ConvertTimeDataDrivenTest, TdbToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(record.posix >= epochs::UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			EXPECT_NEAR(
				TimeConverter::instance().tdb_j2000_to_posix(record.tdb),
				record.posix,
				convert_time_test::kTolTdb
			) << record.iso;
			EXPECT_NEAR(
				TimeConverter::instance().tdb_j2000_to_utc_j2000(record.tdb),
				record.utc,
				convert_time_test::kTolTdb
			) << record.iso;
		}
		EXPECT_NEAR(
			TimeConverter::instance().tdb_j2000_to_tai_j2000(record.tdb),
			record.tai,
			convert_time_test::kTolTdb
		) << record.iso;
		EXPECT_NEAR(
			TimeConverter::instance().tdb_j2000_to_tt_j2000(record.tdb),
			record.tt,
			convert_time_test::kTolTdb
		) << record.iso;

		// Before 1972, UTC and TAI (TDB as well by proxy) were not synchronized, so the ISO string derived
		// from TDB may not match the reference UTC ISO string.
		if(record.posix >= epochs::UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			const auto iso_from_tdb_j2000 = TimeConverter::instance().tdb_j2000_to_utc_iso(record.tdb);
			EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(iso_from_tdb_j2000, record.iso, 3))
				<< iso_from_tdb_j2000 << " != " << record.iso;

		}
	}
}

TEST_F(ConvertTimeDataDrivenTest, UtcIsoIdentityRoundTripForRecords)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(
			TimeConverter::instance().utc_iso_to_utc_iso(record.iso),
			record.iso,
			3
		)) << record.iso;
	}
}

TEST(ConvertTimeIso, Iso8601EqualTreatsTSeparatorAsOptional)
{
	EXPECT_TRUE(
		TimeConverter::instance().iso_8601_equal("1970-01-01T00:00:00.000000", "1970-01-01 00:00:00.000", 3)
	);
	EXPECT_TRUE(
		TimeConverter::instance().iso_8601_equal("1970-01-01T00:00:00.000000", "1970-01-01 00:00:00.000", 6)
	);
}

TEST(ConvertTimeIso, Iso8601EqualUsesRequestedFractionalPrecision)
{
	EXPECT_TRUE(TimeConverter::instance()
					.iso_8601_equal("1970-01-01T00:00:00.123456", "1970-01-01 00:00:00.123000", 3));
	EXPECT_FALSE(TimeConverter::instance()
					 .iso_8601_equal("1970-01-01T00:00:00.123456", "1970-01-01 00:00:00.123000", 4));
	EXPECT_TRUE(
		TimeConverter::instance().iso_8601_equal("1970-01-01T00:00:00.9", "1970-01-01 00:00:00.900000", 6)
	);
}

TEST(ConvertTimeIso, Iso8601EqualReturnsFalseForInvalidInputOrPrecision)
{
	EXPECT_FALSE(TimeConverter::instance().iso_8601_equal("not-a-time", "1970-01-01 00:00:00.000", 3));
	EXPECT_FALSE(
		TimeConverter::instance().iso_8601_equal("1970-01-01T00:00:00.000", "1970-01-01 00:00:00.000", 10)
	);
}

TEST_F(ConvertTimeDataDrivenTest, NumericRoundTripUsingUtcIsStableForNonLeapSecondRows)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		const double utc_from_posix = TimeConverter::instance().posix_to_utc_j2000(record.posix);
		const double posix_from_utc = TimeConverter::instance().utc_j2000_to_posix(utc_from_posix);
		EXPECT_NEAR(posix_from_utc, record.posix, convert_time_test::kTolExactLike) << record.iso;

		if(record.posix >= epochs::UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			const double tai_from_utc = TimeConverter::instance().utc_j2000_to_tai_j2000(record.utc);
			const double utc_from_tai = TimeConverter::instance().tai_j2000_to_utc_j2000(tai_from_utc);
			EXPECT_NEAR(utc_from_tai, record.utc, convert_time_test::kTolExactLike) << record.iso;
		}
	}
}
