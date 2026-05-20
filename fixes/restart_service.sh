#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-}"

if [[ -z "$SERVICE" ]]; then
  echo "Usage: restart_service.sh <service-name.service>" >&2
  exit 1
fi

if [[ ! "$SERVICE" =~ ^[a-zA-Z0-9_.@-]+\.service$ ]]; then
  echo "Invalid service name: $SERVICE" >&2
  exit 1
fi

sudo systemctl restart "$SERVICE"
echo "$SERVICE restarted."
