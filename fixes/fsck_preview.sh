#!/usr/bin/env bash
set -euo pipefail

if ! command -v fsck >/dev/null 2>&1; then
  echo "fsck not found on this system." >&2
  exit 1
fi

sudo fsck -A -N
