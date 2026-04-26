#include "convert_time_j2000.h"
#include "test/convert_time_gtest_common.h"

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
	const double t_leap = utc_iso_to_tai_j2000("2016-12-31T23:59:60Z");
	const double t_next = utc_iso_to_tai_j2000("2017-01-01T00:00:00Z");
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
		const ParsedUtcIso parsed_utc_iso =
			utc_iso_to_parsed_utc_iso(record.iso); // Just test that parsing doesn't throw for valid input

		EXPECT_NEAR(utc_iso_to_utc_j2000(record.iso), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;

		if(parsed_utc_iso.second != 60)
		{
			const auto utc_iso_from_j2000 = utc_j2000_to_utc_iso(record.utc);
			EXPECT_TRUE(iso_8601_equal(record.iso, utc_iso_from_j2000, 3))
				<< record.iso << " -> utc_iso_from_j2000=" << utc_iso_from_j2000;
		}

		{
			const auto utc_j2000_from_parsed = parsed_utc_iso_to_utc_j2000(
				parsed_utc_iso
			); // Test that conversion from parsed struct doesn't throw

			const ParsedUtcIso parsed_utc_iso_back = utc_j2000_to_parsed_utc_iso(
				utc_j2000_from_parsed
			); // Test that conversion back to parsed struct doesn't throw

			const auto utc_j2000_from_back = parsed_utc_iso_to_utc_j2000(
				parsed_utc_iso_back
			); // Test that conversion from parsed struct back to J2000 doesn't throw

			EXPECT_NEAR(utc_j2000_from_back, utc_j2000_from_parsed, 1.0e-6)
				<< record.iso << " round-trip utc_j2000_time=" << utc_j2000_from_parsed;
		}

		EXPECT_NEAR(utc_iso_to_tai_j2000(record.iso), record.tai, convert_time_test::kTolExactLike)
			<< record.iso << " tai=" << record.tai;

		{
			const auto tai_j2000_from_parsed = parsed_utc_iso_to_tai_j2000(
				parsed_utc_iso
			); // Test that conversion from parsed struct doesn't throw

			const ParsedUtcIso parsed_utc_iso_back = tai_j2000_to_parsed_utc_iso(
				tai_j2000_from_parsed
			); // Test that conversion back to parsed struct doesn't throw

			const auto tai_j2000_from_back = parsed_utc_iso_to_tai_j2000(
				parsed_utc_iso_back
			); // Test that conversion from parsed struct back to J2000 doesn't throw

			EXPECT_NEAR(tai_j2000_from_back, tai_j2000_from_parsed, 1.0e-6)
				<< record.iso << " round-trip tai_j2000_time=" << tai_j2000_from_parsed;
		}
	}
}

TEST(ConvertTimeJ2000, UtcJ2000ToParsedRoundTrip)
{
	// Test round-trip conversion: utc_iso -> utc_j2000_time -> parsed_utc_iso
	const std::string iso_string = "2000-01-01T12:00:00Z";
	const double utc_j2000_time = utc_iso_to_utc_j2000(iso_string);
	const ParsedUtcIso parsed = utc_j2000_to_parsed_utc_iso(utc_j2000_time);

	EXPECT_EQ(parsed.year, 2000);
	EXPECT_EQ(parsed.month, 1);
	EXPECT_EQ(parsed.day, 1);
	EXPECT_EQ(parsed.hour, 12);
	EXPECT_EQ(parsed.minute, 0);
	EXPECT_EQ(parsed.second, 0);
	EXPECT_EQ(parsed.nanos, 0);
	EXPECT_EQ(parsed.tz_offset_seconds, 0);
}

TEST(ConvertTimeJ2000, UtcJ2000ToParsedRoundTripWithFractional)
{
	// Test with fractional seconds
	const std::string iso_string = "2020-06-15T14:30:45.123456789Z";
	const double utc_j2000_time = utc_iso_to_utc_j2000(iso_string);
	const ParsedUtcIso parsed = utc_j2000_to_parsed_utc_iso(utc_j2000_time);

	EXPECT_EQ(parsed.year, 2020);
	EXPECT_EQ(parsed.month, 6);
	EXPECT_EQ(parsed.day, 15);
	EXPECT_EQ(parsed.hour, 14);
	EXPECT_EQ(parsed.minute, 30);
	EXPECT_EQ(parsed.second, 45);
	// Note: double precision may introduce small rounding errors in nanoseconds
	EXPECT_NEAR(parsed.nanos, 123456789, 100);
	EXPECT_EQ(parsed.tz_offset_seconds, 0);
}

TEST(ConvertTimeJ2000, UtcJ2000ToParsedHandlesNegativeJ2000)
{
	// Test with a time before J2000 epoch
	const std::string iso_string = "1999-12-31T12:00:00Z";
	const double utc_j2000_time = utc_iso_to_utc_j2000(iso_string);
	const ParsedUtcIso parsed = utc_j2000_to_parsed_utc_iso(utc_j2000_time);

	EXPECT_EQ(parsed.year, 1999);
	EXPECT_EQ(parsed.month, 12);
	EXPECT_EQ(parsed.day, 31);
	EXPECT_EQ(parsed.hour, 12);
	EXPECT_EQ(parsed.minute, 0);
	EXPECT_EQ(parsed.second, 0);
}

TEST(ConvertTimeJ2000, TaiJ2000ToParsedRoundTrip)
{
	const std::string iso_string = "2000-01-01T11:59:28Z";
	const double tai_j2000_time = utc_iso_to_tai_j2000(iso_string);
	const ParsedUtcIso parsed = tai_j2000_to_parsed_utc_iso(tai_j2000_time);

	EXPECT_EQ(parsed.year, 2000);
	EXPECT_EQ(parsed.month, 1);
	EXPECT_EQ(parsed.day, 1);
	EXPECT_EQ(parsed.hour, 11);
	EXPECT_EQ(parsed.minute, 59);
	EXPECT_EQ(parsed.second, 28);
	EXPECT_EQ(parsed.nanos, 0);
	EXPECT_EQ(parsed.tz_offset_seconds, 0);
}

TEST(ConvertTimeJ2000, TaiJ2000ToParsedRoundTripWithFractional)
{
	const std::string iso_string = "2020-06-15T14:30:45.123456789Z";
	const double tai_j2000_time = utc_iso_to_tai_j2000(iso_string);
	const ParsedUtcIso parsed = tai_j2000_to_parsed_utc_iso(tai_j2000_time);

	EXPECT_EQ(parsed.year, 2020);
	EXPECT_EQ(parsed.month, 6);
	EXPECT_EQ(parsed.day, 15);
	EXPECT_EQ(parsed.hour, 14);
	EXPECT_EQ(parsed.minute, 30);
	EXPECT_EQ(parsed.second, 45);
	EXPECT_NEAR(parsed.nanos, 123456789, 100);
	EXPECT_EQ(parsed.tz_offset_seconds, 0);
}

TEST(ConvertTimeJ2000, TaiJ2000ToParsedHandlesNegativeJ2000)
{
	const std::string iso_string = "1999-12-31T11:59:27Z";
	const double tai_j2000_time = utc_iso_to_tai_j2000(iso_string);
	const ParsedUtcIso parsed = tai_j2000_to_parsed_utc_iso(tai_j2000_time);

	EXPECT_EQ(parsed.year, 1999);
	EXPECT_EQ(parsed.month, 12);
	EXPECT_EQ(parsed.day, 31);
	EXPECT_EQ(parsed.hour, 11);
	EXPECT_EQ(parsed.minute, 59);
	EXPECT_EQ(parsed.second, 27);
}

TEST(ConvertTimeJ2000, TaiJ2000ToParsedReturnsLeapSecondLabel)
{
	const double tai_j2000_time = utc_iso_to_tai_j2000("2016-12-31T23:59:60.250000000Z");
	const ParsedUtcIso parsed = tai_j2000_to_parsed_utc_iso(tai_j2000_time);

	EXPECT_EQ(parsed.year, 2016);
	EXPECT_EQ(parsed.month, 12);
	EXPECT_EQ(parsed.day, 31);
	EXPECT_EQ(parsed.hour, 23);
	EXPECT_EQ(parsed.minute, 59);
	EXPECT_EQ(parsed.second, 60);
	EXPECT_NEAR(parsed.nanos, 250000000, 100);
	EXPECT_EQ(parsed.tz_offset_seconds, 0);
}

TEST(ConvertTimeJ2000, PosixToTaiJ2000AtEpoch)
{
	// TAI J2000 epoch in POSIX time (2000-01-01 11:59:28 UTC) should convert to 0.0 in TAI J2000
	const double tai_j2000_epoch_posix = static_cast<double>(TAI_J2000_EPOCH_IN_POSIX_TIME);
	EXPECT_DOUBLE_EQ(posix_to_tai_j2000(tai_j2000_epoch_posix), 0.0);
}

TEST(ConvertTimeJ2000, PosixToTaiJ2000ConsistentWithUtcIsoPath)
{
	// Test that posix_to_tai_j2000 gives the same result as utc_iso_to_tai_j2000
	// when converting from UTC POSIX (accounting for leap seconds)
	const std::string iso_string = "2020-01-15T08:30:45.123456Z";
	const double posix_time = utc_iso_to_posix(iso_string);
	const double tai_j2000_direct = posix_to_tai_j2000(posix_time);
	const double tai_j2000_iso_path = utc_iso_to_tai_j2000(iso_string);

	EXPECT_NEAR(tai_j2000_direct, tai_j2000_iso_path, 1.0e-9);
}

TEST(ConvertTimeJ2000, PosixToTaiJ2000WithEpochRecords)
{
	// Test with all reference data
	for(const auto& record : convert_time_test::epoch_records())
	{
		// POSIX timestamps for leap seconds are ambiguous (same POSIX value as the following
		// 00:00:00), so they cannot be deterministically mapped back to a unique UTC label.
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		// Convert POSIX to TAI J2000
		const double tai_j2000_time = posix_to_tai_j2000(record.posix);

		// Should match the reference TAI J2000 value
		EXPECT_NEAR(tai_j2000_time, record.tai, convert_time_test::kTolExactLike)
			<< record.iso << " posix=" << record.posix;
	}
}

TEST(ConvertTimeJ2000, PosixToTaiJ2000RoundTripViaIso)
{
	// Test round-trip: ISO -> POSIX -> TAI J2000 -> back to ISO should be consistent
	const std::string original_iso = "2015-06-30T23:59:60Z"; // Leap second
	const double posix_time = utc_iso_to_posix(original_iso);
	const double tai_j2000_time = posix_to_tai_j2000(posix_time);

	// Convert back: TAI J2000 -> parsed -> ISO
	const ParsedUtcIso parsed = tai_j2000_to_parsed_utc_iso(tai_j2000_time);
	const double tai_j2000_back = parsed_utc_iso_to_tai_j2000(parsed);

	// Should get approximately the same TAI J2000 value back
	EXPECT_NEAR(tai_j2000_time, tai_j2000_back, 1.0e-9);
}

TEST(ConvertTimeJ2000, PosixToTaiJ2000BeforeEpoch)
{
	// Test with times before J2000 epoch
	const std::string iso_string = "1999-12-31T12:00:00Z";
	const double posix_time = utc_iso_to_posix(iso_string);
	const double tai_j2000_time = posix_to_tai_j2000(posix_time);

	// Should be negative (before epoch)
	EXPECT_LT(tai_j2000_time, 0.0);

	// Should match the ISO path
	const double tai_j2000_iso = utc_iso_to_tai_j2000(iso_string);
	EXPECT_NEAR(tai_j2000_time, tai_j2000_iso, 1.0e-9);
}

TEST(ConvertTimeJ2000, PosixToTaiJ2000WithFractionalSeconds)
{
	// Test with fractional seconds
	const std::string iso_string = "2010-03-15T18:45:30.987654321Z";
	const double posix_time = utc_iso_to_posix(iso_string);
	const double tai_j2000_time = posix_to_tai_j2000(posix_time);

	// Should match the ISO path
	const double tai_j2000_iso = utc_iso_to_tai_j2000(iso_string);
	EXPECT_NEAR(tai_j2000_time, tai_j2000_iso, 1.0e-9);

	// Result should be finite
	EXPECT_TRUE(std::isfinite(tai_j2000_time));
}

TEST(ConvertTimeJ2000, TaiJ2000ToPosixAtEpoch)
{
	// TAI J2000 zero should map to the configured TAI J2000 POSIX epoch instant.
	const double posix_time = tai_j2000_to_posix(0.0);
	EXPECT_DOUBLE_EQ(posix_time, static_cast<double>(TAI_J2000_EPOCH_IN_POSIX_TIME));
}

TEST(ConvertTimeJ2000, TaiJ2000ToPosixConsistentWithUtcIsoPath)
{
	const std::string iso_string = "2020-01-15T08:30:45.123456Z";
	const double tai_j2000_time = utc_iso_to_tai_j2000(iso_string);

	const double posix_direct = tai_j2000_to_posix(tai_j2000_time);
	const double posix_iso_path = utc_iso_to_posix(iso_string);

	EXPECT_NEAR(posix_direct, posix_iso_path, 1.0e-9);
}

TEST(ConvertTimeJ2000, TaiJ2000ToPosixWithEpochRecords)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		const double posix_from_tai = tai_j2000_to_posix(record.tai);
		EXPECT_NEAR(posix_from_tai, record.posix, convert_time_test::kTolExactLike)
			<< record.iso << " tai=" << record.tai;
	}
}
