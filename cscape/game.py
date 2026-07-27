from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import pwd
import re
import shlex
from pathlib import Path
from typing import Any


STATE_DIR = Path(os.environ.get("LINUXSCAPE_STATE_DIR", "/run/linuxscape"))
STATE_PATH = STATE_DIR / "state.json"
EVENTS_PATH = STATE_DIR / "events.jsonl"
RUN_ID_PATH = STATE_DIR / "run_id"

README_PATH = "/escape/home/newbie/README.txt"
HIDDEN_HINT_PATH = "/escape/home/newbie/.queue_hint"
PARENT_SCRIPT_PATH = "/escape/opt/boogies_setlist_script.py"
SYSTEM_LOG_PATH = "/escape/home/newbie/logs/system.log"
RECORDER_PATH = "/usr/local/bin/linuxscape-record-command"

try:
    PLAYER_UID = pwd.getpwnam("linuxscape").pw_uid
except KeyError:
    PLAYER_UID = -1

READ_COMMANDS = {
    "cat",
    "less",
    "more",
    "head",
    "tail",
    "grep",
    "awk",
    "sed",
    "nano",
    "vim",
    "vi",
}

PROCESS_COMMANDS = {
    "ps",
    "pgrep",
    "pstree",
    "top",
    "htop",
}

KILL_COMMANDS = {
    "kill",
    "pkill",
    "killall",
}

ORDER = [
    "used_whoami",
    "used_pwd",
    "used_ls",
    "read_readme",
    "found_hidden_files",
    "read_hidden_hint",
    "found_queue_script",
    "read_queue_script",
    "checked_memory",
    "checked_logs",
    "used_ps",
    "children_stopped",
    "found_parent",
    "parent_stopped",
]

STEP = {name: index + 1 for index, name in enumerate(ORDER)}


class Game:
    title = "LinuxScape: Groove Rescue"

    def __init__(self) -> None:
        self._run_id = ""
        self._reset_progress()
        self._sync_run()

    def _reset_progress(self) -> None:
        self.progress_step = 0
        self._last_sequence = 0

        self._last_worker_observation: set[int] = set()
        self._last_parent_observation: set[int] = set()

        self._pending_worker_pids: set[int] | None = None
        self._pending_parent_pids: set[int] | None = None

    def _read_run_id(self) -> str:
        try:
            run_id = RUN_ID_PATH.read_text(encoding="utf-8").strip()
        except OSError:
            return "legacy"

        return run_id or "legacy"

    def _sync_run(self) -> None:
        run_id = self._read_run_id()

        if run_id == self._run_id:
            return

        previous_run_id = self._run_id
        self._run_id = run_id
        self._reset_progress()

        if previous_run_id:
            print(
                f"LinuxScape: neue Runde erkannt: {run_id}",
                flush=True,
            )

    def _load_events_after(self, sequence: int) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        try:
            with EVENTS_PATH.open("r", encoding="utf-8") as events_file:
                for line in events_file:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(event, dict):
                        continue

                    event_sequence = event.get("sequence")
                    event_run_id = event.get("run_id", "legacy")

                    if (
                        isinstance(event_sequence, int)
                        and event_sequence > sequence
                        and event_run_id == self._run_id
                    ):
                        events.append(event)
        except OSError:
            return self._load_latest_state_after(sequence)

        events.sort(key=lambda event: event["sequence"])
        return events

    def _load_latest_state_after(self, sequence: int) -> list[dict[str, Any]]:
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        if not isinstance(state, dict):
            return []

        state_sequence = state.get("sequence")
        state_run_id = state.get("run_id", "legacy")

        if (
            isinstance(state_sequence, int)
            and state_sequence > sequence
            and state_run_id == self._run_id
        ):
            return [state]

        return []

    def _refresh(self, target_step: str) -> None:
        self._sync_run()
        target_number = STEP[target_step]

        self._evaluate_pending()

        while self.progress_step < target_number:
            events = self._load_events_after(self._last_sequence)

            if not events:
                break

            for event in events:
                if self.progress_step >= target_number:
                    break

                sequence = event.get("sequence")

                if not isinstance(sequence, int):
                    continue

                self._last_sequence = sequence
                self._consume_event(event)
                self._evaluate_pending()

        self._evaluate_pending()

    def _consume_event(self, event: dict[str, Any]) -> None:
        if self.progress_step >= len(ORDER):
            return

        expected = ORDER[self.progress_step]
        command = event.get("last_command")
        cwd = event.get("cwd")
        exit_code = event.get("last_exit_code")

        if not isinstance(command, str) or not command.strip():
            return

        if not isinstance(cwd, str) or not cwd:
            cwd = "/escape/home/newbie"

        words = self._split_command(command)
        program = self._program(words)
        success = exit_code == 0

        event_workers = self._integer_set(event.get("worker_pids"))
        event_parents = self._integer_set(event.get("parent_pids"))

        if expected == "used_whoami" and success and program == "whoami":
            self._complete(expected)
            return

        if expected == "used_pwd" and success and program == "pwd":
            self._complete(expected)
            return

        if expected == "used_ls" and success and program == "ls":
            self._complete(expected)
            return

        if (
            expected == "read_readme"
            and success
            and program in READ_COMMANDS
            and self._targets_exact_path(words, cwd, README_PATH)
        ):
            self._complete(expected)
            return

        if (
            expected == "found_hidden_files"
            and success
            and self._finds_hidden_hint(program, words)
        ):
            self._complete(expected)
            return

        if (
            expected == "read_hidden_hint"
            and success
            and program in READ_COMMANDS
            and self._targets_exact_path(words, cwd, HIDDEN_HINT_PATH)
        ):
            self._complete(expected)
            return

        if (
            expected == "found_queue_script"
            and success
            and self._finds_queue_script(program, words)
        ):
            self._complete(expected)
            return

        if (
            expected == "read_queue_script"
            and success
            and program in READ_COMMANDS
            and self._targets_exact_path(words, cwd, PARENT_SCRIPT_PATH)
        ):
            self._complete(expected)
            return

        if (
            expected == "checked_memory"
            and success
            and self._checks_memory(program, words, cwd)
        ):
            self._complete(expected)
            return

        if (
            expected == "checked_logs"
            and success
            and program in READ_COMMANDS
            and self._targets_exact_path(words, cwd, SYSTEM_LOG_PATH)
        ):
            self._complete(expected)
            return

        if expected == "used_ps" and success and program in PROCESS_COMMANDS:
            if event_workers:
                self._last_worker_observation = event_workers

            if event_parents:
                self._last_parent_observation = event_parents

            self._complete(expected)
            return

        if expected == "children_stopped":
            if not self._targets_workers(program, words):
                return

            target_pids = set(self._last_worker_observation)

            if not target_pids:
                target_pids = event_workers

            if not target_pids:
                return

            self._pending_worker_pids = target_pids
            self._evaluate_pending()
            return

        if expected == "found_parent" and success and program in PROCESS_COMMANDS:
            if not event_parents:
                return

            self._last_parent_observation = event_parents
            self._complete(expected)
            return

        if expected == "parent_stopped":
            if not self._targets_parent(program, words):
                return

            target_pids = set(self._last_parent_observation)

            if not target_pids:
                target_pids = event_parents

            if not target_pids:
                return

            self._pending_parent_pids = target_pids
            self._evaluate_pending()

    def _evaluate_pending(self) -> None:
        if self.progress_step >= len(ORDER):
            return

        expected = ORDER[self.progress_step]

        if expected == "children_stopped" and self._pending_worker_pids:
            remaining = {
                pid
                for pid in self._pending_worker_pids
                if self._pid_exists(pid)
            }

            if not remaining:
                self._pending_worker_pids = None
                self._complete(expected)

        if expected == "parent_stopped" and self._pending_parent_pids:
            remaining = {
                pid
                for pid in self._pending_parent_pids
                if self._pid_exists(pid)
            }

            if not remaining and not self._find_live_parent_pids():
                self._pending_parent_pids = None
                self._complete(expected)

    def _complete(self, step: str) -> None:
        if self.progress_step >= len(ORDER):
            return

        if ORDER[self.progress_step] != step:
            return

        self.progress_step += 1
        print(
            f"LinuxScape-Fortschritt: {step}",
            flush=True,
        )

    def _pid_exists(self, pid: int) -> bool:
        return Path(f"/proc/{pid}").exists()

    def _find_live_parent_pids(self) -> set[int]:
        parent_pids: set[int] = set()

        try:
            proc_entries = list(Path("/proc").iterdir())
        except OSError:
            return parent_pids

        for entry in proc_entries:
            if not entry.name.isdigit():
                continue

            if self._read_process_uid(entry) != PLAYER_UID:
                continue

            try:
                cmdline = (entry / "cmdline").read_bytes().split(b"\0")
            except OSError:
                continue

            arguments = [
                item.decode("utf-8", errors="replace")
                for item in cmdline
                if item
            ]

            if self._is_parent_command(arguments):
                parent_pids.add(int(entry.name))

        return parent_pids

    def _read_process_uid(self, process_path: Path) -> int | None:
        try:
            status = (process_path / "status").read_text(
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

    def _is_parent_command(self, arguments: list[str]) -> bool:
        if not arguments:
            return False

        if any(
            argument == RECORDER_PATH
            for argument in arguments[:3]
        ):
            return False

        normalized = {
            posixpath.normpath(argument)
            for argument in arguments[:5]
            if argument.startswith("/")
        }

        return PARENT_SCRIPT_PATH in normalized

    def _integer_set(self, value: Any) -> set[int]:
        if not isinstance(value, list):
            return set()

        return {
            item
            for item in value
            if isinstance(item, int) and item > 0
        }

    def _split_command(self, command: str) -> list[str]:
        try:
            return shlex.split(command)
        except ValueError:
            return command.split()

    def _program(self, words: list[str]) -> str:
        if not words:
            return ""

        return posixpath.basename(words[0])

    def _finds_hidden_hint(
        self,
        program: str,
        words: list[str],
    ) -> bool:
        if program == "ls":
            return any(
                argument == "--all"
                or (
                    argument.startswith("-")
                    and not argument.startswith("--")
                    and "a" in argument[1:]
                )
                for argument in words[1:]
            )

        if program == "find":
            return self._find_name_pattern_matches(words, ".queue_hint")

        return False

    def _finds_queue_script(
        self,
        program: str,
        words: list[str],
    ) -> bool:
        if program != "find":
            return False

        target_name = posixpath.basename(PARENT_SCRIPT_PATH)
        return self._find_name_pattern_matches(words, target_name)

    def _find_name_pattern_matches(
        self,
        words: list[str],
        target_name: str,
    ) -> bool:
        for index, argument in enumerate(words[:-1]):
            if argument not in {"-name", "-iname", "-path", "-ipath"}:
                continue

            pattern = words[index + 1].strip("'\"")

            if argument in {"-name", "-iname"}:
                if fnmatch.fnmatchcase(target_name, pattern):
                    return True

                if argument == "-iname" and fnmatch.fnmatch(
                    target_name.lower(),
                    pattern.lower(),
                ):
                    return True
            else:
                if fnmatch.fnmatchcase(PARENT_SCRIPT_PATH, pattern):
                    return True

                if argument == "-ipath" and fnmatch.fnmatch(
                    PARENT_SCRIPT_PATH.lower(),
                    pattern.lower(),
                ):
                    return True

        return False

    def _checks_memory(
        self,
        program: str,
        words: list[str],
        cwd: str,
    ) -> bool:
        if program in {"free", "vmstat", "top", "htop"}:
            return True

        if program not in READ_COMMANDS:
            return False

        return any(
            self._targets_exact_path(words, cwd, path)
            for path in (
                "/proc/meminfo",
                "/sys/fs/cgroup/memory.current",
                "/sys/fs/cgroup/memory.max",
            )
        )

    def _targets_workers(
        self,
        program: str,
        words: list[str],
    ) -> bool:
        if program not in KILL_COMMANDS:
            return False

        arguments = self._non_option_arguments(words)

        if program == "kill":
            return any(
                argument.isdigit()
                and int(argument) in self._last_worker_observation
                for argument in arguments
            )

        return any(
            self._matches_worker_kill_pattern(argument)
            for argument in arguments
        )

    def _targets_parent(
        self,
        program: str,
        words: list[str],
    ) -> bool:
        if program not in KILL_COMMANDS:
            return False

        arguments = self._non_option_arguments(words)

        if program == "kill":
            return any(
                argument.isdigit()
                and int(argument) in self._last_parent_observation
                for argument in arguments
            )

        return any(
            self._matches_parent_kill_pattern(argument)
            for argument in arguments
        )

    def _matches_worker_kill_pattern(self, pattern: str) -> bool:
        normalized = pattern.lower()

        if "queue" not in normalized or "worker" not in normalized:
            return False

        return self._matches_identifier_pattern(
            pattern,
            (
                "queue_worker",
                "queue_worker_1",
                "queue-worker",
                "queue-worker-mem",
            ),
        )

    def _matches_parent_kill_pattern(self, pattern: str) -> bool:
        normalized = pattern.lower()

        if "boogie" not in normalized:
            return False

        if "setlist" not in normalized and "script" not in normalized:
            return False

        return self._matches_identifier_pattern(
            pattern,
            (
                "boogies_setlist_script",
                "boogies_setlist_script.py",
                PARENT_SCRIPT_PATH,
            ),
        )

    def _matches_identifier_pattern(
        self,
        pattern: str,
        identifiers: tuple[str, ...],
    ) -> bool:
        if pattern in identifiers:
            return True

        if any(fnmatch.fnmatchcase(identifier, pattern) for identifier in identifiers):
            return True

        try:
            expression = re.compile(pattern)
        except re.error:
            return False

        return any(
            expression.fullmatch(identifier) is not None
            for identifier in identifiers
        )

    def _targets_exact_path(
        self,
        words: list[str],
        cwd: str,
        target_path: str,
    ) -> bool:
        normalized_target = posixpath.normpath(target_path)

        for argument in words[1:]:
            if not argument or argument.startswith("-"):
                continue

            cleaned = argument.strip("'\"")

            if any(character in cleaned for character in "*?["):
                candidate_pattern = self._resolve_path(cwd, cleaned)

                if fnmatch.fnmatchcase(normalized_target, candidate_pattern):
                    return True

                continue

            candidate = self._resolve_path(cwd, cleaned)

            if candidate == normalized_target:
                return True

        return False

    def _resolve_path(self, cwd: str, argument: str) -> str:
        if argument.startswith("/"):
            return posixpath.normpath(argument)

        return posixpath.normpath(posixpath.join(cwd, argument))

    def _non_option_arguments(self, words: list[str]) -> list[str]:
        return [
            argument.strip("'\"")
            for argument in words[1:]
            if argument and not argument.startswith("-")
        ]

    def _check(self, step: str) -> bool:
        self._sync_run()

        if self.progress_step >= STEP[step]:
            return True

        if STEP[step] != self.progress_step + 1:
            return False

        self._refresh(step)
        return self.progress_step >= STEP[step]

    def check_identity_confirmed(self) -> bool:
        return self._check("used_whoami")

    def check_pwd_used(self) -> bool:
        return self._check("used_pwd")

    def check_ls_used(self) -> bool:
        return self._check("used_ls")

    def check_readme_read(self) -> bool:
        return self._check("read_readme")

    def check_hidden_files_found(self) -> bool:
        return self._check("found_hidden_files")

    def check_hidden_hint_read(self) -> bool:
        return self._check("read_hidden_hint")

    def check_queue_script_found(self) -> bool:
        return self._check("found_queue_script")

    def check_queue_script_read(self) -> bool:
        return self._check("read_queue_script")

    def check_memory_checked(self) -> bool:
        return self._check("checked_memory")

    def check_logs_checked(self) -> bool:
        return self._check("checked_logs")

    def check_ps_used(self) -> bool:
        return self._check("used_ps")

    def check_children_found(self) -> bool:
        self._refresh("used_ps")
        return (
            self.progress_step >= STEP["used_ps"]
            and bool(self._last_worker_observation)
        )

    def check_children_stopped(self) -> bool:
        return self._check("children_stopped")

    def check_parent_found(self) -> bool:
        return self._check("found_parent")

    def check_parent_stopped(self) -> bool:
        return self._check("parent_stopped")

    def check_shutdown_initiated(self) -> bool:
        return self.check_parent_stopped()


if __name__ == "__main__":
    import cscape

    cscape.run(Game())
