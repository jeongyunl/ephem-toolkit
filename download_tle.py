#!/usr/bin/env python3


import sys
import urllib.parse
import urllib.request


def main():
    if len(sys.argv) < 2:
        print("Usage: download_tle.py <satellite_id_1> <satellite_id_2> ...")
        sys.exit(1)

    satellite_ids = sys.argv[1:]
    print(f"Satellite IDs: {satellite_ids}\n")

    for satellite_id in satellite_ids:
        print(f"Downloading TLE for {satellite_id}")

        # Encode satellite ID for URL

        satellite_id = urllib.parse.quote(satellite_id, safe="*")

        url = f"https://celestrak.org/NORAD/elements/gp.php?INTDES={satellite_id}"

        try:

            # Download the TLE data into a variable
            tle_data = urllib.request.urlopen(url).read()
            # Read the first line of the TLE data
            tle_lines = tle_data.decode("utf-8").splitlines()
            # Check if the TLE data from celestrak has at least 3 lines (satellite name, line 1, line 2)
            if len(tle_lines) < 3:
                print(f"No TLE data found for {satellite_id}")
                continue

            # Retrieve the satellite name from the first line of the TLE data
            satellite_name = tle_lines[0].strip()
            # replace spaces in the satellite name with hyphens
            satellite_name = satellite_name.replace(" ", "-")

            # Save the TLE data to a file named after the satellite name
            with open(f"{satellite_name}_{satellite_id}.tle", "w") as f:
                # Write the second and third lines of the TLE data to the file
                f.write(tle_lines[1] + "\n")
                f.write(tle_lines[2] + "\n")
                f.close()

            print(f"Downloaded TLE for {satellite_name} ({satellite_id})")

            # Break the line after each TLE file
            print()

        except Exception as e:
            print(f"Error downloading TLE for {satellite_id}: {e}")


if __name__ == "__main__":
    main()
