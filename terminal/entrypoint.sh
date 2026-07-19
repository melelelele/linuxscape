#!/usr/bin/env bash
set -Eeuo pipefail

readonly PASSWORD="${LINUXSCAPE_PASSWORD:-linuxscape}"

mkdir -p \
    /run/sshd \
    /run/linuxscape

chmod 0777 /run/linuxscape

printf \
    'linuxscape:%s\n' \
    "${PASSWORD}" \
    | chpasswd

ssh-keygen -A

/usr/local/sbin/reset-lab

exec /usr/sbin/sshd \
    -D \
    -e \
    -f /etc/ssh/sshd_config
