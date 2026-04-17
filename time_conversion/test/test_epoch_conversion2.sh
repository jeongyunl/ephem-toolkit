#!/bin/sh -x

echo posix
../../convert_time2.py -i posix -o iso,posix,utc,tai,tt,tdb,tdb_apx 0.000 946728000.000 946727968.000 946727935.816

echo j200
../../convert_time2.py -i utc -o iso,posix,utc,tai,tt,tdb,tdb_apx 0.000 -32.000 -64.184

echo tai
../../convert_time2.py -i tai -o iso,posix,utc,tai,tt,tdb,tdb_apx 32.000 0.000 -32.184

echo tt
../../convert_time2.py -i tt -o iso,posix,utc,tai,tt,tdb,tdb_apx 64.184 32.184 0.000

echo tdb
../../convert_time2.py -i tdb -o iso,posix,utc,tai,tt,tdb,tdb_apx 64.184 32.184 0.000

echo tdb_apx
../../convert_time2.py -i tdb_apx -o iso,posix,utc,tai,tt,tdb,tdb_apx 64.184 32.184 0.000

