cmake_minimum_required(VERSION 3.27)
project(tudatpy-utils)
include(FetchContent)
include(CTest)

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

# dispatch table-based implementation
add_executable(convert_time convert_time_cli.cpp convert_time.cpp)
target_link_libraries(convert_time PUBLIC ${Tudat_PROPAGATION_LIBRARIES})

# convert_time() based implementation
add_executable(convert_time2 convert_time_cli2.cpp convert_time.cpp)
target_link_libraries(convert_time2 PUBLIC ${Tudat_PROPAGATION_LIBRARIES})

if(BUILD_TESTING)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
    )
    FetchContent_MakeAvailable(googletest)

    add_executable(
        convert_time_gtest
        test/convert_time_gtest.cpp
        convert_time.cpp
    )

    target_link_libraries(
        convert_time_gtest
        PRIVATE
        ${Tudat_PROPAGATION_LIBRARIES}
        GTest::gtest
        GTest::gtest_main
    )

    target_include_directories(
        convert_time_gtest
        BEFORE
        PRIVATE
        ${googletest_SOURCE_DIR}/googletest/include
        ${CMAKE_CURRENT_SOURCE_DIR}
    )

    target_compile_definitions(
        convert_time_gtest
        PRIVATE
        NOTABLE_EPOCHS_FILE="${CMAKE_CURRENT_SOURCE_DIR}/test/notable_epochs.dat"
    )

    include(GoogleTest)
    gtest_discover_tests(convert_time_gtest)
endif()
