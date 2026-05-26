#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 /path/to/homeassistant/config" >&2
  echo "Example: $0 /config" >&2
  exit 2
fi

HA_CONFIG_DIR="$1"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/custom_components/bookoo_direct"
TARGET_DIR="${HA_CONFIG_DIR%/}/custom_components/bookoo_direct"

if [[ ! -d "$SOURCE_DIR" ]]; then
  echo "Source integration not found: $SOURCE_DIR" >&2
  exit 1
fi

mkdir -p "$(dirname "$TARGET_DIR")"
rm -rf "$TARGET_DIR"
cp -R "$SOURCE_DIR" "$TARGET_DIR"

find "$TARGET_DIR" -type d -name "__pycache__" -prune -exec rm -rf {} +
find "$TARGET_DIR" -type f -name "*.pyc" -delete

echo "Deployed Bookoo Direct to:"
echo "$TARGET_DIR"
echo
echo "Next steps:"
echo "1. Restart Home Assistant."
echo "2. Go to Settings -> Devices & services -> Add integration."
echo "3. Search for Bookoo Direct."
