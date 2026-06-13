#!/bin/sh

LINES="$1"
FILE="$2"

head -n $(( ${LINES} + 50 )) "${FILE}" | grep "^[0-9]" | head -n "${LINES}"
