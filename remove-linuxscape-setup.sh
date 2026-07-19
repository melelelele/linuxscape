#!/usr/bin/env bash
set -Eeuo pipefail

echo "Entferne LinuxScape vom System..."

echo "Stoppe Services..."
systemctl stop linuxscape-cscape.service 2>/dev/null || true
systemctl disable linuxscape-cscape.service 2>/dev/null || true

echo "Beende Spielprozesse..."
pkill -KILL -u linuxscape 2>/dev/null || true
pkill -f "/escape/opt/boogies_setlist_script.py" 2>/dev/null || true
pkill -f "queue_worker" 2>/dev/null || true
pkill -f "queue-monitor" 2>/dev/null || true
pkill -f "light-sync" 2>/dev/null || true
pkill -f "snackd" 2>/dev/null || true
pkill -f "poster-watch" 2>/dev/null || true

echo "Entferne systemd-Service..."
rm -f /etc/systemd/system/linuxscape-cscape.service
systemctl daemon-reload

echo "Entferne SSH-Konfiguration..."
rm -f /etc/ssh/sshd_config.d/90-linuxscape.conf

if sshd -t; then
    systemctl restart ssh
else
    echo "WARNUNG: sshd-Konfiguration ist fehlerhaft. SSH wurde nicht neu gestartet." >&2
fi

echo "Entferne installierte LinuxScape-Dateien..."
rm -rf /opt/linuxscape
rm -rf /escape
rm -rf /run/linuxscape

rm -f /usr/local/bin/queue-worker-mem
rm -f /usr/local/bin/linuxscape-shell
rm -f /usr/local/bin/linuxscape-record-command
rm -f /usr/local/sbin/linuxscape-reset
rm -f /usr/local/sbin/linuxscape-uninstall

rm -rf /etc/linuxscape

echo "Entferne Benutzer..."
if id linuxscape >/dev/null 2>&1; then
    userdel -r linuxscape 2>/dev/null || userdel linuxscape
fi

if id cscape >/dev/null 2>&1; then
    userdel -r cscape 2>/dev/null || userdel cscape
fi

echo "LinuxScape wurde entfernt."
echo "Optional können ungenutzte Pakete manuell entfernt werden, z. B.:"
echo "  sudo apt autoremove"



id linuxscape || echo "linuxscape entfernt"
id cscape || echo "cscape entfernt"

ls /opt/linuxscape 2>/dev/null || echo "/opt/linuxscape entfernt"
ls /escape 2>/dev/null || echo "/escape entfernt"

systemctl status linuxscape-cscape.service 2>/dev/null || echo "Service entfernt"
