#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


STATE_DIR = Path("/run/linuxscape")
STATE_PATH = STATE_DIR / "state.json"
EVENTS_PATH = STATE_DIR / "events.jsonl"
LOCK_PATH = STATE_DIR / "state.lock"

PLAYER_UID = os.getuid()


def load_sequence() -> int:
    try:
        payload = json.loads(
            STATE_PATH.read_text(
                encoding="utf-8",
            )
        )
    except (OSError, json.JSONDecodeError):
        return 0

    if not isinstance(payload, dict):
        return 0

    sequence = payload.get("sequence")

    if (
        isinstance(sequence, int)
        and sequence >= 0
    ):
        return sequence

    return 0


def read_processes() -> tuple[list[int], list[int]]:
    worker_pids: list[int] = []
    parent_pids: list[int] = []

    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue

        try:
            status = (
                entry / "status"
            ).read_text(
                encoding="utf-8",
                errors="replace",
            )

            uid_line = next(
                line
                for line in status.splitlines()
                if line.startswith("Uid:")
            )

            real_uid = int(
                uid_line.split()[1]
            )

            if real_uid != PLAYER_UID:
                continue

            cmdline = (
                (entry / "cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode(
                    "utf-8",
                    errors="replace",
                )
            )
        except (
            OSError,
            StopIteration,
            ValueError,
        ):
            continue

        pid = int(entry.name)

        if "queue_worker" in cmdline:
            worker_pids.append(pid)

        if "boogies_setlist_script.py" in cmdline:
            parent_pids.append(pid)

    return (
        sorted(worker_pids),
        sorted(parent_pids),
    )


def append_event(
    payload: dict[str, Any],
) -> None:
    encoded = (
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")

    descriptor = os.open(
        EVENTS_PATH,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_APPEND,
        0o666,
    )

    try:
        os.write(
            descriptor,
            encoded,
        )
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_latest_state(
    payload: dict[str, Any],
) -> None:
    with NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=STATE_DIR,
        prefix=".state-",
        suffix=".json",
        delete=False,
    ) as temporary_file:
        json.dump(
            payload,
            temporary_file,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        temporary_file.write("\n")
        temporary_file.flush()

        os.fsync(
            temporary_file.fileno()
        )

        temporary_path = Path(
            temporary_file.name
        )

    os.chmod(
        temporary_path,
        0o666,
    )

    os.replace(
        temporary_path,
        STATE_PATH,
    )


def record(
    exit_code: int,
    cwd: str,
    command: str,
) -> None:
    STATE_DIR.mkdir(
        mode=0o777,
        parents=True,
        exist_ok=True,
    )

    worker_pids, parent_pids = (
        read_processes()
    )

    with LOCK_PATH.open(
        "a+",
        encoding="utf-8",
    ) as lock_file:
        fcntl.flock(
            lock_file.fileno(),
            fcntl.LOCK_EX,
        )

        payload = {
            "sequence": load_sequence() + 1,
            "updated_at": (
                datetime.now(timezone.utc)
                .isoformat()
            ),
            "last_command": command,
            "last_exit_code": exit_code,
            "cwd": cwd,
            "worker_pids": worker_pids,
            "worker_count": len(worker_pids),
            "parent_pids": parent_pids,
            "parent_count": len(parent_pids),
        }

        append_event(payload)
        write_latest_state(payload)


def main() -> int:
    if len(sys.argv) != 4:
        print(
            "Verwendung: "
            "linuxscape-record-command "
            "EXIT_CODE CWD COMMAND",
            file=sys.stderr,
        )
        return 2

    try:
        exit_code = int(sys.argv[1])
    except ValueError:
        print(
            "EXIT_CODE muss eine Zahl sein.",
            file=sys.stderr,
        )
        return 2

    command = sys.argv[3].strip()

    if not command:
        return 0

    record(
        exit_code=exit_code,
        cwd=sys.argv[2],
        command=command,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
