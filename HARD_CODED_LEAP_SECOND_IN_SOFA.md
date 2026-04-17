
Tudat's TerrestrialTimeScaleConverter largely rely on SOFA library for time conversions.
SOFA's iauDat() which calculates Delta(AT) = TAI-UTC for a given UTC date has leap seconds hard-coded.


Call graph (incomplete)
iauDat()
    tudat::sofa_interface::getDeltaAtFromUtc()
        tudat::sofa_interface::convertTAItoUTC()
            tudat::earth_orientation::TerrestrialTimeScaleConverter::calculateUniversalTimes()
                tudat::earth_orientation::TerrestrialTimeScaleConverter::updateTimes()
                    tudat::earth_orientation::TerrestrialTimeScaleConverter::getCurrentTime()
            tudat::sofa_interface::getTDBminusTT()
        tudat::sofa_interface::convertUTCtoTAI()
            tudat::earth_orientation::TerrestrialTimeScaleConverter::updateTimes()
            tudat::earth_orientation::TerrestrialTimeScaleConverter::calculateAtomicTimesFromUtc()
            tudat::sofa_interface::convertUTCtoTT()
    tudat::sofa_interface::getDeltaAtFromTai()

Solution?