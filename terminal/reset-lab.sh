#!/usr/bin/env bash
set -Eeuo pipefail

readonly PLAYER_USER="linuxscape"
readonly PLAYER_GROUP="linuxscape"
readonly STATE_DIR="/run/linuxscape"
readonly RUN_ID_PATH="${STATE_DIR}/run_id"

if [[ "${EUID}" -ne 0 ]]; then
    echo "reset-lab muss als root laufen." >&2
    exit 1
fi

mkdir -p "${STATE_DIR}"
chmod 0777 "${STATE_DIR}"

# Offene SSH-Shell und Prozesse der vorherigen Runde beenden.
pkill -KILL \
    -u "${PLAYER_USER}" \
    2>/dev/null \
    || true

# Alte Prozesse aus vorherigen Runden beseitigen.
for process_pattern in \
    "/escape/opt/boogies_setlist_script.py" \
    "queue_worker" \
    "queue-worker-mem" \
    "queue-monitor" \
    "light-sync" \
    "snackd" \
    "poster-watch"
do
    pkill -f \
        "${process_pattern}" \
        2>/dev/null \
        || true
done

rm -f \
    "${STATE_DIR}/state.json" \
    "${STATE_DIR}/events.jsonl" \
    "${STATE_DIR}/state.lock"

# Das bestehende Ursprungsskript erzeugt die Lab-Dateien.
bash /opt/linuxscape/reset-lab.original.sh

# Das Ursprungsskript startet seine Prozesse als root.
# Diese Instanzen werden beendet und danach als Spieler neu gestartet.
for process_pattern in \
    "/escape/opt/boogies_setlist_script.py" \
    "queue_worker" \
    "queue-worker-mem" \
    "queue-monitor" \
    "light-sync" \
    "snackd" \
    "poster-watch"
do
    pkill -f \
        "${process_pattern}" \
        2>/dev/null \
        || true
done

sleep 0.3

# Spielskripte bleiben root-owned.
chown -R root:root /escape
chmod -R a+rX /escape

# Spielerbereiche gehören dem SSH-Benutzer.
chown -R \
    "${PLAYER_USER}:${PLAYER_GROUP}" \
    /escape/home/newbie \
    /escape/run \
    /escape/var

chmod -R \
    u+rwX \
    /escape/home/newbie \
    /escape/run \
    /escape/var

# Parent-Prozess als echter Spielerbenutzer starten.
runuser \
    -u "${PLAYER_USER}" \
    -- \
    env \
    QUEUE_CHILD_COUNT="${QUEUE_CHILD_COUNT:-45}" \
    QUEUE_PREVIEW_KB_PER_CHILD="${QUEUE_PREVIEW_KB_PER_CHILD:-2048}" \
    QUEUE_SPAWN_INTERVAL_SECONDS="${QUEUE_SPAWN_INTERVAL_SECONDS:-0.5}" \
    QUEUE_LOG_INTERVAL_SECONDS="${QUEUE_LOG_INTERVAL_SECONDS:-4.0}" \
    bash -c '
        cd /escape/home/newbie

        nohup \
            python3 \
            /escape/opt/boogies_setlist_script.py \
            >/escape/run/boogies_setlist_script.out \
            2>&1 &

        echo $! \
            > /escape/run/boogies_setlist_script.pid
    '

# Unwichtige Hintergrundprozesse ebenfalls als Spieler starten.
for process_name in \
    queue-monitor \
    light-sync \
    snackd \
    poster-watch
do
    runuser \
        -u "${PLAYER_USER}" \
        -- \
        bash -c \
        "nohup \
            /escape/opt/dummy-loop.sh \
            '${process_name}' \
            >/escape/run/${process_name}.out \
            2>&1 &"
done

sleep 1

# Die neue Runden-ID wird erst veröffentlicht, wenn das Lab vollständig steht.
# game.py erkennt den Wechsel auch ohne Neustart des CSCape-Dienstes.
temporary_run_id="$(mktemp "${STATE_DIR}/.run-id.XXXXXX")"
cat /proc/sys/kernel/random/uuid > "${temporary_run_id}"
chmod 0644 "${temporary_run_id}"
mv -f "${temporary_run_id}" "${RUN_ID_PATH}"

echo "LinuxScape-Lab wurde neu erzeugt."
echo "Runden-ID: $(cat "${RUN_ID_PATH}")"
echo "Parent-PID: $(cat /escape/run/boogies_setlist_script.pid)"
