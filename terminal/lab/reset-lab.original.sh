#!/usr/bin/env bash
set -euo pipefail

pkill -f "/escape/opt/boogies_setlist_script.py" 2>/dev/null || true
pkill -f "queue_worker" 2>/dev/null || true
pkill -f "queue-monitor" 2>/dev/null || true
pkill -f "light-sync" 2>/dev/null || true
pkill -f "snackd" 2>/dev/null || true
pkill -f "poster-watch" 2>/dev/null || true

rm -rf /escape

mkdir -p \
  /escape/home/newbie/logs \
  /escape/home/newbie/docs \
  /escape/home/newbie/flyers \
  /escape/home/newbie/scripts \
  /escape/home/newbie/archive \
  /escape/home/newbie/playlists \
  /escape/opt \
  /escape/run \
  /escape/var/queue \
  /escape/var/cache/previews

cat > /escape/home/newbie/README.txt <<'TXT'
[BYTE-BENNYS NOTIZEN FUER PROBLEME BEI DER KISTE]

AM WICHTIGSTEN: erst mal nicht ausrasten. Erst mal folgendes probieren:

1. BENUTZER PRUEFEN
   Beispiel: whoami

2. AKTUELLEN ORDNER PRUEFEN
   Beispiel: pwd

3. DATEIEN IM ORDNER ANZEIGEN
   Beispiel: ls

4. VERSTECKTE DATEIEN ANZEIGEN
   Beispiel: ls -a

5. DATEIEN LESEN
   Beispiel: cat [Dateiname]

6. DATEIEN SUCHEN
   Beispiel: find [Ort] -name [Dateiname]

7. LOGDATEIEN LESEN
   Beispiel: cat [Logdatei]

8. SPEICHER PRUEFEN
   Beispiel: free -h

9. PROZESSE PRUEFEN
   Beispiel: ps aux

10. PROZESSE NACH MUSTER STOPPEN
    Beispiel: pkill -f [Suchmuster]

HINWEISE:
- Logs liegen oft in Ordnern mit dem Namen logs.
- Versteckte Dateien beginnen mit einem Punkt.
- Wenn viele aehnliche Prozesse laufen, kann es sein, dass ein anderer Prozess sie erzeugt.
TXT

cat > /escape/home/newbie/.queue_hint <<'TXT'
QUEUE-HINWEIS

Boogie hat die Setlist automatisiert und ein Python-Skript geschrieben, es heisst:
boogies_setlist_script.py
TXT

cat > /escape/home/newbie/SCRIPTS.txt <<'TXT'
LOCAL SCRIPTS

Skripte liegen im Ordner:

scripts

Allgemeine Muster:

ls scripts
cat [Skriptpfad]
./[Skriptpfad]

Hinweis:
Dieses Terminal zeigt Ausgaben nach Befehlsende an. Scripts sind deshalb auf kurze, abgeschlossene Ausgaben ausgelegt.
TXT

cat > /escape/home/newbie/flyers/party.txt <<'TXT'
CAVE NIGHT

Bring your own keyboard.
No drinks on the mixer.
Do not touch the projector.
TXT

cat > /escape/home/newbie/docs/equipment.txt <<'TXT'
EQUIPMENT LIST

speakers: 2
mixer: 1
projector: 1
folding_chairs: 9
extension_cords: 5
power_strips: 4
network_switches: 1
label_printer: 1
microphones: 2
desk_lamps: 3
TXT

cat > /escape/home/newbie/docs/cable_labels.txt <<'TXT'
CABLE LABELS

red: projector
blue: speakers
green: lights
yellow: network
white: power
black: unlabelled
TXT

cat > /escape/home/newbie/docs/storage_index.txt <<'TXT'
STORAGE INDEX

box_a: adapters
box_b: audio cables
box_c: power cables
box_d: labels
box_e: tools
box_f: flyers
TXT

cat > /escape/home/newbie/docs/network_notes.txt <<'TXT'
NETWORK NOTES

hostname: cavebox
user: newbie
local_data_path: /escape/home/newbie
log_path: /escape/home/newbie/logs
queue_path: /escape/var/queue
script_path: /escape/opt
TXT

cat > /escape/home/newbie/docs/projector.txt <<'TXT'
PROJECTOR NOTES

input: hdmi
audio: disabled
mount: ceiling
remote_storage: box_e
filter_service_interval_days: 30
TXT

cat > /escape/home/newbie/archive/old_wifi_notes.txt <<'TXT'
OLD WIFI NOTES

basement123
cavebox2023
grooveguest
soundcheck

status: outdated
TXT

cat > /escape/home/newbie/archive/lost_and_found.txt <<'TXT'
LOST AND FOUND

black_hoodie
black_cap
left_glove
small_notebook
usb_c_adapter
old_key
battery_pack_empty
TXT

cat > /escape/home/newbie/archive/shopping_list.txt <<'TXT'
SHOPPING LIST

trash_bags
gaffer_tape
paper_towels
batteries
marker_pens
cable_ties
water
ear_plugs
TXT

cat > /escape/home/newbie/playlists/boogies_setlist.txt <<'TXT'
BOOGIE_SETLIST

01 Gloop Gloop Baby
02 The Bass Lives in the Basement
03 Vacuum Cleaner in the Fog
04 Fish Disco Behind the Heater
05 Wet Socks on the Dancefloor
06 The Fridge Hums the Hook
07 The Queue Is Hungry
08 Small Monsters, Big Playlist
09 The Beat Has Hiccups
10 Boogie Loads More
11 Boogie Loads More Again
12 Boogie Does Not Stop
13 Last Song For Real Now
14 Last Song Two
15 Last Song Final Final
16 Last Song Final Final New
TXT


cat > /escape/home/newbie/scripts/poster.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

text="${*:-GROOVE CAVE}"

if command -v figlet >/dev/null 2>&1; then
  figlet "$text"
elif command -v toilet >/dev/null 2>&1; then
  toilet "$text"
else
  echo "=============================="
  echo "$text"
  echo "=============================="
fi
SH

chmod +x /escape/home/newbie/scripts/poster.sh

cat > /escape/home/newbie/scripts/cow.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

message="${*:-no signal on channel 2}"

if command -v cowsay >/dev/null 2>&1; then
  cowsay "$message"
elif [ -x /usr/games/cowsay ]; then
  /usr/games/cowsay "$message"
else
  echo "< $message >"
  echo "        \\   ^__^"
  echo "         \\  (oo)\\_______"
  echo "            (__)\\       )\\/\\"
  echo "                ||----w |"
  echo "                ||     ||"
fi
SH

chmod +x /escape/home/newbie/scripts/cow.sh

cat > /escape/home/newbie/scripts/sl.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

if command -v sl >/dev/null 2>&1; then
  exec sl
fi

if [ -x /usr/games/sl ]; then
  exec /usr/games/sl
fi

echo "sl is not installed"
exit 1
SH

chmod +x /escape/home/newbie/scripts/sl.sh
cat > /usr/local/bin/sl <<'SH'
#!/usr/bin/env bash
set -euo pipefail

exec /usr/games/sl "$@"
SH

chmod +x /usr/local/bin/sl
cat > /escape/home/newbie/scripts/spectrum.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

cat <<'TXT'
AUDIO SPECTRUM SNAPSHOT

31Hz    ########
63Hz    ############
125Hz   ###############
250Hz   ##########
500Hz   #######
1kHz    #############
2kHz    #########
4kHz    ######
8kHz    ####
16kHz   ##

TXT
SH

chmod +x /escape/home/newbie/scripts/spectrum.sh


cat > /escape/home/newbie/scripts/track-card.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

tracks_file="/escape/home/newbie/playlists/boogies_setlist.txt"

mapfile -t tracks < <(grep -E '^[0-9]{2} ' "$tracks_file" | sed 's/^[0-9][0-9] //')

if [ "${#tracks[@]}" -eq 0 ]; then
  echo "no tracks found"
  exit 0
fi

track="${tracks[$(( RANDOM % ${#tracks[@]} ))]}"

cat <<TXT
+--------------------------------------------+
| TRACK CARD                                 |
+--------------------------------------------+
| title: ${track}
| source: boogies_setlist.txt
+--------------------------------------------+
TXT
SH

chmod +x /escape/home/newbie/scripts/track-card.sh



cat > /escape/home/newbie/scripts/panel.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cat <<'TXT'
+----------------------------------------------+
| LOCAL CONTROL PANEL                          |
+----------------------+-----------------------+
| audio                | ready                 |
| projector            | hdmi                  |
| lights               | local                 |
| storage              | mounted               |
| queue                | check process list    |
+----------------------+-----------------------+
TXT
SH

chmod +x /escape/home/newbie/scripts/panel.sh

cat > /escape/home/newbie/scripts/files.sh <<'SH'
#!/usr/bin/env bash
set -euo pipefail

find /escape/home/newbie -maxdepth 2 -type f | sort
SH

chmod +x /escape/home/newbie/scripts/files.sh

cat > /escape/home/newbie/logs/system.log <<'TXT'
[grooveboot] cavebox online
[grooveboot] container profile loaded
[grooveboot] queue subsystem enabled
[room] storage paths mounted
[room] local scripts indexed
[queue] preview cache target is memory-backed
[queue] queue depth is growing faster than playback
[queue] preview workers are being created repeatedly
[system] memory pressure rising
[system] parent script creates preview children
TXT


cat > /escape/opt/boogies_setlist_script.py <<'PY'
#!/usr/bin/env python3
import os
import re
import shlex
import signal
import subprocess
import sys
import time
from datetime import datetime

LOG_PATH = "/escape/home/newbie/logs/system.log"
QUEUE_STATE_PATH = "/escape/var/queue/live.queue"
WORKER_BINARY = "/usr/local/bin/queue-worker-mem"

CHILD_COUNT = int(os.environ.get("QUEUE_CHILD_COUNT", "45"))
PREVIEW_KB_PER_CHILD = int(os.environ.get("QUEUE_PREVIEW_KB_PER_CHILD", "1024"))
SPAWN_INTERVAL_SECONDS = float(os.environ.get("QUEUE_SPAWN_INTERVAL_SECONDS", "0.12"))
LOG_INTERVAL_SECONDS = float(os.environ.get("QUEUE_LOG_INTERVAL_SECONDS", "4.0"))

TRACKS = [
    "Pickle Water at Midnight",
    "No Dancing in the Aquarium",
    "Boogie's Slime Waltz",
    "The Bass Lives in the Basement",
    "Vacuum Cleaner in the Fog",
    "Leave the Couch Alone",
    "Glitter on Concrete",
    "Fish Disco Behind the Heater",
    "Cable Salad with Extra Sauce",
    "Three AM in the Drink Storage",
    "The Carpet Sticks Back",
    "Gloop Gloop Baby",
    "Wet Socks on the Dancefloor",
    "The Cup Was Already Like That",
    "Slime Trail to the DJ Booth",
    "Too Many Tracks Not Enough Sense",
    "Boogie Will Only Be a Second",
    "Please Don't Press the Red Button",
    "The Lamp Flickers on Beat",
    "Basement Air and Confetti",
    "Dance the Queue Waltz",
    "Bass from the Trash Can",
    "The Fridge Hums the Hook",
    "Questionable Party Mode",
    "Five More Minutes",
    "That Wasn't Fog",
    "Where Is the Vacuum Cleaner",
    "Please No More Optimization",
    "The Queue Is Hungry",
    "Slimy Transitions",
    "Track Number Way Too Many",
    "The Beat Wears Rubber Boots",
    "All Sticky Hands in the Air",
    "Something Lives Under the Booth",
    "Rave in the Storage Room",
    "Dripstone Techno",
    "Cable Tie Romance",
    "Musty Moonlight",
    "The Floor Makes Noises",
    "Left of the Broken Chair",
    "Lights Off Slime On",
    "No Signal but Good Vibes",
    "The Mixer Smells Like Pickles",
    "Preload Everything Please",
    "Loose Contact in My Heart",
    "The Bass Is Too Soft",
    "Slime in the Cup Holder",
    "Dancefloor Slightly Damp",
    "Nobody Knows What's Going On",
    "Boogie Slightly Overdoes It",
    "Tiny Pause Huge Damage",
    "The Last Track Was Yesterday",
    "Queue Queue Kachoo",
    "Gloop on Repeat",
    "Left Sofa Is Blinking",
    "Fog Machine Without Permission",
    "The Club in the Cable Duct",
    "Fish Food Finale",
    "Mushy Drop",
    "Night of Too Many Tracks",
    "Slime Trail Deluxe",
    "Basement Kid Mayhem",
    "Slower Faster Slower",
    "Second Hand Sense of Rhythm",
    "The Playlist Is Breathing",
    "Not This Track Again",
    "The Floor Sticks in Major",
    "Bassline from a Bucket",
    "The Queue Is Not Well",
    "More Is Not Always Music",
    "All Tracks at Once",
    "Pre Party in Preview Memory",
    "Boogie and the 45 Children",
    "The Little Green Overkill",
    "Dance with the Process Child",
    "Slime Slide to the Chorus",
    "The Beat Sits Down for a Moment",
    "Basement Window Closed Bass Out",
    "Drops on the Turntable",
    "The Algorithm Is Thirsty",
    "It Says Do Not Touch",
    "Rubber Boot Groove",
    "Five Liters of Funk",
    "Storage Room Afterparty",
    "Dance Tea with Cable Smell",
    "Slimy Sunrise",
    "The Last Drop Is Dripping",
    "Queue in a Bucket",
    "Bass Under Observation",
    "The Great Gloop",
    "Small Monsters Big Playlist",
    "One Track Rarely Comes Alone",
    "The Booth Ghost",
    "We'll Clean Up Tomorrow",
    "Nobody Cleans Up Tomorrow",
    "The Carpet Knows Too Much",
    "Dust Bunnies in the Strobe Light",
    "Please Do Not Feed Boogie",
    "Music for Damp Cardboard Boxes",
    "The Beat Has Hiccups",
    "Dance of the Spare Cables",
    "The Queue Waves Back",
    "Too Much Preview Too Little Pause",
    "Glibber on Beat",
    "Boogie Loads More",
    "Boogie Loads More Again",
    "Boogie Does Not Stop",
    "Final Boss Drink Crate",
    "The Fan Claps Along",
    "The Speakers Need a Vacation",
    "Everything Is a Bit Much",
    "Last Song For Real Now",
    "Last Song Two",
    "Last Song Final Final",
    "Last Song Final Final New",
]

children = []
running = True
last_status_log = 0.0


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def log(message: str) -> None:
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"[{utc_now()}] {message}\n")


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    return value or "track"


def alive_children():
    return [child for child in children if child.poll() is None]


def write_queue_state() -> None:
    alive = alive_children()
    approx_kb = len(alive) * PREVIEW_KB_PER_CHILD
    approx_mb = approx_kb / 1024

    with open(QUEUE_STATE_PATH, "w", encoding="utf-8") as f:
        f.write("[live queue]\n")
        f.write(f"target_children={CHILD_COUNT}\n")
        f.write(f"alive_children={len(alive)}\n")
        f.write(f"preview_kb_per_child={PREVIEW_KB_PER_CHILD}\n")
        f.write(f"approx_preview_memory_mb={approx_mb:.1f}\n")
        f.write("problem=parent script keeps replacing stopped children\n")


def cleanup(signum=None, frame=None) -> None:
    global running
    running = False

    log("boogies_setlist_script.py: stop signal received")

    for child in alive_children():
        try:
            child.terminate()
        except ProcessLookupError:
            pass

    time.sleep(0.4)

    force_killed = 0

    for child in alive_children():
        if child.poll() is None:
            force_killed += 1
            try:
                child.kill()
            except ProcessLookupError:
                pass

    log(f"boogies_setlist_script.py: cleanup finished; force_killed={force_killed}")
    write_queue_state()
    sys.exit(0)


signal.signal(signal.SIGTERM, cleanup)
signal.signal(signal.SIGINT, cleanup)


def spawn_worker(index: int) -> subprocess.Popen:
    track = TRACKS[index % len(TRACKS)]
    track_slug = slugify(track)
    worker_name = f"queue_worker_{track_slug}_{index:02d}"

    command = (
        f"exec -a {shlex.quote(worker_name)} "
        f"{shlex.quote(WORKER_BINARY)} "
        f"{shlex.quote(str(PREVIEW_KB_PER_CHILD))} "
        f"{shlex.quote(track)}"
    )

    child = subprocess.Popen(
        ["bash", "-c", command],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    log(
        f"boogies_setlist_script.py: spawned child pid={child.pid} "
        f"name={worker_name} track='{track}' preview_kb={PREVIEW_KB_PER_CHILD}"
    )

    return child


log(
    "boogies_setlist_script.py: started; "
    f"target_children={CHILD_COUNT}; "
    f"preview_kb_per_child={PREVIEW_KB_PER_CHILD}; "
    f"spawn_interval={SPAWN_INTERVAL_SECONDS}s"
)
log("boogies_setlist_script.py: queue depth is controlled by child count, not by actual playback demand")

i = 0

while running:
    children = alive_children()

    if len(children) < CHILD_COUNT:
        missing = CHILD_COUNT - len(children)

        if missing == CHILD_COUNT or missing % 10 == 0 or missing <= 3:
            log(
                f"boogies_setlist_script.py: queue below target; "
                f"alive_children={len(children)} missing_children={missing}"
            )

        child = spawn_worker(i)
        children.append(child)
        i += 1

        write_queue_state()
    else:
        now = time.time()

        if now - last_status_log >= LOG_INTERVAL_SECONDS:
            approx_mb = (len(children) * PREVIEW_KB_PER_CHILD) / 1024

            log(
                f"boogies_setlist_script.py: holding queue_depth={len(children)} "
                f"approx_preview_memory_mb={approx_mb:.1f} memory_pressure=high"
            )
            log(
                "boogies_setlist_script.py: child processes are still alive; parent process is still active"
            )

            write_queue_state()
            last_status_log = now

    time.sleep(SPAWN_INTERVAL_SECONDS)
PY

chmod +x /escape/opt/boogies_setlist_script.py
cat > /escape/opt/dummy-loop.sh <<'SH'
#!/usr/bin/env bash
name="$1"
exec -a "$name" sleep 999999
SH

chmod +x /escape/opt/dummy-loop.sh

cat > /usr/local/bin/help <<'SH'
#!/usr/bin/env bash
cat <<'TXT'
groove cave command patterns:

whoami
pwd
ls
ls -a

cat [Dateiname]
cat [Dateipfad]
cat [Logdatei]

find [Ort] -name [Dateiname]

free -h
cat /sys/fs/cgroup/memory.max
cat /sys/fs/cgroup/memory.current

ps aux

pkill -f [Suchmuster]

./[Skriptpfad]

notes:
- Dateien liest du mit cat.
- Logs sind auch nur Dateien.
- Prozesse siehst du mit ps aux.
- Skripte in Ordnern startest du mit ./[Skriptpfad].
- free -h kann im Container Host-Speicher anzeigen.
- Das echte Container-Limit steht in /sys/fs/cgroup/memory.max.

tab completion and arrow keys are enabled.
TXT
SH

chmod +x /usr/local/bin/help

nohup env \
  QUEUE_CHILD_COUNT=45 \
  QUEUE_PREVIEW_KB_PER_CHILD=2048 \
  QUEUE_SPAWN_INTERVAL_SECONDS=5 \
  QUEUE_LOG_INTERVAL_SECONDS=4.0 \
  python3 /escape/opt/boogies_setlist_script.py \
  >/escape/run/boogies_setlist_script.out 2>&1 &

echo $! > /escape/run/boogies_setlist_script.pid

nohup /escape/opt/dummy-loop.sh queue-monitor >/escape/run/queue-monitor.out 2>&1 &
nohup /escape/opt/dummy-loop.sh light-sync >/escape/run/light-sync.out 2>&1 &
nohup /escape/opt/dummy-loop.sh snackd >/escape/run/snackd.out 2>&1 &
nohup /escape/opt/dummy-loop.sh poster-watch >/escape/run/poster-watch.out 2>&1 &

sleep 2

echo "Groove lab reset complete."
echo "boogies_setlist_script pid: $(cat /escape/run/boogies_setlist_script.pid)"
echo "queue_worker count: $(pgrep -f queue_worker 2>/dev/null | wc -l | tr -d ' ')"