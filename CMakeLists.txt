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
add_compile_definitions(
    NOTABLE_EPOCHS_FILE="${CMAKE_CURRENT_SOURCE_DIR}/test/notable_epochs.dat"
)
add_compile_options(
    -Wall
    -Wextra
    -Wunused
)

# dispatch table-based implementation add_executable( convert_time_disp_tbl_cli
# convert_time_disp_tbl_cli.cpp convert_time.cpp ) target_link_libraries(
# convert_time_disp_tbl_cli PUBLIC ${Tudat_PROPAGATION_LIBRARIES} )

# convert_time() based implementation
add_executable(
    convert_time_disp_fn_cli
    convert_time_disp_fn_cli.cpp
    convert_time_disp_tbl.cpp
    convert_time.cpp
)
target_link_libraries(
    convert_time_disp_fn_cli PUBLIC ${Tudat_PROPAGATION_LIBRARIES}
)

if(BUILD_TESTING)
    FetchContent_Declare(
        googletest
        URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
    )
    FetchContent_MakeAvailable(googletest)

    #
    # convert_time_gtest
    #

    add_executable(
        convert_time_gtest
        test/convert_time_gtest.cpp
        test/convert_time_common_gtest.cpp
        convert_time.cpp
    )

    target_link_libraries(
        convert_time_gtest
        PRIVATE ${Tudat_PROPAGATION_LIBRARIES}
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
    )

    #
    # convert_time_tmpl_gtest
    #

    add_executable(
        convert_time_tmpl_gtest
        test/convert_time_tmpl_gtest.cpp
        test/convert_time_common_gtest.cpp
        convert_time.cpp
    )

    target_link_libraries(
        convert_time_tmpl_gtest
        PRIVATE ${Tudat_PROPAGATION_LIBRARIES}
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_tmpl_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
    )

    #
    # convert_time_disp_fn_gtest
    #

    add_executable(
        convert_time_disp_fn_gtest
        test/convert_time_disp_fn_gtest.cpp
        test/convert_time_common_gtest.cpp
        convert_time.cpp
    )

    target_link_libraries(
        convert_time_disp_fn_gtest
        PRIVATE ${Tudat_PROPAGATION_LIBRARIES}
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_disp_fn_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
    )

    #

    include(GoogleTest)
    gtest_discover_tests(convert_time_gtest)
    gtest_discover_tests(convert_time_tmpl_gtest)
    gtest_discover_tests(convert_time_disp_fn_gtest)
endif()
