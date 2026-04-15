cmake_minimum_required(VERSION 3.27)
project(tudatpy-utils)
find_package(tudat REQUIRED)
find_package(Eigen3 REQUIRED)
find_package(nrlmsise00)

include_directories(${EIGEN3_INCLUDE_DIRS})

# set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -ftime-report")
set(CMAKE_CXX_STANDARD 20)

add_compile_definitions(EIGEN_NO_DEBUG)
add_compile_options(
    -Wall
    -Wextra
    -Wunused
)

add_executable(convert_time convert_time_cli.cpp convert_time.cpp)
target_link_libraries(convert_time PUBLIC ${Tudat_PROPAGATION_LIBRARIES})
