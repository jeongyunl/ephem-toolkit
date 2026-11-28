#!/usr/bin/env bash
set -euo pipefail

ANALYSIS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(git -C "$ANALYSIS_DIR" rev-parse --show-toplevel)"
cd "$ROOT"

OEM="tests/data/ISS_2026-05-20.OEM"
SCENARIO="$ANALYSIS_DIR/scenario-recorded.json"
CONFIG="$ANALYSIS_DIR/play-oem.toml"
STATE="$ANALYSIS_DIR/play-oem-state.toml"
OUTPUT="$ANALYSIS_DIR/play-oem-restart.prof"

usage() {
  cat <<'EOF'
Usage: profile_play_oem_ui.sh [options]

Options:
  --oem PATH       OEM input (default: tests/data/ISS_2026-05-20.OEM)
  --scenario PATH  JSON range scenario
  --config PATH    User config TOML copy
  --state PATH     Saved-state TOML copy
  --output PATH    cProfile output
  -h, --help       Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --oem) OEM="$2"; shift 2 ;;
    --scenario) SCENARIO="$2"; shift 2 ;;
    --config) CONFIG="$2"; shift 2 ;;
    --state) STATE="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

for path in "$OEM" "$SCENARIO" "$CONFIG" "$STATE"; do
  [[ -f "$path" ]] || { echo "Missing required file: $path" >&2; exit 2; }
done
[[ -x ".venv/bin/python" ]] || { echo "Missing executable: .venv/bin/python" >&2; exit 2; }

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ephem-play-oem-profile.XXXXXX")"
trap 'rm -rf "$tmpdir"' EXIT
cp "$CONFIG" "$tmpdir/play-oem.toml"
cp "$STATE" "$tmpdir/play-oem-state.toml"

.venv/bin/python -m cProfile -o "$OUTPUT" "$ANALYSIS_DIR/profile_play_oem_ui.py" \
  "$OEM" \
  --scenario "$SCENARIO" \
  --config-file "$tmpdir/play-oem.toml" \
  --state-file "$tmpdir/play-oem-state.toml"

summary="${OUTPUT%.prof}.txt"
.venv/bin/python - "$OUTPUT" "$summary" <<'PY'
import pstats
import sys

profile, summary = sys.argv[1:]
with open(summary, "w", encoding="utf-8") as stream:
    stats = pstats.Stats(profile, stream=stream)
    stats.strip_dirs().sort_stats("cumtime").print_stats(35)
print(f"Profile: {profile}")
print(f"Summary: {summary}")
PY
