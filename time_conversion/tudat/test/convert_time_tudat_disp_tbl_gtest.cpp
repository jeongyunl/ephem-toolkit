#include "time_converter_tudat.h"

#include <gtest/gtest.h>
#include <string>
#include <variant>

namespace
{
constexpr double kTol = 2.0e-4;
}

TEST(ConvertTimeTudatDispTbl, ShouldConvertUtcIsoToUtcPosix)
{
	const TimeValue input = std::string("2000-01-01T12:00:00");
	const auto output =
		TimeConverterTudat::instance().convert_time(input, TimeFormat::UTC_ISO8601, TimeFormat::POSIX);

	ASSERT_TRUE(std::holds_alternative<double>(output));
	EXPECT_NEAR(std::get<double>(output), 946728000.0, kTol);
}

TEST(ConvertTimeTudatDispTbl, ShouldConvertUtcPosixToUtcIso)
{
	const TimeValue input = 946728000.0;
	const auto output =
		TimeConverterTudat::instance().convert_time(input, TimeFormat::POSIX, TimeFormat::UTC_ISO8601);

	ASSERT_TRUE(std::holds_alternative<std::string>(output));
	EXPECT_EQ(std::get<std::string>(output), "2000-01-01 12:00:00.000");
}

TEST(ConvertTimeTudatDispTbl, ShouldThrowInvalidArgumentWhenUtcIsoFormatButDoubleProvided)
{
	const TimeValue input = 946728000.0;
	EXPECT_THROW(
		{
			(void)TimeConverterTudat::instance()
				.convert_time(input, TimeFormat::UTC_ISO8601, TimeFormat::POSIX);
		},
		std::invalid_argument
	);
}

TEST(ConvertTimeTudatDispTbl, ShouldThrowInvalidArgumentWhenNumericFormatButStringProvided)
{
	const TimeValue input = std::string("2000-01-01T12:00:00");
	EXPECT_THROW(
		{
			(void)TimeConverterTudat::instance()
				.convert_time(input, TimeFormat::POSIX, TimeFormat::UTC_J2000);
		},
		std::invalid_argument
	);
}

TEST(ConvertTimeTudatDispTbl, ShouldThrowInvalidArgumentForUnsupportedInputFormat)
{
	const TimeValue input = 0.0;
	EXPECT_THROW(
		{
			(void)TimeConverterTudat::instance()
				.convert_time(input, static_cast<TimeFormat>(-1), TimeFormat::POSIX);
		},
		std::invalid_argument
	);
}
