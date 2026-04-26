#include "convert_time_epochs.h"

#include <gtest/gtest.h>

using namespace std::chrono;
const std::chrono::sys_time<std::chrono::system_clock::duration> utc_j2000_epoch = {
	sys_days{ 2000y / January / 1 } + hours{ 12 }
};

TEST(ConvertTimeEpochs, Iso8601LabelsMatchExpected)
{
	EXPECT_STREQ(
		epochs::UTC_J2000_EPOCH_IN_ISO8601,
		std::format("{:%FT%T}", epochs::UTC_J2000_EPOCH_IN_SYS_TIME<std::chrono::seconds>).c_str()
	);
	EXPECT_STREQ(
		epochs::TAI_J2000_EPOCH_IN_ISO8601,
		std::format("{:%FT%T}", epochs::TAI_J2000_EPOCH_IN_SYS_TIME<std::chrono::seconds>).c_str()
	);
	EXPECT_STREQ(
		epochs::TT_J2000_EPOCH_IN_ISO8601,
		std::format("{:%FT%T}", epochs::TT_J2000_EPOCH_IN_SYS_TIME<std::chrono::milliseconds>).c_str()
	);
	EXPECT_STREQ(
		epochs::POSIX_EPOCH_IN_ISO8601,
		std::format("{:%FT%T}", epochs::POSIX_EPOCH_IN_SYS_TIME<std::chrono::seconds>).c_str()
	);
	EXPECT_STREQ(
		epochs::UTC_1972_EPOCH_IN_ISO8601,
		std::format("{:%FT%T}", epochs::UTC_1972_EPOCH_IN_SYS_TIME<std::chrono::seconds>).c_str()
	);

	EXPECT_EQ(utc_j2000_epoch, epochs::UTC_J2000_EPOCH_IN_SYS_TIME<std::chrono::system_clock::duration>);
}

TEST(ConvertTimeEpochs, PosixEpochConstantsAreConsistent)
{
	const std::int64_t expected_utc_j2000_posix =
		calendar_date_to_posix_days(2000, 1, 1) * SECONDS_PER_DAY + 12 * SECONDS_PER_HOUR;
	const std::int64_t expected_tai_j2000_posix = calendar_date_to_posix_days(2000, 1, 1) * SECONDS_PER_DAY
		+ 11 * SECONDS_PER_HOUR + 59 * SECONDS_PER_MINUTE + 28;
	const double expected_tt_j2000_posix =
		calendar_date_to_posix_days(2000, 1, 1) * static_cast<double>(SECONDS_PER_DAY)
		+ 11.0 * static_cast<double>(SECONDS_PER_HOUR) + 58.0 * static_cast<double>(SECONDS_PER_MINUTE)
		+ 55.816;

	EXPECT_EQ(
		epochs::UTC_J2000_EPOCH_IN_SYS_TIME<std::chrono::seconds>.time_since_epoch().count(),
		expected_utc_j2000_posix
	);

	EXPECT_EQ(
		epochs::TAI_J2000_EPOCH_IN_SYS_TIME<std::chrono::seconds>.time_since_epoch().count(),
		expected_tai_j2000_posix
	);

	EXPECT_NEAR(
		epochs::TT_J2000_EPOCH_IN_SYS_TIME<std::chrono::duration<double>>.time_since_epoch().count(),
		expected_tt_j2000_posix,
		1.0e-6
	);

	EXPECT_EQ(
		epochs::UTC_1972_EPOCH_IN_SYS_TIME<std::chrono::seconds>.time_since_epoch().count(),
		epochs::UTC_1972_EPOCH_IN_POSIX_TIME
	);

	EXPECT_EQ(epochs::UTC_J2000_EPOCH_IN_POSIX_TIME, expected_utc_j2000_posix);
	EXPECT_EQ(epochs::TAI_J2000_EPOCH_IN_POSIX_TIME, expected_tai_j2000_posix);
	EXPECT_DOUBLE_EQ(epochs::TT_J2000_EPOCH_IN_POSIX_TIME, expected_tt_j2000_posix);
	EXPECT_EQ(
		epochs::UTC_J2000_EPOCH_IN_POSIX_TIME - epochs::TAI_J2000_EPOCH_IN_POSIX_TIME,
		static_cast<std::int64_t>(TAI_MINUS_UTC_AT_J2000)
	);
	EXPECT_NEAR(
		static_cast<double>(epochs::TAI_J2000_EPOCH_IN_POSIX_TIME) - epochs::TT_J2000_EPOCH_IN_POSIX_TIME,
		TT_MINUS_TAI,
		1.0e-6
	);
}

TEST(ConvertTimeEpochs, J2000OffsetConstantsAreConsistent)
{
	EXPECT_EQ(epochs::UTC_J2000_EPOCH_IN_TAI_J2000_TIME, static_cast<std::int64_t>(TAI_MINUS_UTC_AT_J2000));
	EXPECT_DOUBLE_EQ(epochs::UTC_J2000_EPOCH_IN_TT_J2000_TIME, TAI_MINUS_UTC_AT_J2000 + TT_MINUS_TAI);

	EXPECT_DOUBLE_EQ(epochs::TAI_J2000_EPOCH_IN_UTC_J2000_TIME, -TAI_MINUS_UTC_AT_J2000);
	EXPECT_DOUBLE_EQ(epochs::TAI_J2000_EPOCH_IN_TT_J2000_TIME, TT_MINUS_TAI);

	EXPECT_DOUBLE_EQ(epochs::TT_J2000_EPOCH_IN_UTC_J2000_TIME, -TAI_MINUS_UTC_AT_J2000 - TT_MINUS_TAI);
	EXPECT_DOUBLE_EQ(epochs::TT_J2000_EPOCH_IN_TAI_J2000_TIME, -TT_MINUS_TAI);
}

TEST(ConvertTimeEpochs, PosixEpochOffsetsAreConsistent)
{
	EXPECT_EQ(epochs::POSIX_EPOCH_IN_UTC_J2000_TIME, -epochs::UTC_J2000_EPOCH_IN_POSIX_TIME);
	EXPECT_DOUBLE_EQ(
		epochs::POSIX_EPOCH_IN_TAI_J2000_TIME,
		-static_cast<double>(epochs::UTC_J2000_EPOCH_IN_POSIX_TIME)
			+ static_cast<std::int64_t>(TAI_MINUS_UTC_AT_1970)
	);
	EXPECT_DOUBLE_EQ(
		epochs::POSIX_EPOCH_IN_TT_J2000_TIME,
		epochs::POSIX_EPOCH_IN_TAI_J2000_TIME + TT_MINUS_TAI
	);
}

TEST(ConvertTimeEpochs, Utc1972EpochMatchesCalendarComputation)
{
	const std::int64_t expected_utc_1972_posix = calendar_date_to_posix_days(1972, 1, 1) * SECONDS_PER_DAY;
	EXPECT_EQ(epochs::UTC_1972_EPOCH_IN_POSIX_TIME, expected_utc_1972_posix);
}
