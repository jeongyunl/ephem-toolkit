#include "convert_time_iso8601.h"
#include "convert_time_leap_transition.h"

#include <gtest/gtest.h>
#include <cmath>
#include <stdexcept>

TEST(ParseIso8601Utc, BasicZulu)
{
	const ParsedUtcIso p = utc_iso_to_parsed_utc_iso("2020-01-02T03:04:05");
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
	const ParsedUtcIso p = utc_iso_to_parsed_utc_iso("2020-01-02 03:04:05");
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
	const ParsedUtcIso p = utc_iso_to_parsed_utc_iso("2020-01-02T03:04:05.1");
	EXPECT_EQ(p.nanos, NANOSECONDS_PER_SECOND / 10);
}

TEST(ParseIso8601Utc, FractionalSecondsTruncatesBeyondNanos)
{
	const ParsedUtcIso p = utc_iso_to_parsed_utc_iso("2020-01-02T03:04:05.123456789123");
	EXPECT_EQ(p.nanos, 123456789);
}

TEST(ParseIso8601Utc, TimezoneOffsetPositive)
{
	const ParsedUtcIso p = utc_iso_to_parsed_utc_iso("2020-01-02T03:04:05+02:30");
	EXPECT_EQ(p.tz_offset_seconds, 2 * SECONDS_PER_HOUR + 30 * SECONDS_PER_MINUTE);
}

TEST(ParseIso8601Utc, TimezoneOffsetNegative)
{
	const ParsedUtcIso p = utc_iso_to_parsed_utc_iso("2020-01-02T03:04:05-05:00");
	EXPECT_EQ(p.tz_offset_seconds, -(5 * SECONDS_PER_HOUR));
}

TEST(ParseIso8601Utc, RejectsTrailingGarbage)
{
	EXPECT_THROW(utc_iso_to_parsed_utc_iso("2020-01-02T03:04:05Z trailing"), std::runtime_error);
}

TEST(ParseIso8601Utc, RejectsInvalidLeapSecondPlacement)
{
	EXPECT_THROW(utc_iso_to_parsed_utc_iso("2020-01-02T23:58:60"), std::runtime_error);
}

TEST(ParseIso8601Utc, AllowsLeapSecondAtEndOfDay)
{
	const ParsedUtcIso p = utc_iso_to_parsed_utc_iso("2016-12-31T23:59:60");
	EXPECT_EQ(p.second, 60);
	EXPECT_EQ(p.tz_offset_seconds, 0);
}

TEST(FormatIso8601Utc, CanonicalZulu)
{
	ParsedUtcIso p;
	p.year = 2020;
	p.month = 1;
	p.day = 2;
	p.hour = 3;
	p.minute = 4;
	p.second = 5;

	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p, true), "2020-01-02T03:04:05");
	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p, false), "2020-01-02 03:04:05");
}

TEST(FormatIso8601Utc, TrimsFractionalTrailingZeros)
{
	ParsedUtcIso p;
	p.year = 2020;
	p.month = 1;
	p.day = 2;
	p.hour = 3;
	p.minute = 4;
	p.second = 5;
	p.nanos = 120000000;

	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p, true, 2), "2020-01-02T03:04:05.12");
}

TEST(FormatIso8601Utc, PreservesTimezoneOffset)
{
	ParsedUtcIso p;
	p.year = 2020;
	p.month = 1;
	p.day = 2;
	p.hour = 3;
	p.minute = 4;
	p.second = 5;
	p.tz_offset_seconds = -(5 * SECONDS_PER_HOUR + 30 * SECONDS_PER_MINUTE);

	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p), "2020-01-02 03:04:05-05:30");
}

TEST(FormatIso8601Utc, FormatsLeapSecond)
{
	ParsedUtcIso p;
	p.year = 2016;
	p.month = 12;
	p.day = 31;
	p.hour = 23;
	p.minute = 59;
	p.second = 60;
	p.nanos = 250000000;

	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p, true), "2016-12-31T23:59:60.25");
}

TEST(FormatIso8601Utc, ParseFormatRoundTripCanonicalizesSeparator)
{
	const ParsedUtcIso parsed = utc_iso_to_parsed_utc_iso("2020-01-02 03:04:05.123400000+02:30");
	EXPECT_EQ(parsed_utc_iso_to_utc_iso(parsed, true, 4), "2020-01-02T03:04:05.1234+02:30");
}

TEST(FormatIso8601Utc, UseSpaceSeparator)
{
	ParsedUtcIso p;
	p.year = 2020;
	p.month = 1;
	p.day = 2;
	p.hour = 3;
	p.minute = 4;
	p.second = 5;

	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p, false), "2020-01-02 03:04:05");
}

TEST(FormatIso8601Utc, LimitsFractionalSecondPlaces)
{
	ParsedUtcIso p;
	p.year = 2020;
	p.month = 1;
	p.day = 2;
	p.hour = 3;
	p.minute = 4;
	p.second = 5;
	p.nanos = 123456789;

	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p, true, 3), "2020-01-02T03:04:05.123");
	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p, true, 6), "2020-01-02T03:04:05.123456");
	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p, true, 9), "2020-01-02T03:04:05.123456789");
}

TEST(FormatIso8601Utc, OmitsFractionalWhenZeroPlaces)
{
	ParsedUtcIso p;
	p.year = 2020;
	p.month = 1;
	p.day = 2;
	p.hour = 3;
	p.minute = 4;
	p.second = 5;
	p.nanos = 123456789;

	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p, true, 0), "2020-01-02T03:04:05");
}

TEST(FormatIso8601Utc, CombineSpaceSeparatorAndFractional)
{
	ParsedUtcIso p;
	p.year = 2020;
	p.month = 1;
	p.day = 2;
	p.hour = 3;
	p.minute = 4;
	p.second = 5;
	p.nanos = 500000000;

	EXPECT_EQ(parsed_utc_iso_to_utc_iso(p, false, 3), "2020-01-02 03:04:05.5");
}

TEST(CumulativeLeapCorrection, Pre1972UsesLinearModel)
{
	// Ensure the pre-1972 branch is exercised and returns a finite value.
	const double utc_1971 = static_cast<double>(calendar_date_to_posix_days(1971, 1, 1) * SECONDS_PER_DAY);
	const double corr = cumulative_leap_correction({ }, utc_1971, false);
	EXPECT_TRUE(std::isfinite(corr));
}

TEST(CumulativeLeapCorrection, IncludeTransitionAtEqual)
{
	const std::int64_t t0 = calendar_date_to_posix_days(2017, 1, 1) * SECONDS_PER_DAY;
	const std::vector<LeapTransition> tr = { LeapTransition{ t0, 1 } };

	const double corr_exclusive = cumulative_leap_correction(tr, static_cast<double>(t0), false);
	const double corr_inclusive = cumulative_leap_correction(tr, static_cast<double>(t0), true);
	EXPECT_NE(corr_exclusive, corr_inclusive);
	EXPECT_EQ(corr_inclusive, corr_exclusive + 1.0);
}
