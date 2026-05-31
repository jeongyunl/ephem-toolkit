#!/usr/bin/env python3

import argparse
import os
import subprocess
import shlex
import sys


def compute_tle_checksum(line_without_checksum):
    checksum = 0
    for char in line_without_checksum:
        if char.isdigit():
            checksum += int(char)
        elif char == "-":
            checksum += 1
    return str(checksum % 10)


def parse_tle_input(stdin_text):
    lines = [line.rstrip("\n") for line in stdin_text.splitlines() if line.strip()]
    if len(lines) < 2:
        raise ValueError("Expected at least 2 non-empty lines from stdin")

    if lines[0].startswith("1 ") and lines[1].startswith("2 "):
        name = ""
        line1 = lines[0]
        line2 = lines[1]
    elif len(lines) >= 3 and lines[1].startswith("1 ") and lines[2].startswith("2 "):
        name = lines[0]
        line1 = lines[1]
        line2 = lines[2]
    else:
        raise ValueError(
            "Could not identify TLE lines. Expected either '<line1> <line2>' or '<name> <line1> <line2>'"
        )

    if len(line1) < 69 or len(line2) < 69:
        raise ValueError("TLE lines must be at least 69 characters long")

    line1 = line1[:69]
    line2 = line2[:69]
    return name, line1, line2


def parse_tle_elements(line1, line2):
    if line1[0] != "1" or line2[0] != "2":
        raise ValueError("Invalid line numbers in TLE")

    data = {
        "satellite_number": int(line1[2:7]),
        "classification": line1[7],
        "int_designator_year": int(line1[9:11]),
        "int_designator_launch_number": int(line1[11:14]),
        "int_designator_piece": line1[14:17].strip(),
        "epoch_year": int(line1[18:20]),
        "epoch_day": float(line1[20:32]),
        "mean_motion_first_derivative": float(line1[33:43]),
        "mean_motion_second_derivative": line1[44:52].strip(),
        "bstar": line1[53:61].strip(),
        "ephemeris_type": int(line1[62]),
        "element_set_number": int(line1[64:68]),
        "line1_checksum": line1[68],
        "line1_checksum_expected": compute_tle_checksum(line1[:68]),
        "inclination_deg": float(line2[8:16]),
        "raan_deg": float(line2[17:25]),
        "eccentricity_raw": line2[26:33],
        "arg_perigee_deg": float(line2[34:42]),
        "mean_anomaly_deg": float(line2[43:51]),
        "mean_motion_rev_per_day": float(line2[52:63]),
        "revolution_number_at_epoch": int(line2[63:68]),
        "line2_checksum": line2[68],
        "line2_checksum_expected": compute_tle_checksum(line2[:68]),
    }
    data["eccentricity"] = float(f"0.{data['eccentricity_raw']}")
    return data


def make_reconstruction_command_parts(elements, output_path, name, write_tle_script):
    command_parts = [
        "python3",
        write_tle_script,
        "--output",
        output_path,
        "--satellite-number",
        str(elements["satellite_number"]),
        "--classification",
        elements["classification"],
        "--int-designator-year",
        str(elements["int_designator_year"]),
        "--int-designator-launch-number",
        str(elements["int_designator_launch_number"]),
        "--int-designator-piece",
        elements["int_designator_piece"] or "A",
        "--epoch-year",
        str(elements["epoch_year"]),
        "--epoch-day",
        f"{elements['epoch_day']:.8f}",
        "--mean-motion-first-derivative",
        f"{elements['mean_motion_first_derivative']:.8f}",
        "--mean-motion-second-derivative",
        elements["mean_motion_second_derivative"],
        "--bstar",
        elements["bstar"],
        "--ephemeris-type",
        str(elements["ephemeris_type"]),
        "--element-set-number",
        str(elements["element_set_number"]),
        "--inclination-deg",
        f"{elements['inclination_deg']:.4f}",
        "--raan-deg",
        f"{elements['raan_deg']:.4f}",
        "--eccentricity",
        f"0.{elements['eccentricity_raw']}",
        "--arg-perigee-deg",
        f"{elements['arg_perigee_deg']:.4f}",
        "--mean-anomaly-deg",
        f"{elements['mean_anomaly_deg']:.4f}",
        "--mean-motion-rev-per-day",
        f"{elements['mean_motion_rev_per_day']:.8f}",
        "--revolution-number-at-epoch",
        str(elements["revolution_number_at_epoch"]),
    ]

    if name:
        command_parts.extend(["--name", name])

    return command_parts


def make_reconstruction_command(command_parts):
    return " ".join(shlex.quote(part) for part in command_parts)


def print_summary(name, line1, line2, elements):
    print("Parsed TLE summary:")
    print(f"  name: {name if name else '(none)'}")
    print("  source lines:")
    print(f"    line1: {line1}")
    print(f"    line2: {line2}")
    print("  line 1 elements:")
    print(f"    satellite-number: {elements['satellite_number']}")
    print(f"    classification: {elements['classification']}")
    print(f"    int-designator-year: {elements['int_designator_year']}")
    print(
        f"    int-designator-launch-number: {elements['int_designator_launch_number']}"
    )
    print(f"    int-designator-piece: {elements['int_designator_piece']}")
    print(f"    epoch-year: {elements['epoch_year']}")
    print(f"    epoch-day: {elements['epoch_day']:.8f}")
    print(
        f"    mean-motion-first-derivative: {elements['mean_motion_first_derivative']:.8f}"
    )
    print(
        f"    mean-motion-second-derivative: {elements['mean_motion_second_derivative']}"
    )
    print(f"    bstar: {elements['bstar']}")
    print(f"    ephemeris-type: {elements['ephemeris_type']}")
    print(f"    element-set-number: {elements['element_set_number']}")
    print("  line 2 elements:")
    print(f"    inclination-deg: {elements['inclination_deg']:.4f}")
    print(f"    raan-deg: {elements['raan_deg']:.4f}")
    print(f"    eccentricity: 0.{elements['eccentricity_raw']}")
    print(f"    arg-perigee-deg: {elements['arg_perigee_deg']:.4f}")
    print(f"    mean-anomaly-deg: {elements['mean_anomaly_deg']:.4f}")
    print(f"    mean-motion-rev-per-day: {elements['mean_motion_rev_per_day']:.8f}")
    print(f"    revolution-number-at-epoch: {elements['revolution_number_at_epoch']}")
    print("  checksum:")
    print(
        f"    line1: source={elements['line1_checksum']} expected={elements['line1_checksum_expected']}"
    )
    print(
        f"    line2: source={elements['line2_checksum']} expected={elements['line2_checksum_expected']}"
    )
    print()


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Parse a Two-Line Element (TLE) set from a file path or stdin, print a "
            "full element summary, and generate the equivalent write_tle.py command."
        )
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        metavar="<input.tle>",
        help=(
            "Input TLE file path. Use '-' or omit this argument to read TLE text "
            "from stdin (default: '-')."
        ),
    )
    parser.add_argument(
        "--output",
        metavar="<file>",
        default="reconstructed.tle",
        help=(
            "Output file path inserted into the generated write_tle.py command "
            "(default: reconstructed.tle)."
        ),
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help=(
            "Run the generated write_tle.py command and verify the rebuilt TLE text "
            "is identical to the parsed source."
        ),
    )
    return parser.parse_args()


def get_write_tle_script_paths():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    abs_path = os.path.join(script_dir, "write_tle.py")
    display_path = os.path.relpath(abs_path, os.getcwd())
    return display_path, abs_path


def build_source_tle_text(name, line1, line2):
    source_text = ""
    if name:
        source_text += name + "\n"
    source_text += line1 + "\n"
    source_text += line2 + "\n"
    return source_text


def verify_reconstruction(command_parts, output_path, name, line1, line2):
    process = subprocess.run(command_parts, capture_output=True, text=True)
    if process.returncode != 0:
        print("Verification failed: generated write_tle.py command returned non-zero")
        if process.stdout.strip():
            print("write_tle.py stdout:")
            print(process.stdout.rstrip())
        if process.stderr.strip():
            print("write_tle.py stderr:")
            print(process.stderr.rstrip())
        return False

    try:
        with open(output_path, "r") as rebuilt_file:
            rebuilt_text = rebuilt_file.read()
    except OSError as error:
        print(
            f"Verification failed: could not read output file '{output_path}': {error}"
        )
        return False

    source_text = build_source_tle_text(name, line1, line2)
    if rebuilt_text == source_text:
        print("Verification: PASS (rebuilt TLE is identical to parsed source)")
        return True

    print("Verification: FAIL (rebuilt TLE differs from parsed source)")

    source_lines = source_text.splitlines()
    rebuilt_lines = rebuilt_text.splitlines()
    min_len = min(len(source_lines), len(rebuilt_lines))
    for line_index in range(min_len):
        if source_lines[line_index] != rebuilt_lines[line_index]:
            print(f"  first differing line: {line_index + 1}")
            print(f"  source:  {source_lines[line_index]}")
            print(f"  rebuilt: {rebuilt_lines[line_index]}")
            return False

    if len(source_lines) != len(rebuilt_lines):
        print(
            f"  line count differs: source={len(source_lines)} rebuilt={len(rebuilt_lines)}"
        )

    return False


def main():
    args = parse_arguments()
    if args.input == "-":
        input_text = sys.stdin.read()
        if not input_text.strip():
            print("Error: no input from stdin")
            sys.exit(1)
    else:
        try:
            with open(args.input, "r") as input_file:
                input_text = input_file.read()
        except OSError as error:
            print(f"Error: could not read input file '{args.input}': {error}")
            sys.exit(1)

        if not input_text.strip():
            print(f"Error: input file '{args.input}' is empty")
            sys.exit(1)

    try:
        name, line1, line2 = parse_tle_input(input_text)
        elements = parse_tle_elements(line1, line2)
    except ValueError as error:
        print(f"Error: {error}")
        sys.exit(1)

    print_summary(name, line1, line2, elements)

    write_tle_display_path, write_tle_abs_path = get_write_tle_script_paths()
    command_parts_display = make_reconstruction_command_parts(
        elements, args.output, name, write_tle_display_path
    )
    command = make_reconstruction_command(command_parts_display)
    print("write_tle.py command to reproduce identical TLE:")
    print(command)

    if args.verify:
        command_parts_verify = make_reconstruction_command_parts(
            elements, args.output, name, write_tle_abs_path
        )
        ok = verify_reconstruction(
            command_parts_verify, args.output, name, line1, line2
        )
        if not ok:
            sys.exit(2)


if __name__ == "__main__":
    main()
