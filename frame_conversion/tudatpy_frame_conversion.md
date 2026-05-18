
## Rotation Matrix
* `tudatpy.astro.element_conversion.teme_to_j2000(epoch: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 3]]`
* `tudatpy.astro.element_conversion.j2000_to_teme(epoch: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 3]]`
* `tudatpy.dynamics.environment.AerodynamicAngleCalculator.get_rotation_matrix_between_frames(self: tudatpy.kernel.dynamics.environment.AerodynamicAngleCalculator, original_frame: tudat::reference_frames::AerodynamicsReferenceFrames, target_frame: tudat::reference_frames::AerodynamicsReferenceFrames) → numpy.ndarray[numpy.float64[3, 3]]`
* `tudatpy.dynamics.environment.RotationalEphemeris.body_fixed_to_inertial_rotation(self: tudatpy.kernel.dynamics.environment.RotationalEphemeris, time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 3]]`
* `tudatpy.dynamics.environment.RotationalEphemeris.inertial_to_body_fixed_rotation(self: tudatpy.kernel.dynamics.environment.RotationalEphemeris, time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 3]]`
* `tudatpy.dynamics.environment.GroundStationState.rotation_matrix_body_fixed_to_topocentric`
* `tudatpy.dynamics.environment.Body.inertial_to_body_fixed_frame`
* `tudatpy.dynamics.environment.Body.body_fixed_to_inertial_frame`
* `tudatpy.dynamics.environment.Body.inertial_to_body_fixed_frame_derivative`
* `tudatpy.dynamics.environment.Body.body_fixed_to_inertial_frame_derivative`
* `tudatpy.interface.spice.compute_rotation_matrix_between_frames(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 3]]`
* `tudatpy.interface.spice.compute_rotation_quaternion_and_rotation_matrix_derivative_between_frames(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → tuple[Eigen::Quaternion<double, 0>, numpy.ndarray[numpy.float64[3, 3]]]`

## Derivative of Rotation Matrix
* `tudatpy.dynamics.environment.RotationalEphemeris.time_derivative_body_fixed_to_inertial_rotation(self: tudatpy.kernel.dynamics.environment.RotationalEphemeris, time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 3]]`
* `tudatpy.dynamics.environment.RotationalEphemeris.time_derivative_inertial_to_body_fixed_rotation(self: tudatpy.kernel.dynamics.environment.RotationalEphemeris, time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 3]]`
* `tudatpy.dynamics.environment.Body.inertial_to_body_fixed_frame_derivative`
* `tudatpy.dynamics.environment.Body.body_fixed_to_inertial_frame_derivative`
* `tudatpy.interface.spice.compute_rotation_matrix_derivative_between_frames(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 3]]`
* `tudatpy.interface.spice.compute_rotation_quaternion_and_rotation_matrix_derivative_between_frames(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → tuple[Eigen::Quaternion<double, 0>, numpy.ndarray[numpy.float64[3, 3]]]`

## Angular/Rotational Velocity
* `tudatpy.dynamics.environment.RotationalEphemeris.angular_velocity_in_body_fixed_frame(self: tudatpy.kernel.dynamics.environment.RotationalEphemeris, time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 1]]`
* `tudatpy.dynamics.environment.RotationalEphemeris.angular_velocity_in_inertial_frame(self: tudatpy.kernel.dynamics.environment.RotationalEphemeris, time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 1]]`
* `tudatpy.dynamics.environment.Body.inertial_angular_velocity`
* `tudatpy.dynamics.environment.Body.body_fixed_angular_velocity`
* `tudatpy.interface.spice.get_angular_velocity_vector_of_frame_in_original_frame(original_frame: str, new_frame: str, ephemeris_time: float | SupportsIndex) → numpy.ndarray[numpy.float64[3, 1]]`






