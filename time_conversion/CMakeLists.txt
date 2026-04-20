add_library(convert_time STATIC convert_time.cpp convert_time_utc_iso.cpp)

target_include_directories(convert_time PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

target_link_libraries(convert_time PUBLIC ${Tudat_PROPAGATION_LIBRARIES})

add_executable(utc_conversion utc_conversion.cpp)

target_link_libraries(utc_conversion PRIVATE convert_time)

target_include_directories(utc_conversion PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(
    example_utc_iso8601_to_tai_zoneinfo
    example_utc_iso8601_to_tai_zoneinfo.cpp
)

target_include_directories(
    example_utc_iso8601_to_tai_zoneinfo PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(example_utc_iso8601_to_tai_zoneinfo PRIVATE convert_time)

add_executable(
    convert_time_disp_fn_cli ../convert_time_disp_fn_cli.cpp
                             convert_time_disp_tbl.cpp
)

target_include_directories(
    convert_time_disp_fn_cli PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(convert_time_disp_fn_cli PRIVATE convert_time)

if(BUILD_TESTING)
    add_executable(
        convert_time_gtest test/convert_time_gtest.cpp
                           test/convert_time_common_gtest.cpp
    )

    target_link_libraries(
        convert_time_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    add_executable(
        convert_time_tmpl_gtest test/convert_time_tmpl_gtest.cpp
                                test/convert_time_common_gtest.cpp
    )

    target_link_libraries(
        convert_time_tmpl_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_tmpl_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    add_executable(
        convert_time_disp_fn_gtest test/convert_time_disp_fn_gtest.cpp
                                   test/convert_time_common_gtest.cpp
    )

    target_link_libraries(
        convert_time_disp_fn_gtest
        PRIVATE convert_time
                GTest::gtest
                GTest::gtest_main
    )

    target_include_directories(
        convert_time_disp_fn_gtest BEFORE
        PRIVATE ${googletest_SOURCE_DIR}/googletest/include
                ${CMAKE_CURRENT_SOURCE_DIR}
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    include(GoogleTest)
    gtest_discover_tests(convert_time_gtest)
    gtest_discover_tests(convert_time_tmpl_gtest)
    gtest_discover_tests(convert_time_disp_fn_gtest)
endif()
