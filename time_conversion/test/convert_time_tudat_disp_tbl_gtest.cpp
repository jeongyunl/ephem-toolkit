#include "tudat/time_converter_tudat.h"

#include <gtest/gtest.h>
#include <string>
#include <variant>

namespace
{
constexpr double kTol = 2.0e-4;

class ConvertTimeTudatDispTbl : public ::testing::Test
{
protected:
	static void SetUpTestSuite() { TimeConverterTudat::instance().make_dispatch_table(); }
};

} // namespace

TEST_F(ConvertTimeTudatDispTbl, ShouldConvertUtcIsoToUtcPosix)
{
	const TimeValue input = std::string("2000-01-01T12:00:00");
	const auto output =
		TimeConverterTudat::instance().convert_time(input, TimeFormat::UTC_ISO8601, TimeFormat::POSIX);

	ASSERT_TRUE(std::holds_alternative<double>(output));
	EXPECT_NEAR(std::get<double>(output), 946728000.0, kTol);
}

TEST_F(ConvertTimeTudatDispTbl, ShouldConvertUtcPosixToUtcIso)
{
	const TimeValue input = 946728000.0;
	const auto output =
		TimeConverterTudat::instance().convert_time(input, TimeFormat::POSIX, TimeFormat::UTC_ISO8601);

	ASSERT_TRUE(std::holds_alternative<std::string>(output));
	EXPECT_EQ(std::get<std::string>(output), "2000-01-01 12:00:00.000");
}

TEST_F(ConvertTimeTudatDispTbl, ShouldThrowInvalidArgumentWhenUtcIsoFormatButDoubleProvided)
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

TEST_F(ConvertTimeTudatDispTbl, ShouldThrowInvalidArgumentWhenNumericFormatButStringProvided)
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

TEST_F(ConvertTimeTudatDispTbl, ShouldThrowInvalidArgumentForUnsupportedInputFormat)
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
