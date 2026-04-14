#pragma once

#include <Eigen/Core>
#include <cspice/SpiceUsr.h>
#include <tudat/astro/basic_astro/celestialBodyConstants.h>
#include <tudat/astro/basic_astro/dateTime.h>
#include <tudat/interface/spice/spiceInterface.h>
#include <tudat/math/interpolators/createInterpolator.h>
#include <tudat/simulation/environment_setup/createAerodynamicCoefficientInterface.h>
#include <tudat/simulation/environment_setup/createBodies.h>
#include <tudat/simulation/environment_setup/createRadiationPressureTargetModel.h>
#include <tudat/simulation/environment_setup/createRotationModel.h>
#include <tudat/simulation/environment_setup/defaultBodies.h>
#include <tudat/simulation/simulation.h>
