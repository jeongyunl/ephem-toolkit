#!/bin/sh

echo j200
../convert_time2.py -i j2000 -o iso j2000 tai tt tdb -t 0.000 -32.000 -64.184

echo tai
../convert_time2.py -i tai -o iso j2000 tai tt tdb -t 32.000 0.000 -32.184

echo tt
../convert_time2.py -i tt -o iso j2000 tai tt tdb -t 64.184 32.184 0.000

echo tdb
../convert_time2.py -i tdb -o iso j2000 tai tt tdb -t 64.184 32.184 0.000

