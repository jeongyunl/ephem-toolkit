#include "convert_time.h"
#include "convert_time_disp_tmpl.h"
#include "test/convert_time_common_gtest.h"

#include <gtest/gtest.h>
#include <tudat/interface/spice/spiceInterface.h>

namespace
{
using convert_time_test::EpochRecord;

class ConvertTimeTemplateDataDrivenTest : public ::testing::Test
{
protected:
	static void SetUpTestSuite()
	{
		tudat::spice_interface::loadSpiceKernelInTudat(tudat::paths::getSpiceKernelPath() + "/naif0012.tls");
	}
};
} // namespace

TEST_F(ConvertTimeTemplateDataDrivenTest, TemplateConvertTimeIsoToPosixMatchesReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(
			(convert_time_tmpl<TimeFormat::UTC_ISO_TUDAT, TimeFormat::UTC_POSIX>(record.iso)),
			record.posix,
			convert_time_test::kTolExactLike
		) << record.iso;
	}
}

TEST_F(ConvertTimeTemplateDataDrivenTest, TemplateConvertTimePosixToUtcMatchesReferenceDataForNonLeapSeconds)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		EXPECT_NEAR(
			(convert_time_tmpl<TimeFormat::UTC_POSIX, TimeFormat::UTC_TUDAT>(record.posix)),
			record.utc,
			convert_time_test::kTolExactLike
		) << record.iso;
	}
}

TEST_F(ConvertTimeTemplateDataDrivenTest, TemplateConvertTimeUtcToTtMatchesReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		if(convert_time_test::is_leap_second_iso(record.iso))
		{
			continue;
		}

		EXPECT_NEAR(
			(convert_time_tmpl<TimeFormat::UTC_TUDAT, TimeFormat::TT_TUDAT>(record.utc)),
			record.tt,
			convert_time_test::kTolTimeScale
		) << record.iso;
	}
}

TEST_F(ConvertTimeTemplateDataDrivenTest, TemplateConvertTimeTaiToIsoRoundTripsBackToTai)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		// The ISO formatter used by the conversion utilities may:
		//  - include fractional seconds (e.g. ".000")
		//  - be unable to represent leap seconds (":60") and instead roll over to the next minute.
		// Therefore, validate correctness by round-tripping back to TAI.
		const std::string iso_from_tai =
			convert_time_tmpl<TimeFormat::TAI_TUDAT, TimeFormat::UTC_ISO_TUDAT>(record.tai);

		const double tai_round_trip =
			convert_time_tmpl<TimeFormat::UTC_ISO_TUDAT, TimeFormat::TAI_TUDAT>(iso_from_tai);

		EXPECT_NEAR(tai_round_trip, record.tai, convert_time_test::kTolTimeScale) << record.iso;
	}
}

TEST_F(ConvertTimeTemplateDataDrivenTest, TemplateConvertTimeTdbApproxToTdbMatchesReferenceData)
{
	for(const auto& record : convert_time_test::epoch_records())
	{
		EXPECT_NEAR(
			(convert_time_tmpl<TimeFormat::TDB_APX_TUDAT, TimeFormat::TDB_TUDAT>(record.tdb_apx)),
			record.tdb,
			convert_time_test::kTolTdb
		) << record.iso;
	}
}
