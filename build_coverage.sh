#!/bin/sh

cmake -S . -B coverage -DBUILD_TESTING=ON -DENABLE_COVERAGE=ON &&
cmake --build coverage -j &&
cmake --build coverage --target coverage
