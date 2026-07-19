#!/usr/bin/env bash
set -Eeuo pipefail

docker-compose \
    exec \
    -T \
    terminal \
    /usr/local/sbin/reset-lab

docker-compose \
    restart \
    cscape

echo "Neue LinuxScape-Runde wurde gestartet."
