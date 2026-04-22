#include "convert_time_tudat.h"

std::shared_ptr<tudat::earth_orientation::TerrestrialTimeScaleConverter> get_tudat_time_scale_converter()
{
	static std::shared_ptr<tudat::earth_orientation::TerrestrialTimeScaleConverter>
		tudat_time_scale_converter = nullptr;

	if(tudat_time_scale_converter != nullptr)
	{
		return tudat_time_scale_converter;
	}

	tudat_time_scale_converter = tudat::earth_orientation::createDefaultTimeConverter();

	return tudat_time_scale_converter;
}
