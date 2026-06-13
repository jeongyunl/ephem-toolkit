#!/bin/sh

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

head -n 50 "$INPUT_FILE" | grep "^[0-9]" | head -n 1 | ../propagation/propagate_satellite_orbit.py --name "ISS_prop" \
	--oem ${INPUT_FILE}.oem --oem-step-size 10m \
	--raw ${INPUT_FILE}.txt \
	--dep-vars ${INPUT_FILE}.csv \
	--mass 482701 --drag on --drag-area 1525.09 --drag-coeff 1.75 --srp off --duration 4d
