#!/bin/sh

#	ISS.OEM_J2K_EPH.txt.oem \

#../plotting/plot_orbits.py -d 2d -o plot_iss.png ISS.OEM_J2K_EPH.txt \
#	ISS.OEM_J2K_EPH.txt.txt

# Show usage if no argument is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <input_file>"
    echo ""
    echo "Arguments:"
    echo "  <input_file>  Path to the OEM input file (e.g., ISS.OEM_J2K_EPH.txt)"
    echo ""
    echo "Example:"
    echo "  $0 ISS.OEM_J2K_EPH.txt"
    exit 1
fi

INPUT_FILE="$1"

../plotting/plot_orbits.py -d 2d "${INPUT_FILE}" \
	"${INPUT_FILE}".oem "${INPUT_FILE}".txt
