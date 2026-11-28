#!/usr/bin/env bash
set -euo pipefail

ANALYSIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(git -C "$ANALYSIS_DIR" rev-parse --show-toplevel)"
cd "$ROOT"

OEM="tests/data/ISS_2026-05-20.OEM"
SCENARIO="$ANALYSIS_DIR/scenario-recorded.json"
OUTPUT="$ANALYSIS_DIR/play-oem-data-baseline.prof"
REPEATS=3

usage() {
  cat <<'EOF'
Usage: profile_oem_data_paths.sh [options]

Options:
  --oem PATH        OEM input
  --scenario PATH   JSON range scenario
  --repeats COUNT   Unprofiled median repeat count
  --output PATH     cProfile output
  -h, --help        Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --oem) OEM="$2"; shift 2 ;;
    --scenario) SCENARIO="$2"; shift 2 ;;
    --repeats) REPEATS="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for path in "$OEM" "$SCENARIO"; do
  [[ -f "$path" ]] || { echo "Missing required file: $path" >&2; exit 2; }
done
[[ -x ".venv/bin/python" ]] || { echo "Missing executable: .venv/bin/python" >&2; exit 2; }

summary="${OUTPUT%.prof}.txt"
.venv/bin/python "$ANALYSIS_DIR/profile_oem_data_paths.py" \
  --oem "$OEM" \
  --scenario "$SCENARIO" \
  --repeats "$REPEATS" \
  --profile "$OUTPUT" \
  --summary "$summary"

printf 'Profile: %s\n' "$OUTPUT"
printf 'Summary: %s\n' "$summary"
