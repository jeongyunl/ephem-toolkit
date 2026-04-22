#include "convert_time_iso8601.h"

#include <gtest/gtest.h>
#include <cmath>
#include <stdexcept>

TEST(ParseIso8601Utc, BasicZulu)
{
	const ParsedUtcIso p = parse_iso8601_utc("2020-01-02T03:04:05Z");
	EXPECT_EQ(p.year, 2020);
	EXPECT_EQ(p.month, 1);
	EXPECT_EQ(p.day, 2);
	EXPECT_EQ(p.hour, 3);
	EXPECT_EQ(p.minute, 4);
	EXPECT_EQ(p.second, 5);
	EXPECT_EQ(p.nanos, 0);
	EXPECT_EQ(p.tz_offset_seconds, 0);
}

TEST(ParseIso8601Utc, SpaceSeparator)
{
	const ParsedUtcIso p = parse_iso8601_utc("2020-01-02 03:04:05Z");
	EXPECT_EQ(p.year, 2020);
	EXPECT_EQ(p.month, 1);
	EXPECT_EQ(p.day, 2);
	EXPECT_EQ(p.hour, 3);
	EXPECT_EQ(p.minute, 4);
	EXPECT_EQ(p.second, 5);
	EXPECT_EQ(p.nanos, 0);
	EXPECT_EQ(p.tz_offset_seconds, 0);
}

TEST(ParseIso8601Utc, FractionalSecondsPadsToNanos)
{
	const ParsedUtcIso p = parse_iso8601_utc("2020-01-02T03:04:05.1Z");
	EXPECT_EQ(p.nanos, NANOSECONDS_PER_SECOND / 10);
}

TEST(ParseIso8601Utc, FractionalSecondsTruncatesBeyondNanos)
{
	const ParsedUtcIso p = parse_iso8601_utc("2020-01-02T03:04:05.123456789123Z");
	EXPECT_EQ(p.nanos, 123456789);
}

TEST(ParseIso8601Utc, TimezoneOffsetPositive)
{
	const ParsedUtcIso p = parse_iso8601_utc("2020-01-02T03:04:05+02:30");
	EXPECT_EQ(p.tz_offset_seconds, 2 * SECONDS_PER_HOUR + 30 * SECONDS_PER_MINUTE);
}

TEST(ParseIso8601Utc, TimezoneOffsetNegative)
{
	const ParsedUtcIso p = parse_iso8601_utc("2020-01-02T03:04:05-05:00");
	EXPECT_EQ(p.tz_offset_seconds, -(5 * SECONDS_PER_HOUR));
}

TEST(ParseIso8601Utc, RejectsTrailingGarbage)
{
	EXPECT_THROW(parse_iso8601_utc("2020-01-02T03:04:05Z trailing"), std::runtime_error);
}

TEST(ParseIso8601Utc, RejectsInvalidLeapSecondPlacement)
{
	EXPECT_THROW(parse_iso8601_utc("2020-01-02T23:58:60Z"), std::runtime_error);
}

TEST(ParseIso8601Utc, AllowsLeapSecondAtEndOfDay)
{
	const ParsedUtcIso p = parse_iso8601_utc("2016-12-31T23:59:60Z");
	EXPECT_EQ(p.second, 60);
	EXPECT_EQ(p.tz_offset_seconds, 0);
}

TEST(CumulativeLeapCorrection, Pre1972UsesLinearModel)
{
	// Ensure the pre-1972 branch is exercised and returns a finite value.
	const double utc_1971 = static_cast<double>(posix_days_from_civil(1971, 1, 1) * SECONDS_PER_DAY);
	const double corr = cumulative_leap_correction({}, utc_1971, false);
	EXPECT_TRUE(std::isfinite(corr));
}

TEST(CumulativeLeapCorrection, IncludeTransitionAtEqual)
{
	const std::int64_t t0 = posix_days_from_civil(2017, 1, 1) * SECONDS_PER_DAY;
	const std::vector<LeapTransition> tr = { LeapTransition{ t0, 1 } };

	const double corr_exclusive = cumulative_leap_correction(tr, static_cast<double>(t0), false);
	const double corr_inclusive = cumulative_leap_correction(tr, static_cast<double>(t0), true);
	EXPECT_NE(corr_exclusive, corr_inclusive);
	EXPECT_EQ(corr_inclusive, corr_exclusive + 1.0);
}
