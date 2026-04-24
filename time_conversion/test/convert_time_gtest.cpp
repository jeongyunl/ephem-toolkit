#include "convert_time.h"
#include "convert_time_chrono.h"
#include "convert_time_j2000.h"
#include "test/convert_time_common_gtest.h"

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
		EXPECT_NEAR(utc_iso_to_posix(record.iso), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_iso_to_utc_j2000(record.iso), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_iso_to_tai_j2000(record.iso), record.tai, convert_time_test::kTolTimeScale)
			<< record.iso;
		EXPECT_NEAR(utc_iso_to_tt_j2000(record.iso), record.tt, convert_time_test::kTolTimeScale)
			<< record.iso;
		EXPECT_NEAR(utc_iso_to_tdb_j2000(record.iso), record.tdb, convert_time_test::kTolTdb) << record.iso;

		const auto sys_time = utc_iso_to_sys_time(record.iso);
		EXPECT_NEAR(
			std::chrono::duration<double>(sys_time.time_since_epoch()).count(),
			record.posix,
			convert_time_test::kTolExactLike
		) << record.iso;

#ifdef HAS_CHRONO_TAI_CLOCK
		const auto tai_time = utc_iso_to_tai_time(record.iso);
		const auto iso_from_tai = std::format("{:%F %T}", std::chrono::tai_clock::to_utc(tai_time));
		EXPECT_TRUE(iso_8601_equal(record.iso, iso_from_tai, 3)) << record.iso << " != " << iso_from_tai;
#endif
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

		const auto iso_from_posix = posix_to_utc_iso(record.posix);
		EXPECT_TRUE(iso_8601_equal(iso_from_posix, record.iso, 3)) << iso_from_posix << " != " << record.iso;

		EXPECT_NEAR(posix_to_utc_j2000(record.posix), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(posix_to_tai_j2000(record.posix), record.tai, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(posix_to_tt_j2000(record.posix), record.tt, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(posix_to_tdb_j2000(record.posix), record.tdb, convert_time_test::kTolTdb) << record.iso;

		const auto sys_time = posix_to_sys_time(record.posix);
		EXPECT_NEAR(
			std::chrono::duration<double>(sys_time.time_since_epoch()).count(),
			record.posix,
			convert_time_test::kTolExactLike
		) << record.iso;

#ifdef HAS_CHRONO_UTC_CLOCK
		const auto utc_time = posix_to_utc_time(record.posix);
		const auto iso_from_utc = std::format("{:%F %T}", utc_time);
		EXPECT_TRUE(iso_8601_equal(record.iso, iso_from_utc, 3)) << record.iso << " != " << iso_from_utc;
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
		const auto tai_time = posix_to_tai_time(record.posix);
		const auto iso_from_tai = std::format("{:%F %T}", std::chrono::tai_clock::to_utc(tai_time));
		EXPECT_TRUE(iso_8601_equal(record.iso, iso_from_tai, 3)) << record.iso << " != " << iso_from_tai;
#endif
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

		const auto iso_from_utc_j2000 = utc_j2000_to_utc_iso(record.utc);
		EXPECT_TRUE(iso_8601_equal(iso_from_utc_j2000, record.iso, 3))
			<< iso_from_utc_j2000 << " != " << record.iso;

		EXPECT_NEAR(utc_j2000_to_posix(record.utc), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_j2000_to_tai_j2000(record.utc), record.tai, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_j2000_to_tt_j2000(record.utc), record.tt, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(utc_j2000_to_tdb_j2000(record.utc), record.tdb, convert_time_test::kTolTdb) << record.iso;

		const auto sys_time = utc_j2000_to_sys_time(record.utc);
		EXPECT_NEAR(
			std::chrono::duration<double>(sys_time.time_since_epoch()).count(),
			record.posix,
			convert_time_test::kTolExactLike
		) << record.iso;

#ifdef HAS_CHRONO_UTC_CLOCK
		const auto utc_time = utc_j2000_to_utc_time(record.utc);
		const auto iso_from_utc = std::format("{:%F %T}", utc_time);
		EXPECT_TRUE(iso_8601_equal(record.iso, iso_from_utc, 3)) << record.iso << " != " << iso_from_utc;
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
		const auto tai_time = utc_j2000_to_tai_time(record.utc);
		const auto iso_from_tai = std::format("{:%F %T}", std::chrono::tai_clock::to_utc(tai_time));
		EXPECT_TRUE(iso_8601_equal(record.iso, iso_from_tai, 3)) << record.iso << " != " << iso_from_tai;
#endif
	}
}

TEST_F(ConvertTimeDataDrivenTest, TaiToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(tai_j2000_to_posix(record.tai), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tai_j2000_to_utc_j2000(record.tai), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tai_j2000_to_tt_j2000(record.tai), record.tt, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tai_j2000_to_tdb_j2000(record.tai), record.tdb, convert_time_test::kTolTdb) << record.iso;

		const auto sys_time = tai_j2000_to_sys_time(record.tai);
		EXPECT_NEAR(
			std::chrono::duration<double>(sys_time.time_since_epoch()).count(),
			record.posix,
			convert_time_test::kTolExactLike
		) << record.iso;

		// Before 1972, UTC and TAI were not synchronized, so the ISO string derived from TAI may not match
		// the reference UTC ISO string.
		if(record.posix >= UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			const auto iso_from_tai_j2000 = tai_j2000_to_utc_iso(record.tai);
			EXPECT_TRUE(iso_8601_equal(iso_from_tai_j2000, record.iso, 3))
				<< iso_from_tai_j2000 << " != " << record.iso;

#ifdef HAS_CHRONO_UTC_CLOCK
			const auto utc_time = tai_j2000_to_utc_time(record.tai);
			const auto iso_from_utc = std::format("{:%F %T}", utc_time);
			EXPECT_TRUE(iso_8601_equal(record.iso, iso_from_utc, 3)) << record.iso << " != " << iso_from_utc;
#endif
		}
	}
}

TEST_F(ConvertTimeDataDrivenTest, TtToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(tt_j2000_to_posix(record.tt), record.posix, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tt_j2000_to_utc_j2000(record.tt), record.utc, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tt_j2000_to_tai_j2000(record.tt), record.tai, convert_time_test::kTolExactLike)
			<< record.iso;
		EXPECT_NEAR(tt_j2000_to_tdb_j2000(record.tt), record.tdb, convert_time_test::kTolTdb) << record.iso;

		// Before 1972, UTC and TAI (TT as well by proxy) were not synchronized, so the ISO string derived
		// from TT may not match the reference UTC ISO string.
		if(record.posix >= UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			const auto iso_from_tt_j2000 = tt_j2000_to_utc_iso(record.tt);
			EXPECT_TRUE(iso_8601_equal(iso_from_tt_j2000, record.iso, 3))
				<< iso_from_tt_j2000 << " != " << record.iso;

#ifdef HAS_CHRONO_UTC_CLOCK
			const auto utc_time = tt_j2000_to_utc_time(record.tt);
			const auto iso_from_utc = std::format("{:%F %T}", utc_time);
			EXPECT_TRUE(iso_8601_equal(record.iso, iso_from_utc, 3)) << record.iso << " != " << iso_from_utc;
#endif
		}
	}
}

TEST_F(ConvertTimeDataDrivenTest, TdbToOtherScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(tdb_j2000_to_posix(record.tdb), record.posix, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(tdb_j2000_to_utc_j2000(record.tdb), record.utc, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(tdb_j2000_to_tai_j2000(record.tdb), record.tai, convert_time_test::kTolTdb) << record.iso;
		EXPECT_NEAR(tdb_j2000_to_tt_j2000(record.tdb), record.tt, convert_time_test::kTolTdb) << record.iso;

		// Before 1972, UTC and TAI (TDB as well by proxy) were not synchronized, so the ISO string derived
		// from TDB may not match the reference UTC ISO string.
		if(record.posix >= UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			const auto iso_from_tdb_j2000 = tdb_j2000_to_utc_iso(record.tdb);
			EXPECT_TRUE(iso_8601_equal(iso_from_tdb_j2000, record.iso, 3))
				<< iso_from_tdb_j2000 << " != " << record.iso;

#ifdef HAS_CHRONO_UTC_CLOCK
			const auto utc_time = tdb_j2000_to_utc_time(record.tdb);
			const auto iso_from_utc = std::format("{:%F %T}", utc_time);
			EXPECT_TRUE(iso_8601_equal(record.iso, iso_from_utc, 3)) << record.iso << " != " << iso_from_utc;
#endif
		}
	}
}

TEST_F(ConvertTimeDataDrivenTest, UtcIsoIdentityRoundTripForRecords)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_TRUE(iso_8601_equal(utc_iso_to_utc_iso(record.iso), record.iso, 3)) << record.iso;
	}
}

TEST(ConvertTimeIso, Iso8601EqualTreatsTSeparatorAsOptional)
{
	EXPECT_TRUE(iso_8601_equal("1970-01-01T00:00:00.000000", "1970-01-01 00:00:00.000", 3));
	EXPECT_TRUE(iso_8601_equal("1970-01-01T00:00:00.000000", "1970-01-01 00:00:00.000", 6));
}

TEST(ConvertTimeIso, Iso8601EqualUsesRequestedFractionalPrecision)
{
	EXPECT_TRUE(iso_8601_equal("1970-01-01T00:00:00.123456", "1970-01-01 00:00:00.123000", 3));
	EXPECT_FALSE(iso_8601_equal("1970-01-01T00:00:00.123456", "1970-01-01 00:00:00.123000", 4));
	EXPECT_TRUE(iso_8601_equal("1970-01-01T00:00:00.9", "1970-01-01 00:00:00.900000", 6));
}

TEST(ConvertTimeIso, Iso8601EqualReturnsFalseForInvalidInputOrPrecision)
{
	EXPECT_FALSE(iso_8601_equal("not-a-time", "1970-01-01 00:00:00.000", 3));
	EXPECT_FALSE(iso_8601_equal("1970-01-01T00:00:00.000", "1970-01-01 00:00:00.000", 10));
}

TEST_F(ConvertTimeDataDrivenTest, NumericRoundTripUsingUtcIsStableForNonLeapSecondRows)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		const double utc_from_posix = posix_to_utc_j2000(record.posix);
		const double posix_from_utc = utc_j2000_to_posix(utc_from_posix);
		EXPECT_NEAR(posix_from_utc, record.posix, convert_time_test::kTolExactLike) << record.iso;

		const double tai_from_utc = utc_j2000_to_tai_j2000(record.utc);
		const double utc_from_tai = tai_j2000_to_utc_j2000(tai_from_utc);
		EXPECT_NEAR(utc_from_tai, record.utc, convert_time_test::kTolExactLike) << record.iso;
	}
}

TEST(ConvertTimeChrono, SysTimeToUtcPosixMatchesChronoDurationSeconds)
{
	const auto sys_time = std::chrono::system_clock::time_point{ std::chrono::seconds{ 123456789 } };
	EXPECT_DOUBLE_EQ(sys_time_to_utc_posix(sys_time), 123456789.0);
}

TEST(ConvertTimeChrono, SysTimeToUtcPosixSupportsSubSecondPrecision)
{
	using namespace std::chrono;
	const auto sys_time = system_clock::time_point{ seconds{ 10 } + milliseconds{ 250 } };
	EXPECT_NEAR(sys_time_to_utc_posix(sys_time), 10.25, 1.0e-12);
}

TEST(ConvertTimeChrono, UtcPosixToSysTimeRoundTripIsStable)
{
	using namespace std::chrono;
	const double posix = 98765.4321;
	const auto sys_time = posix_to_sys_time(posix);
	EXPECT_NEAR(sys_time_to_utc_posix(sys_time), posix, 1.0e-9);
}

TEST(ConvertTimeChrono, UtcPosixToSysTimeSupportsCustomDuration)
{
	using namespace std::chrono;
	const double posix = 42.0;
	const auto sys_time = posix_to_sys_time<milliseconds>(posix);
	EXPECT_EQ(sys_time.time_since_epoch(), milliseconds{ 42000 });
}

TEST(ConvertTimeChrono, SysTimeToUtcIsoFormatsWithoutTimezoneSuffix)
{
	using namespace std::chrono;

	struct TestCase
	{
		sys_time<milliseconds> input;
		const char* expected;
	};

	const TestCase cases[] = {
		{ sys_days{ 1970y / January / 1 } + seconds{ 0 }, "1970-01-01T00:00:00.000" },
		{ sys_days{ 1970y / January / 1 } + seconds{ 1 }, "1970-01-01T00:00:01.000" },
		{ sys_days{ 1970y / January / 1 } + seconds{ 59 }, "1970-01-01T00:00:59.000" },
		{ sys_days{ 1970y / January / 1 } + minutes{ 1 }, "1970-01-01T00:01:00.000" },
		{ sys_days{ 1970y / January / 2 } + seconds{ 0 }, "1970-01-02T00:00:00.000" },

		{ sys_days{ 2016y / December / 31 } + hours{ 23 } + minutes{ 59 } + seconds{ 59 },
		  "2016-12-31T23:59:59.000" },
		{ sys_days{ 2016y / December / 31 } + hours{ 23 } + minutes{ 59 } + seconds{ 60 },
		  "2017-01-01T00:00:00.000" },
	};

	for(const auto& tc : cases)
	{
		EXPECT_EQ(sys_time_to_utc_iso(tc.input), tc.expected);
	}
}

TEST(ConvertTimeChrono, SysTimeToUtcIsoSupportsCustomDurationSeconds)
{
	using namespace std::chrono;
	const auto t = sys_time<seconds>{ sys_days{ 1970y / January / 1 } + seconds{ 1 } };
	EXPECT_EQ(sys_time_to_utc_iso(t), "1970-01-01T00:00:01");
}

TEST(ConvertTimeChrono, SysTimeToUtcIsoSupportsCustomDurationMicroseconds)
{
	using namespace std::chrono;
	const auto t =
		sys_time<microseconds>{ sys_days{ 1970y / January / 1 } + seconds{ 1 } + microseconds{ 2 } };
	EXPECT_EQ(sys_time_to_utc_iso(t), "1970-01-01T00:00:01.000002");
}

TEST(ConvertTimeChrono, UtcPosixToSysTimeTruncatesTowardZeroForMilliseconds)
{
	using namespace std::chrono;
	const double posix = 1.2345;
	const auto sys_time = posix_to_sys_time<milliseconds>(posix);
	EXPECT_EQ(sys_time.time_since_epoch(), milliseconds{ 1234 });
}

TEST(ConvertTimeChrono, UtcPosixToSysTimeHandlesNegativeEpochForMilliseconds)
{
	using namespace std::chrono;
	const double posix = -1.25;
	const auto sys_time = posix_to_sys_time<milliseconds>(posix);
	EXPECT_EQ(sys_time.time_since_epoch(), milliseconds{ -1250 });
}

TEST(ConvertTimeChrono, SysTimeToUtcPosixSupportsCustomRepAndPeriod)
{
	using namespace std::chrono;
	const auto t = system_clock::time_point{ milliseconds{ 1500 } };
	const auto ms = sys_time_to_utc_posix<long long, std::milli>(t);
	EXPECT_EQ(ms, 1500);
}

TEST(ConvertTimeChrono, SysTimeToUtcPosixHandlesNegativeEpoch)
{
	using namespace std::chrono;
	const auto t = system_clock::time_point{ milliseconds{ -1250 } };
	EXPECT_NEAR(sys_time_to_utc_posix(t), -1.25, 1.0e-12);
}

#ifdef HAS_CHRONO_UTC_CLOCK
TEST(ConvertTimeChrono, UtcPosixToUtcTimeSupportsCustomDuration)
{
	using namespace std::chrono;
	const double posix = 42.0;
	const auto t = posix_to_utc_time<milliseconds>(posix);
	EXPECT_EQ(t.time_since_epoch(), milliseconds{ 42000 });
}

TEST(ConvertTimeChrono, UtcIsoToUtcTimePreservesLeapSeconds)
{
	using namespace std::chrono;

	for(const auto& record : convert_time_test::epoch_records())
	{
		// Rount-trip conversion test
		// ISO to chrono::utc_time and back to ISO should preserve the original string for all rows, including
		// leap seconds.
		const auto t = utc_iso_to_utc_time<milliseconds>(record.iso);
		EXPECT_TRUE(iso_8601_equal(utc_time_to_utc_iso(t), record.iso, 3)) << record.iso;
	}
}

TEST(ConvertTimeChrono, ParsedUtcIsoToUtcTimePreservesLeapSeconds)
{
	using namespace std::chrono;

	for(const auto& record : convert_time_test::epoch_records())
	{
		const ParsedUtcIso parsed = utc_iso_to_parsed_utc_iso(record.iso);
		const auto t = parsed_utc_iso_to_utc_time<milliseconds>(parsed);
		EXPECT_TRUE(iso_8601_equal(utc_time_to_utc_iso(t), record.iso, 3)) << record.iso;
	}
}

TEST(ConvertTimeChrono, UtcPosixToUtcTimeTruncatesTowardZeroForMilliseconds)
{
	using namespace std::chrono;
	const double posix = 1.2345;
	const auto t = posix_to_utc_time<milliseconds>(posix);
	EXPECT_EQ(t.time_since_epoch(), milliseconds{ 1234 });
}

TEST(ConvertTimeChrono, UtcPosixToUtcTimeHandlesNegativeEpochForMilliseconds)
{
	using namespace std::chrono;
	const double posix = -1.25;
	const auto t = posix_to_utc_time<milliseconds>(posix);
	EXPECT_EQ(t.time_since_epoch(), milliseconds{ -1250 });
}

TEST(ConvertTimeChrono, UtcTimeToUtcIsoFormatsWithoutTimezoneSuffix)
{
	using namespace std::chrono;

	struct TestCase
	{
		utc_time<milliseconds> input;
		const char* expected;
	};

	const TestCase cases[] = {
		{ utc_time<milliseconds>{ milliseconds{ 0 } }, "1970-01-01T00:00:00.000" },
		{ utc_time<milliseconds>{ milliseconds{ 1000 } }, "1970-01-01T00:00:01.000" },
		{ utc_time<milliseconds>{ milliseconds{ 86400000 } }, "1970-01-02T00:00:00.000" },

		{ std::chrono::utc_clock::from_sys(
			  sys_days{ 2016y / December / 31 } + hours{ 23 } + minutes{ 59 } + seconds{ 59 }
		  ) + seconds(1),
		  "2016-12-31T23:59:60.000" },

		{ std::chrono::utc_clock::from_sys(
			  sys_days{ 2016y / December / 31 } + hours{ 23 } + minutes{ 59 } + seconds{ 59 }
		  ) + seconds(2),
		  "2017-01-01T00:00:00.000" },

	};

	for(const auto& tc : cases)
	{
		EXPECT_EQ(utc_time_to_utc_iso(tc.input), tc.expected);
	}
}
#endif
