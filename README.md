# LinuxScape Live

LinuxScape Live ist ein Linux-Escape-Room auf Basis von CSCape.

Das Projekt besteht aus zwei getrennten Komponenten:

1. **CSCape-Regiemodul**

   * Story
   * Reveal.js-Präsentation
   * Spiellogik (`game.py`)
   * automatische Fortschrittskontrolle

2. **Linux-Lab**

   * Linux-Terminal per SSH
   * Prozesse
   * Dateien
   * Linux-Kommandos

Der Spieler arbeitet ausschließlich in einem Terminal.

Das Regiemodul erkennt automatisch, welche Aufgaben bereits gelöst wurden, und schaltet die Story weiter.

---



Das Linux-Lab schreibt lokale JSON-Dateien.

`game.py` liest diese Dateien und entscheidet, wann ein Check erfüllt wurde.

---

# Projektstruktur

```text
linuxscape-live/
│
├── cscape/
│   ├── game.py
│   ├── index.html
│   ├── cscape.py
│   ├── revealjs-cscape.js
│   ├── run.sh
│   ├── reveal.js/
│   ├── story-styles/
│   ├── pics/
│   └── sounds/
│
├── terminal/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── linuxscape-shell
│   ├── record-command.py
│   ├── reset-lab.sh
│   ├── queue-worker-mem.c
│   └── lab/
│
├── runtime/
│
├── docker-compose.yml
│
└── README.md
```

---

# Spielprinzip

Der Spieler verbindet sich per SSH mit dem Linux-Lab.

Beispiel:

```bash
ssh -p 2222 linuxscape@localhost
```

Passwort:

```text
linuxscape
```

Im Spiel werden unter anderem folgende Befehle verwendet:

```bash
whoami
pwd
ls
ls -a
cat
find
free -h
ps aux
pkill -f
```

Die Spielfigur untersucht ein fehlerhaftes Musiksystem.

Im Hintergrund läuft:

```text
boogies_setlist_script.py
```

Dieses erzeugt viele:

```text
queue_worker
```

Prozesse.

Die Aufgabe besteht darin:

1. Hinweise zu finden
2. Prozesse zu analysieren
3. die Worker zu stoppen
4. den Parent-Prozess zu finden
5. den Parent-Prozess zu stoppen

---

# Lokale Entwicklung

## Voraussetzungen

Beispiel Debian:

```bash
sudo apt update

sudo apt install -y \
    python3 \
    python3-venv \
    python3-pip \
    docker.io \
    docker-compose \
    openssh-client
```

---

# Terminal-Lab starten

Projektordner:

```bash
cd linuxscape-live
```

Container bauen:

```bash
docker-compose build
```

Container starten:

```bash
docker-compose up -d
```

Status prüfen:

```bash
docker-compose ps
```

Es sollte ein Container laufen:

```text
linuxscape-terminal
```

---

# SSH-Verbindung testen

```bash
ssh -p 2222 linuxscape@localhost
```

Passwort:

```text
linuxscape
```

Test:

```bash
whoami
pwd
```

---

# CSCape starten


In das CSCape-Verzeichnis wechseln:

```bash
cd cscape
```

Starten:

```bash
./run.sh
```
und in einem separaten Fenster:
```bash
python tts_server.py
```
Alternativ:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python tts_server.py
```
und in einem separaten Fenster:
```bash
cd ~/Dokumente/GitHub/cscaperooms/linuxscape-live/cscape

source .venv/bin/activate

export LINUXSCAPE_STATE_DIR="$(realpath ../runtime)"
export PORT=5000

python game.py
```


Dadurch wird:

```text
localhost:5000
```

gestartet.

---

# Regie-Präsentation

CSCape funktioniert wie ein normales CSCape-Projekt.

`index.html` wird lokal im Browser geöffnet.

Die Präsentation kommuniziert automatisch mit:

```text
http://localhost:5000
```

über das CSCape-Plugin.

---

# Runtime-Dateien

Das Linux-Lab schreibt:

```text
runtime/state.json
runtime/events.jsonl
```

Beispiel:

```json
{
  "last_command": "whoami"
}
```

Diese Dateien werden von `game.py` ausgewertet.

---

# Neue Spielrunde

Lab zurücksetzen:

```bash
docker-compose restart terminal
```

oder:

```bash
docker-compose down
docker-compose up -d
```

Dadurch werden:

* Dateien neu erzeugt
* Prozesse neu gestartet
* Hinweise zurückgesetzt

---

# Raspberry-Pi-Betrieb

Der Raspberry Pi ersetzt im echten Aufbau den lokalen Terminal-Container.

In der lokalen Entwicklung sieht das Setup so aus:

```text
Spieler-PC
    │
    │ ssh -p 2222 linuxscape@SERVER-PC
    ▼
Server-PC
    ├── terminal-Container
    ├── runtime/
    └── cscape/
```

Im Raspberry-Pi-Betrieb sieht es so aus:

```text
Spieler-PC
    │
    │ ssh linuxscape@linuxscape.local
    ▼
Raspberry Pi
    ├── echtes Linux-Lab unter /escape
    ├── echte Spielprozesse
    ├── runtime-State unter /run/linuxscape
    └── cscape-Regiemodul
```

Der Spieler-PC braucht dann nur:

* ein Terminal
* SSH-Client
* Netzwerkzugang zum Raspberry Pi

Docker wird auf dem Spieler-PC nicht benötigt.

---

## Ziel

Auf dem Raspberry Pi laufen:

1. SSH-Zugang für den Spieler
2. Spielumgebung unter `/escape`
3. Parent-Prozess `boogies_setlist_script.py`
4. Worker-Prozesse `queue_worker_*`
5. lokaler Command-Recorder
6. CSCape-Regiemodul

Der Spieler verbindet sich per SSH und landet direkt in:

```text
/escape/home/newbie
```

---

## Voraussetzungen

Empfohlen:

* Raspberry Pi
* Raspberry Pi und Spieler-PC im selben Netzwerk
* SSH aktiviert

Auf dem Pi installieren:

```bash
sudo apt update

sudo apt install -y \
  python3 \
  python3-venv \
  python3-pip \
  openssh-server \
  procps \
  psmisc \
  gcc \
  make \
  libc6-dev \
  bash \
  less \
  figlet \
  cowsay \
  sl \
  rsync
```

---

## Benutzer anlegen

Es gibt zwei wichtige Rollen:

* `linuxscape`: Spieler-Shell und Spielprozesse
* `cscape`: Regiemodul

Spieler-Benutzer anlegen, falls er noch nicht existiert:

```bash
id linuxscape || sudo useradd \
  --create-home \
  --shell /bin/bash \
  linuxscape
```

Passwort für den Spieler-Benutzer setzen:

```bash
sudo passwd linuxscape
```

Der gesetzte Passwortwert ist später das SSH-Passwort für den Spieler.

Regie-Benutzer anlegen, falls er noch nicht existiert:

```bash
id cscape || sudo useradd \
  --system \
  --home-dir /opt/linuxscape/cscape \
  --shell /usr/sbin/nologin \
  cscape
```

Prüfen:

```bash
id linuxscape
id cscape
```


## Projekt auf den Pi kopieren

Das Repository auf dem Pi clonen oder auf andere Weise den Projektordner auf dem Pi ablegen:

```bash
git clone ...
```


---

## Projektverzeichnisse auf dem Pi einrichten

Auf dem Pi:

```bash
sudo mkdir -p /opt/linuxscape
sudo rm -rf /opt/linuxscape/cscape
sudo rm -rf /opt/linuxscape/terminal

sudo cp -a /pfad/zum/linuxscape-live/cscape /opt/linuxscape/cscape
sudo cp -a /pfad/zum/linuxscape-live/terminal /opt/linuxscape/terminal

sudo mkdir -p /run/linuxscape
sudo chmod 0777 /run/linuxscape
```

---

## Queue-Worker bauen

Der Worker ist ein kleines C-Programm und muss auf dem Pi gebaut werden:

```bash
sudo gcc \
  -O2 \
  -Wall \
  -Wextra \
  -o /usr/local/bin/queue-worker-mem \
  /opt/linuxscape/terminal/queue-worker-mem.c
```

Prüfen:

```bash
ls -l /usr/local/bin/queue-worker-mem
```

---

## Lab-Reset installieren

Das Reset-Skript erzeugt die Spielumgebung unter `/escape`.

```bash
sudo cp \
  /opt/linuxscape/terminal/lab/reset-lab.original.sh \
  /opt/linuxscape/reset-lab.original.sh

sudo cp \
  /opt/linuxscape/terminal/reset-lab.sh \
  /usr/local/sbin/linuxscape-reset

sudo chmod +x \
  /opt/linuxscape/reset-lab.original.sh \
  /usr/local/sbin/linuxscape-reset
```

---

## Spieler-Shell installieren

Diese Dateien sorgen dafür, dass der Spieler beim SSH-Login direkt im Spiel landet und Befehle aufgezeichnet werden.

```bash
sudo cp \
  /opt/linuxscape/terminal/linuxscape-shell \
  /usr/local/bin/linuxscape-shell

sudo cp \
  /opt/linuxscape/terminal/record-command.py \
  /usr/local/bin/linuxscape-record-command

sudo mkdir -p /etc/linuxscape

sudo cp \
  /opt/linuxscape/terminal/bashrc \
  /etc/linuxscape/bashrc

sudo chmod +x \
  /usr/local/bin/linuxscape-shell \
  /usr/local/bin/linuxscape-record-command

sudo chmod 0644 \
  /etc/linuxscape/bashrc
```

---

## SSH konfigurieren

Der Spieler soll nicht in einer normalen Shell starten, sondern direkt in der LinuxScape-Spielumgebung.

```bash
sudo tee /etc/ssh/sshd_config.d/90-linuxscape.conf >/dev/null <<'EOF'
Match User linuxscape
    ForceCommand /usr/local/bin/linuxscape-shell
    PermitTTY yes
    DisableForwarding yes
    X11Forwarding no
    AllowAgentForwarding no
    PermitTunnel no
    PermitUserEnvironment no
EOF
```

Konfiguration prüfen:

```bash
sudo sshd -t
```

SSH neu starten:

```bash
sudo systemctl restart ssh
```

Falls es bei der installierten OpenSSH-Version Probleme gibt, könnte diese Alternative besser funktionieren:
```bash
sudo tee /etc/ssh/sshd_config.d/90-linuxscape.conf >/dev/null <<'EOF'
Match User linuxscape
    ForceCommand /usr/local/bin/linuxscape-shell
    PermitTTY yes
    DisableForwarding yes
    X11Forwarding no
    AllowAgentForwarding no
    PermitTunnel no
EOF
```
danach SSH neu starten:

```bash
sudo systemctl restart ssh
```


---

## Lab erzeugen

Jetzt die erste Runde erzeugen:

```bash
sudo linuxscape-reset
```

Prüfen:

```bash
ls -la /escape/home/newbie
pgrep -a -u linuxscape -f 'boogies_setlist_script|queue_worker'
```

Erwartet:

* `/escape/home/newbie` existiert
* `boogies_setlist_script.py` läuft
* mehrere `queue_worker_*` Prozesse laufen

---

## CSCape-Python-Umgebung einrichten

```bash
sudo python3 -m venv /opt/linuxscape/cscape/.venv

sudo /opt/linuxscape/cscape/.venv/bin/pip install \
  --upgrade pip wheel

sudo /opt/linuxscape/cscape/.venv/bin/pip install \
  -r /opt/linuxscape/cscape/requirements.txt
```

Rechte setzen:

```bash
sudo chown -R cscape:cscape /opt/linuxscape/cscape
sudo chmod -R a+rX /opt/linuxscape/cscape
sudo chmod 0777 /run/linuxscape
```

---

## CSCape-Service einrichten

```bash
sudo tee /etc/systemd/system/linuxscape-cscape.service >/dev/null <<'EOF'
[Unit]
Description=LinuxScape CSCape Regiemodul
After=network.target

[Service]
Type=simple
User=cscape
Group=cscape
WorkingDirectory=/opt/linuxscape/cscape
Environment=PORT=5000
Environment=LINUXSCAPE_STATE_DIR=/run/linuxscape
Environment=PYTHONUNBUFFERED=1
ExecStart=/opt/linuxscape/cscape/.venv/bin/python /opt/linuxscape/cscape/game.py
Restart=on-failure
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF
```

Service starten:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now linuxscape-cscape.service
```

Status prüfen:

```bash
systemctl status linuxscape-cscape.service
```

Logs:

```bash
journalctl -u linuxscape-cscape.service -f
```

---

# CSCape starten


In das CSCape-Verzeichnis des Projekts wechseln:

```bash
cd /pfad/zum/linuxscape-live/cscape
```

Starten:

```bash
./run.sh
```
und in einem separaten Fenster:
```bash
python tts_server.py
```
Alternativ:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python tts_server.py
```
und in einem separaten Fenster:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python game.py
```

Dadurch wird:

```text
localhost:5000
```

gestartet.

---

## Spieler-PC einrichten

Der Spieler-PC braucht nur einen SSH-Client.

Auf Linux ist dieser meistens schon vorhanden.

Test:

```bash
ssh -V
```
IP-Adresse von Raspberry Pi herausfinden:
*auf Pi:*
```
hostname -I
```

IP verwenden (Beispiel: 192.168.178.55, ersetzen mit richtiger IP-Adresse):
*auf Spieler-PC:*

```bash
ssh linuxscape@192.168.178.55 
```

Nach dem Login mit dem im Einrichtungsprozess selbst gewählten Passwort sollte der Spieler direkt hier landen:

```text
/escape/home/newbie
```

Testbefehle:

```bash
whoami
pwd
ls
```

---

## Spielrunde starten

Auf dem Pi:

```bash
sudo linuxscape-reset
sudo systemctl restart linuxscape-cscape.service
```

Dann:

1. Regie-Präsentation öffnen
2. Spieler per SSH verbinden
3. Spiel starten

---

## Diagnose

### Prüfen, ob CSCape läuft

```bash
curl http://localhost:5000/check/check_identity_confirmed
```

### Prüfen, ob Commands aufgezeichnet werden

Auf dem Pi:

```bash
python3 -m json.tool /run/linuxscape/state.json
cat /run/linuxscape/events.jsonl
```

### Prüfen, ob Spielprozesse laufen

```bash
pgrep -a -u linuxscape -f 'boogies_setlist_script|queue_worker'
```

### SSH-Logs

```bash
journalctl -u ssh -n 100 --no-pager
```

### CSCape-Logs

```bash
journalctl -u linuxscape-cscape.service -n 100 --no-pager
```

---

## Raspberry-Pi-Setup entfernen

Falls der Raspberry Pi wieder in den Zustand vor LinuxScape zurückgesetzt werden soll, kann das Skript `remove-linuxscape-setup.sh` verwendet werden.

Das Skript entfernt die LinuxScape-Spielumgebung, Services, kopierten Dateien und die Benutzer `linuxscape` und `cscape`.

Auf dem Pi in den Projektordner wechseln:
```bash
cd /pfad/zum/Projektordner/linuxscape-live
```


Ausführbar machen:

```bash
sudo chmod +x remove-linuxscape-setup.sh
```

Ausführen:

```bash
sudo ./remove-linuxscape-setup.sh
```