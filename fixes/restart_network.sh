#!/usr/bin/env bash
set -euo pipefail

if systemctl list-unit-files | grep -q '^NetworkManager\.service'; then
  sudo systemctl restart NetworkManager
  echo "NetworkManager restarted."
  exit 0
fi

if systemctl list-unit-files | grep -q '^systemd-networkd\.service'; then
  sudo systemctl restart systemd-networkd
  echo "systemd-networkd restarted."
  exit 0
fi

echo "No supported network service found." >&2
exit 1
