#include "convert_time_disp_tbl.h"
#include "convert_time_j2000.h"

#include <gtest/gtest.h>
#include <string>
#include <variant>

namespace
{
constexpr double kTol = 2.0e-4;
}

TEST(ConvertTimeDispFn, ShouldConvertUtcIsoToUtcPosix)
{
	const TimeValue input = std::string("2000-01-01T12:00:00");
	const auto output = convert_time(input, TimeFormat::UTC_ISO8601, TimeFormat::POSIX);

	ASSERT_TRUE(std::holds_alternative<double>(output));
	EXPECT_NEAR(std::get<double>(output), 946728000.0, kTol);
}

TEST(ConvertTimeDispFn, ShouldConvertUtcPosixToUtcIso)
{
	const TimeValue input = 946728000.0;
	const auto output = convert_time(input, TimeFormat::POSIX, TimeFormat::UTC_ISO8601);

	ASSERT_TRUE(std::holds_alternative<std::string>(output));
	;

	EXPECT_TRUE(iso_8601_equal(std::get<std::string>(output), "2000-01-01T12:00:00.000", 3))
		<< std::get<std::string>(output) << " != 2000-01-01T12:00:00.000";
}

TEST(ConvertTimeDispFn, ShouldThrowBadVariantAccessWhenUtcIsoFormatButDoubleProvided)
{
	const TimeValue input = 946728000.0;
	EXPECT_THROW(
		{ (void)convert_time(input, TimeFormat::UTC_ISO8601, TimeFormat::POSIX); },
		std::invalid_argument
	);
}

TEST(ConvertTimeDispFn, ShouldThrowBadVariantAccessWhenNumericFormatButStringProvided)
{
	const TimeValue input = std::string("2000-01-01T12:00:00");
	EXPECT_THROW(
		{ (void)convert_time(input, TimeFormat::POSIX, TimeFormat::UTC_J2000); },
		std::invalid_argument
	);
}

TEST(ConvertTimeDispFn, ShouldThrowInvalidArgumentForUnsupportedInputFormat)
{
	const TimeValue input = 0.0;
	EXPECT_THROW(
		{ (void)convert_time(input, static_cast<TimeFormat>(-1), TimeFormat::POSIX); },
		std::invalid_argument
	);
}

TEST(ConvertTimeDispFn, ShouldReturnChronoSysTimeForPosixInput)
{
	using namespace std::chrono;
	const double posix = 946728000.0; // 2000-01-01T12:00:00 UTC
	const TimeValue input = posix;
	const auto output = convert_time(input, TimeFormat::POSIX, TimeFormat::CHRONO_SYS_TIME_ISO);

	ASSERT_TRUE(std::holds_alternative<system_clock::time_point>(output));
	const auto tp = std::get<system_clock::time_point>(output);
	EXPECT_NEAR(std::chrono::duration<double>(tp.time_since_epoch()).count(), posix, 1.0e-9);
}

TEST(ConvertTimeDispFn, ChronoSysTimeRoundTripToPosix)
{
	using namespace std::chrono;
	const double posix = 98765.4321;
	const TimeValue input = posix;
	const auto chrono_out = convert_time(input, TimeFormat::POSIX, TimeFormat::CHRONO_SYS_TIME_ISO);
	ASSERT_TRUE(std::holds_alternative<system_clock::time_point>(chrono_out));
	const auto tp = std::get<system_clock::time_point>(chrono_out);

	// Convert back using existing handler for chrono -> posix via sys_time_to_utc_posix
	const auto back_posix = sys_time_to_utc_posix(tp);
	EXPECT_NEAR(back_posix, posix, 1.0e-9);
}
