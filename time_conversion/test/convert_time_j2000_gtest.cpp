#include "convert_time_j2000.h"
#include "test/convert_time_common_gtest.h"

#include <gtest/gtest.h>
#include <cmath>

TEST(ConvertTimeJ2000, UtcJ2000EpochIsZero)
{
	EXPECT_DOUBLE_EQ(utc_iso_to_utc_j2000("2000-01-01T12:00:00Z"), 0.0);
}

TEST(ConvertTimeJ2000, TaiJ2000EpochIsZero)
{
	EXPECT_DOUBLE_EQ(utc_iso_to_tai_j2000("2000-01-01T11:59:28Z"), 0.0);
}

TEST(ConvertTimeJ2000, TimezoneOffsetIsApplied)
{
	// 12:00:00+01:00 == 11:00:00Z, so should be -3600 seconds from UTC J2000 epoch.
	EXPECT_DOUBLE_EQ(utc_iso_to_utc_j2000("2000-01-01T12:00:00+01:00"), -3600.0);
}

TEST(ConvertTimeJ2000, LeapSecondIsHandledAndDoesNotCountTransitionYet)
{
	// Library behavior: 23:59:60 maps to the POSIX second of the following 00:00:00,
	// but the leap transition at that boundary is not counted yet.
	// Therefore, the leap second should be exactly 1 second before the next midnight.
	const double t_leap = utc_iso_to_utc_j2000("2016-12-31T23:59:60Z");
	const double t_next = utc_iso_to_utc_j2000("2017-01-01T00:00:00Z");
	EXPECT_DOUBLE_EQ(t_next - t_leap, 1.0);
}

TEST(ConvertTimeJ2000, Iso8601EqualTreatsTSeparatorAsOptional)
{
	EXPECT_TRUE(iso_8601_equal("2000-01-01T12:00:00Z", "2000-01-01 12:00:00Z", 3));
}

TEST(ConvertTimeJ2000, Iso8601EqualRejectsInvalidPrecision)
{
	EXPECT_FALSE(iso_8601_equal("2000-01-01T12:00:00Z", "2000-01-01T12:00:00Z", 10));
}

TEST(ConvertTimeJ2000, Iso8601EqualRespectsFractionalPrecision)
{
	// Difference is 456 microseconds.
	const char* a = "1970-01-01T00:00:00.123456Z";
	const char* b = "1970-01-01T00:00:00.123000Z";

	// At millisecond precision they compare equal.
	EXPECT_TRUE(iso_8601_equal(a, b, 3));
	// At microsecond precision they should not.
	EXPECT_FALSE(iso_8601_equal(a, b, 6));
}

TEST(ConvertTimeJ2000, UtcAndTaiJ2000AreFinite)
{
	const double utc = utc_iso_to_utc_j2000("2020-01-01T00:00:00Z");
	const double tai = utc_iso_to_tai_j2000("2020-01-01T00:00:00Z");
	EXPECT_TRUE(std::isfinite(utc));
	EXPECT_TRUE(std::isfinite(tai));
}

TEST(ConvertTimeJ2000, IsoToJ2000MatchesReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(utc_iso_to_utc_j2000(record.iso), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_iso_to_tai_j2000(record.iso), record.tai, convert_time_test::kTolExactLike)
			<< record.iso << " tai=" << record.tai;
	}
}
