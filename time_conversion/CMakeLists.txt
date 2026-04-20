add_executable(utc_conversion utc_conversion.cpp utc_iso_to_x.cpp)

target_include_directories(utc_conversion PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(
    example_utc_iso8601_to_tai_zoneinfo example_utc_iso8601_to_tai_zoneinfo.cpp
                                        utc_iso_to_x.cpp
)

add_executable(
    convert_time_disp_fn_cli
    ../convert_time_disp_fn_cli.cpp
    convert_time_disp_tbl.cpp
    convert_time.cpp
)

target_include_directories(
    convert_time_disp_fn_cli PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}
)

target_link_libraries(
    convert_time_disp_fn_cli PUBLIC ${Tudat_PROPAGATION_LIBRARIES}
)

if(BUILD_TESTING)
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
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

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
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

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
                ${CMAKE_CURRENT_SOURCE_DIR}/..
    )

    include(GoogleTest)
    gtest_discover_tests(convert_time_gtest)
    gtest_discover_tests(convert_time_tmpl_gtest)
    gtest_discover_tests(convert_time_disp_fn_gtest)
endif()
