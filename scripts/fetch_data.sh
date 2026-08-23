#!/usr/bin/env bash
# fetch_data.sh — re-downloads all raw data (never stored in git/workspace).
# Usage:
#   ./scripts/fetch_data.sh ibtracs                 # best-track labels (27 MB)
#   ./scripts/fetch_data.sh hursat 2013 PHAILIN     # one storm's satellite imagery
set -euo pipefail
mkdir -p data/raw
case "${1:-}" in
  ibtracs)
    curl -sSo data/raw/ibtracs.NI.list.v04r01.csv \
      "https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.NI.list.v04r01.csv"
    echo "OK: data/raw/ibtracs.NI.list.v04r01.csv"
    ;;
  hursat)
    YEAR="${2:?year required}"; STORM="${3:?storm name required}"
    BASE="https://www.ncei.noaa.gov/data/hurricane-satellite-hursat-b1/archive/v06/${YEAR}/"
    FILE=$(curl -s "$BASE" | grep -o 'href="[^"]*"' | grep -i "$STORM" | head -1 | sed 's/href="//;s/"//')
    [ -z "$FILE" ] && { echo "Storm $STORM not found in $YEAR"; exit 1; }
    OUT="data/raw/hursat_$(echo "$STORM" | tr 'A-Z' 'a-z')"
    mkdir -p "$OUT"
    curl -sSo /tmp/hursat.tar.gz "${BASE}${FILE}"
    tar -xzf /tmp/hursat.tar.gz -C "$OUT" && rm /tmp/hursat.tar.gz
    echo "OK: $OUT ($(ls "$OUT" | wc -l) files)"
    ;;
  *)
    echo "Usage: $0 ibtracs | hursat <year> <STORM_NAME>"; exit 1;;
esac
