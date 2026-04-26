#include "convert_time_tudat_disp_tbl.h"

#include <gtest/gtest.h>
#include <string>
#include <variant>

namespace
{
constexpr double kTol = 2.0e-4;
}

using namespace convert_time_tudat;

TEST(ConvertTimeTudatDispTbl, ShouldConvertUtcIsoToUtcPosix)
{
	const std::variant<std::string, double> input = std::string("2000-01-01T12:00:00");
	const auto output = convert_time(input, TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_POSIX);

	ASSERT_TRUE(std::holds_alternative<double>(output));
	EXPECT_NEAR(std::get<double>(output), 946728000.0, kTol);
}

TEST(ConvertTimeTudatDispTbl, ShouldConvertUtcPosixToUtcIso)
{
	const std::variant<std::string, double> input = 946728000.0;
	const auto output = convert_time(input, TimeFormat::UTC_POSIX, TimeFormat::UTC_ISO_TUDAT);

	ASSERT_TRUE(std::holds_alternative<std::string>(output));
	EXPECT_EQ(std::get<std::string>(output), "2000-01-01 12:00:00.000");
}

TEST(ConvertTimeTudatDispTbl, ShouldThrowBadVariantAccessWhenUtcIsoFormatButDoubleProvided)
{
	const std::variant<std::string, double> input = 946728000.0;
	EXPECT_THROW(
		{ (void)convert_time(input, TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_POSIX); },
		std::bad_variant_access
	);
}

TEST(ConvertTimeTudatDispTbl, ShouldThrowBadVariantAccessWhenNumericFormatButStringProvided)
{
	const std::variant<std::string, double> input = std::string("2000-01-01T12:00:00");
	EXPECT_THROW(
		{ (void)convert_time(input, TimeFormat::UTC_POSIX, TimeFormat::UTC_TUDAT); },
		std::bad_variant_access
	);
}

TEST(ConvertTimeTudatDispTbl, ShouldThrowInvalidArgumentForUnsupportedInputFormat)
{
	const std::variant<std::string, double> input = 0.0;
	EXPECT_THROW(
		{ (void)convert_time(input, static_cast<TimeFormat>(-1), TimeFormat::UTC_POSIX); },
		std::invalid_argument
	);
}
