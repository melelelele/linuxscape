#!/usr/bin/env python3
from __future__ import annotations

import fcntl
import json
import os
import posixpath
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


STATE_DIR = Path("/run/linuxscape")
STATE_PATH = STATE_DIR / "state.json"
EVENTS_PATH = STATE_DIR / "events.jsonl"
LOCK_PATH = STATE_DIR / "state.lock"
RUN_ID_PATH = STATE_DIR / "run_id"

PARENT_SCRIPT_PATH = "/escape/opt/boogies_setlist_script.py"
WORKER_EXECUTABLE_NAMES = {
    "queue-worker-mem",
}
WORKER_PROCESS_PREFIXES = (
    "queue_worker",
    "queue-worker",
)

PLAYER_UID = os.getuid()


def read_run_id() -> str:
    try:
        run_id = RUN_ID_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return "legacy"

    return run_id or "legacy"


def load_sequence(run_id: str) -> int:
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

    if payload.get("run_id", "legacy") != run_id:
        return 0

    sequence = payload.get("sequence")

    if isinstance(sequence, int) and sequence >= 0:
        return sequence

    return 0


def read_status_uid(status_path: Path) -> int | None:
    try:
        status = status_path.read_text(
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None

    for line in status.splitlines():
        if not line.startswith("Uid:"):
            continue

        fields = line.split()

        if len(fields) < 2:
            return None

        try:
            return int(fields[1])
        except ValueError:
            return None

    return None


def read_cmdline(process_path: Path) -> list[str]:
    try:
        raw_arguments = (process_path / "cmdline").read_bytes().split(b"\0")
    except OSError:
        return []

    return [
        argument.decode(
            "utf-8",
            errors="replace",
        )
        for argument in raw_arguments
        if argument
    ]


def read_executable_name(process_path: Path) -> str:
    try:
        executable = os.readlink(process_path / "exe")
    except OSError:
        return ""

    return posixpath.basename(executable)


def read_comm(process_path: Path) -> str:
    try:
        return (process_path / "comm").read_text(
            encoding="utf-8",
            errors="replace",
        ).strip()
    except OSError:
        return ""


def parent_pid(pid: int) -> int | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None

    closing_parenthesis = stat.rfind(")")

    if closing_parenthesis < 0:
        return None

    remaining_fields = stat[closing_parenthesis + 2 :].split()

    if len(remaining_fields) < 2:
        return None

    try:
        return int(remaining_fields[1])
    except ValueError:
        return None


def own_process_tree() -> set[int]:
    excluded: set[int] = set()
    pid = os.getpid()

    while pid > 1 and pid not in excluded:
        excluded.add(pid)
        next_pid = parent_pid(pid)

        if next_pid is None:
            break

        pid = next_pid

    return excluded


def is_worker_process(
    arguments: list[str],
    executable_name: str,
    comm: str,
) -> bool:
    if executable_name in WORKER_EXECUTABLE_NAMES:
        return True

    candidates = []

    if arguments:
        candidates.append(posixpath.basename(arguments[0]))

    if comm:
        candidates.append(comm)

    return any(
        candidate.startswith(WORKER_PROCESS_PREFIXES)
        for candidate in candidates
    )


def is_parent_process(arguments: list[str]) -> bool:
    if not arguments:
        return False

    for argument in arguments[:5]:
        if not argument.startswith("/"):
            continue

        if posixpath.normpath(argument) == PARENT_SCRIPT_PATH:
            return True

    return False


def read_processes() -> tuple[list[int], list[int]]:
    worker_pids: list[int] = []
    parent_pids: list[int] = []
    excluded_pids = own_process_tree()

    try:
        process_entries = list(Path("/proc").iterdir())
    except OSError:
        return worker_pids, parent_pids

    for entry in process_entries:
        if not entry.name.isdigit():
            continue

        pid = int(entry.name)

        if pid in excluded_pids:
            continue

        real_uid = read_status_uid(entry / "status")

        if real_uid != PLAYER_UID:
            continue

        arguments = read_cmdline(entry)
        executable_name = read_executable_name(entry)
        comm = read_comm(entry)

        if is_worker_process(
            arguments,
            executable_name,
            comm,
        ):
            worker_pids.append(pid)

        if is_parent_process(arguments):
            parent_pids.append(pid)

    return (
        sorted(set(worker_pids)),
        sorted(set(parent_pids)),
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
        0o644,
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
    temporary_path: Path | None = None

    try:
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
            os.fsync(temporary_file.fileno())

            temporary_path = Path(temporary_file.name)

        os.chmod(
            temporary_path,
            0o644,
        )

        os.replace(
            temporary_path,
            STATE_PATH,
        )
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink(missing_ok=True)


def record(
    exit_code: int,
    cwd: str,
    command: str,
) -> None:
    STATE_DIR.mkdir(
        mode=0o755,
        parents=True,
        exist_ok=True,
    )

    run_id = read_run_id()
    worker_pids, parent_pids = read_processes()

    with LOCK_PATH.open(
        "a+",
        encoding="utf-8",
    ) as lock_file:
        fcntl.flock(
            lock_file.fileno(),
            fcntl.LOCK_EX,
        )

        payload = {
            "schema_version": 2,
            "run_id": run_id,
            "sequence": load_sequence(run_id) + 1,
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
