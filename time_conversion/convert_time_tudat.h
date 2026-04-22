#pragma once

#include <tudat/astro/basic_astro/dateTime.h>
#include <tudat/astro/earth_orientation/terrestrialTimeScaleConverter.h>

std::shared_ptr<tudat::earth_orientation::TerrestrialTimeScaleConverter> get_tudat_time_scale_converter();
