#!/bin/sh -x

convert_time_py=../time_conversion/tools/convert_time.py

echo posix
$convert_time_py -i posix -o iso,posix,utc,tai,tt,tdb 0.000 946728000.000 946727968.000 946727935.816

echo j200
$convert_time_py -i utc -o iso,posix,utc,tai,tt,tdb 0.000 -32.000 -64.184

echo tai
$convert_time_py -i tai -o iso,posix,utc,tai,tt,tdb 32.000 0.000 -32.184

echo tt
$convert_time_py -i tt -o iso,posix,utc,tai,tt,tdb 64.184 32.184 0.000

echo tdb
$convert_time_py -i tdb -o iso,posix,utc,tai,tt,tdb 64.184 32.184 0.000

echo tdb_apx
$convert_time_py -i tdb_apx -o iso,posix,utc,tai,tt,tdb 64.184 32.184 0.000
