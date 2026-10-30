#!/usr/bin/env bash
# Copy Google's apps from your own extracted stock product image into the device tree.
# Never commit or publish the results.
set -euo pipefail

usage() { echo "usage: $0 /path/to/stock/product device/google/sabrina16/proprietary" >&2; exit 2; }
[ $# -eq 2 ] || usage
stock=$1
out=$2
mkdir -p "$out"
for apk in priv-app/TVLauncherXPrebuilt/TVLauncherXPrebuilt.apk app/LatinIMEGoogleTvPrebuilt/LatinIMEGoogleTvPrebuilt.apk; do
    [ -f "$stock/$apk" ] || { echo "error: missing $stock/$apk" >&2; exit 1; }
    cp -v "$stock/$apk" "$out/"
done
