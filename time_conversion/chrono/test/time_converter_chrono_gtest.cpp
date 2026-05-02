#include "time_converter.h"
#include "chrono/time_converter_chrono.h"
#include "test/convert_time_gtest_common.h"

#include <gtest/gtest.h>
#include <chrono>
#include <cmath>

namespace
{

using convert_time_test::EpochRecord;

class ConvertTimeDataDrivenTest : public ::testing::Test
{
protected:
	static void SetUpTestSuite() {}
};

} // namespace

TEST(ConvertTimeChrono, SysTimeToUtcPosixMatchesChronoDurationSeconds)
{
	const auto sys_time = std::chrono::system_clock::time_point{ std::chrono::seconds{ 123456789 } };
	EXPECT_DOUBLE_EQ(TimeConverterChrono::instance().sys_time_to_utc_posix(sys_time), 123456789.0);
}

TEST(ConvertTimeChrono, SysTimeToUtcPosixSupportsSubSecondPrecision)
{
	using namespace std::chrono;
	const auto sys_time = system_clock::time_point{ seconds{ 10 } + milliseconds{ 250 } };
	EXPECT_NEAR(TimeConverterChrono::instance().sys_time_to_utc_posix(sys_time), 10.25, 1.0e-12);
}

TEST(ConvertTimeChrono, UtcPosixToSysTimeRoundTripIsStable)
{
	using namespace std::chrono;
	const double posix = 98765.4321;
	const auto sys_time = TimeConverterChrono::instance().posix_to_sys_time(posix);
	EXPECT_NEAR(TimeConverterChrono::instance().sys_time_to_utc_posix(sys_time), posix, 1.0e-9);
}

TEST(ConvertTimeChrono, UtcPosixToSysTimeSupportsCustomDuration)
{
	using namespace std::chrono;
	const double posix = 42.0;
	const auto sys_time = TimeConverterChrono::instance().posix_to_sys_time<milliseconds>(posix);
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
		EXPECT_EQ(TimeConverterChrono::instance().sys_time_to_utc_iso(tc.input, true), tc.expected);
	}
}

TEST(ConvertTimeChrono, SysTimeToUtcIsoSupportsCustomDurationSeconds)
{
	using namespace std::chrono;
	const auto t = sys_time<seconds>{ sys_days{ 1970y / January / 1 } + seconds{ 1 } };
	EXPECT_EQ(TimeConverterChrono::instance().sys_time_to_utc_iso(t), "1970-01-01 00:00:01");
}

TEST(ConvertTimeChrono, SysTimeToUtcIsoSupportsCustomDurationMicroseconds)
{
	using namespace std::chrono;
	const auto t =
		sys_time<microseconds>{ sys_days{ 1970y / January / 1 } + seconds{ 1 } + microseconds{ 2 } };
	EXPECT_EQ(TimeConverterChrono::instance().sys_time_to_utc_iso(t), "1970-01-01 00:00:01.000002");
}

TEST(ConvertTimeChrono, UtcPosixToSysTimeTruncatesTowardZeroForMilliseconds)
{
	using namespace std::chrono;
	const double posix = 1.2345;
	const auto sys_time = TimeConverterChrono::instance().posix_to_sys_time<milliseconds>(posix);
	EXPECT_EQ(sys_time.time_since_epoch(), milliseconds{ 1234 });
}

TEST(ConvertTimeChrono, UtcPosixToSysTimeHandlesNegativeEpochForMilliseconds)
{
	using namespace std::chrono;
	const double posix = -1.25;
	const auto sys_time = TimeConverterChrono::instance().posix_to_sys_time<milliseconds>(posix);
	EXPECT_EQ(sys_time.time_since_epoch(), milliseconds{ -1250 });
}

TEST(ConvertTimeChrono, SysTimeToUtcPosixSupportsCustomRepAndPeriod)
{
	using namespace std::chrono;
	const auto t = system_clock::time_point{ milliseconds{ 1500 } };
	const auto ms = TimeConverterChrono::instance().sys_time_to_utc_posix<long long, std::milli>(t);
	EXPECT_EQ(ms, 1500);
}

TEST(ConvertTimeChrono, SysTimeToUtcPosixHandlesNegativeEpoch)
{
	using namespace std::chrono;
	const auto t = system_clock::time_point{ milliseconds{ -1250 } };
	EXPECT_NEAR(TimeConverterChrono::instance().sys_time_to_utc_posix(t), -1.25, 1.0e-12);
}

#ifdef HAS_CHRONO_UTC_CLOCK
TEST(ConvertTimeChrono, UtcPosixToUtcTimeSupportsCustomDuration)
{
	using namespace std::chrono;
	const double posix = 42.0;
	const auto t = TimeConverterChrono::instance().posix_to_utc_time<milliseconds>(posix);
	EXPECT_EQ(t.time_since_epoch(), milliseconds{ 42000 });
}

TEST(ConvertTimeChrono, UtcIsoToUtcTimePreservesLeapSeconds)
{
	using namespace std::chrono;

	for(const auto& record : convert_time_test::epoch_records())
	{
		const auto t = TimeConverterChrono::instance().utc_iso_to_utc_time<milliseconds>(record.iso);
		EXPECT_TRUE(TimeConverter::instance()
						.iso_8601_equal(TimeConverterChrono::instance().utc_time_to_utc_iso(t), record.iso, 3)
		) << record.iso;
	}
}

TEST(ConvertTimeChrono, ParsedUtcIsoToUtcTimePreservesLeapSeconds)
{
	using namespace std::chrono;

	for(const auto& record : convert_time_test::epoch_records())
	{
		const ParsedUtcIso parsed = TimeConverter::instance().utc_iso_to_parsed_utc_iso(record.iso);
		const auto t = TimeConverterChrono::instance().parsed_utc_iso_to_utc_time<milliseconds>(parsed);
		EXPECT_TRUE(TimeConverter::instance()
						.iso_8601_equal(TimeConverterChrono::instance().utc_time_to_utc_iso(t), record.iso, 3)
		) << record.iso;
	}
}

TEST(ConvertTimeChrono, UtcPosixToUtcTimeTruncatesTowardZeroForMilliseconds)
{
	using namespace std::chrono;
	const double posix = 1.2345;
	const auto t = TimeConverterChrono::instance().posix_to_utc_time<milliseconds>(posix);
	EXPECT_EQ(t.time_since_epoch(), milliseconds{ 1234 });
}

TEST(ConvertTimeChrono, UtcPosixToUtcTimeHandlesNegativeEpochForMilliseconds)
{
	using namespace std::chrono;
	const double posix = -1.25;
	const auto t = TimeConverterChrono::instance().posix_to_utc_time<milliseconds>(posix);
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
		EXPECT_EQ(TimeConverterChrono::instance().utc_time_to_utc_iso(tc.input, true), tc.expected);
	}
}
#endif

TEST(ConvertTimeChrono, IsoToAllNumericScalesMatchReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		{
			const auto sys_time = TimeConverterChrono::instance().utc_iso_to_sys_time(record.iso);
			EXPECT_NEAR(
				std::chrono::duration<double>(sys_time.time_since_epoch()).count(),
				record.posix,
				convert_time_test::kTolExactLike
			) << record.iso;
		}

#ifdef HAS_CHRONO_TAI_CLOCK
		{
			const auto tai_time = TimeConverterChrono::instance().utc_iso_to_tai_time(record.iso);
			const auto iso_from_tai = std::format("{:%F %T}", std::chrono::tai_clock::to_utc(tai_time));
			EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(record.iso, iso_from_tai, 3))
				<< record.iso << " != " << iso_from_tai;
		}
#endif

		// Before 1972, UTC and TAI were not synchronized, so the ISO string derived from TAI may not match
		// the reference UTC ISO string.
		if(record.posix >= epochs::UTC_1972_EPOCH_IN_POSIX_TIME)
		{
			{
				const auto sys_time = TimeConverterChrono::instance().tai_j2000_to_sys_time(record.tai);
				EXPECT_NEAR(
					std::chrono::duration<double>(sys_time.time_since_epoch()).count(),
					record.posix,
					convert_time_test::kTolExactLike
				) << record.iso;
			}

			{
				const auto iso_from_tai_j2000 =
					TimeConverterChrono::instance().tai_j2000_to_utc_iso(record.tai);
				EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(iso_from_tai_j2000, record.iso, 3))
					<< iso_from_tai_j2000 << " != " << record.iso;
			}

#ifdef HAS_CHRONO_UTC_CLOCK
			{
				const auto utc_time = TimeConverterChrono::instance().tai_j2000_to_utc_time(record.tai);
				const auto iso_from_utc = std::format("{:%F %T}", utc_time);
				EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(record.iso, iso_from_utc, 3))
					<< record.iso << " != " << iso_from_utc;
			}

			{
				const auto utc_time = TimeConverterChrono::instance().tt_j2000_to_utc_time(record.tt);
				const auto iso_from_utc = std::format("{:%F %T}", utc_time);
				EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(record.iso, iso_from_utc, 3))
					<< record.iso << " != " << iso_from_utc;
			}

			{
				const auto utc_time = TimeConverterChrono::instance().tdb_j2000_to_utc_time(record.tdb);
				const auto iso_from_utc = std::format("{:%F %T}", utc_time);
				EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(record.iso, iso_from_utc, 3))
					<< record.iso << " != " << iso_from_utc;
			}
#endif
		}

		// POSIX timestamps during leap seconds are ambiguous and cannot be reliably tested against reference
		// data, so skip those rows.
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		{
			const auto sys_time = TimeConverterChrono::instance().posix_to_sys_time(record.posix);
			EXPECT_NEAR(
				std::chrono::duration<double>(sys_time.time_since_epoch()).count(),
				record.posix,
				convert_time_test::kTolExactLike
			) << record.iso;
		}

		{
			const auto sys_time = TimeConverterChrono::instance().utc_j2000_to_sys_time(record.utc);
			EXPECT_NEAR(
				std::chrono::duration<double>(sys_time.time_since_epoch()).count(),
				record.posix,
				convert_time_test::kTolExactLike
			) << record.iso;
		}

#ifdef HAS_CHRONO_UTC_CLOCK
		{
			const auto utc_time = TimeConverterChrono::instance().posix_to_utc_time(record.posix);
			const auto iso_from_utc = std::format("{:%F %T}", utc_time);
			EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(record.iso, iso_from_utc, 3))
				<< record.iso << " != " << iso_from_utc;
		}

		{
			const auto utc_time = TimeConverterChrono::instance().utc_j2000_to_utc_time(record.utc);
			const auto iso_from_utc = std::format("{:%F %T}", utc_time);
			EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(record.iso, iso_from_utc, 3))
				<< record.iso << " != " << iso_from_utc;
		}
#endif

#ifdef HAS_CHRONO_TAI_CLOCK
		{
			const auto tai_time = TimeConverterChrono::instance().posix_to_tai_time(record.posix);
			const auto iso_from_tai = std::format("{:%F %T}", std::chrono::tai_clock::to_utc(tai_time));
			EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(record.iso, iso_from_tai, 3))
				<< record.iso << " != " << iso_from_tai;
		}

		{
			const auto tai_time = TimeConverterChrono::instance().utc_j2000_to_tai_time(record.utc);
			const auto iso_from_tai = std::format("{:%F %T}", std::chrono::tai_clock::to_utc(tai_time));
			EXPECT_TRUE(TimeConverter::instance().iso_8601_equal(record.iso, iso_from_tai, 3))
				<< record.iso << " != " << iso_from_tai;
		}
#endif
	}
}
