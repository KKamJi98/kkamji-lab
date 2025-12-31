#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: convert-images-to-webp.sh <src_dir> <dst_dir> [quality]

Convert PNG/JPG images under <src_dir> to WebP files in <dst_dir>.
- Keeps original images.
- Requires cwebp.

Args:
  src_dir  Source directory to scan (recursive)
  dst_dir  Destination directory for .webp files
  quality  Optional WebP quality (default: 80)
USAGE
}

if [ "$#" -lt 2 ]; then
  usage
  exit 1
fi

src_dir="$1"
dst_dir="$2"
quality="${3:-80}"

if [ ! -d "$src_dir" ]; then
  echo "ERROR: source directory not found: $src_dir" >&2
  exit 1
fi

if ! command -v cwebp >/dev/null 2>&1; then
  echo "ERROR: cwebp not found. Install it before running this script." >&2
  exit 1
fi

mkdir -p "$dst_dir"

converted=0
skipped=0
while IFS= read -r -d '' img; do
  base=$(basename "$img")
  name="${base%.*}"
  out="$dst_dir/${name}.webp"
  if [ -e "$out" ]; then
    echo "WARN: output exists, skipping: $out" >&2
    skipped=$((skipped + 1))
    continue
  fi
  cwebp -q "$quality" "$img" -o "$out" >/dev/null
  converted=$((converted + 1))
done < <(find "$src_dir" -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) -print0)

echo "Converted $converted image(s) into: $dst_dir"
if [ "$skipped" -gt 0 ]; then
  echo "Skipped $skipped duplicate(s). Consider renaming files or changing dst_dir." >&2
fi
