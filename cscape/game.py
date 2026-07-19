from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import re
import shlex
from pathlib import Path
from typing import Any


STATE_DIR = Path(os.environ.get("LINUXSCAPE_STATE_DIR", "/run/linuxscape"))
STATE_PATH = STATE_DIR / "state.json"
EVENTS_PATH = STATE_DIR / "events.jsonl"

README_PATH = "/escape/home/newbie/README.txt"
HIDDEN_HINT_PATH = "/escape/home/newbie/.queue_hint"
PARENT_SCRIPT_PATH = "/escape/opt/boogies_setlist_script.py"
SYSTEM_LOG_PATH = "/escape/home/newbie/logs/system.log"

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
        self.progress_step = 0
        self._last_sequence = 0

        self._facts: set[str] = set()
        self._known_worker_pids: set[int] = set()
        self._known_parent_pids: set[int] = set()

        self._latest_worker_count: int | None = None
        self._latest_parent_count: int | None = None

        self._refresh()

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

                    if isinstance(event_sequence, int) and event_sequence > sequence:
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

        if isinstance(state_sequence, int) and state_sequence > sequence:
            return [state]

        return []

    def _refresh(self) -> None:
        for event in self._load_events_after(self._last_sequence):
            sequence = event.get("sequence")

            if not isinstance(sequence, int):
                continue

            self._last_sequence = max(self._last_sequence, sequence)
            self._remember_processes(event)
            self._collect_facts(event)

        self._advance_as_far_as_possible()

    def _remember_processes(self, event: dict[str, Any]) -> None:
        self._known_worker_pids.update(self._integer_list(event.get("worker_pids")))
        self._known_parent_pids.update(self._integer_list(event.get("parent_pids")))

        worker_count = self._count(event, "worker_count")
        parent_count = self._count(event, "parent_count")

        if worker_count is not None:
            self._latest_worker_count = worker_count

        if parent_count is not None:
            self._latest_parent_count = parent_count

    def _collect_facts(self, event: dict[str, Any]) -> None:
        if event.get("last_exit_code") != 0:
            return

        command = event.get("last_command")
        cwd = event.get("cwd")

        if not isinstance(command, str) or not command.strip():
            return

        if not isinstance(cwd, str) or not cwd:
            cwd = "/escape/home/newbie"

        words = self._split_command(command)
        program = self._program(words)

        worker_count = self._count(event, "worker_count")
        parent_count = self._count(event, "parent_count")

        if program == "whoami":
            self._facts.add("used_whoami")

        if program == "pwd":
            self._facts.add("used_pwd")

        if program == "ls":
            self._facts.add("used_ls")

        if program in READ_COMMANDS and self._targets_path(words, cwd, README_PATH):
            self._facts.add("read_readme")

        if self._finds_hidden_hint(program, words, command):
            self._facts.add("found_hidden_files")

        if program in READ_COMMANDS and self._targets_path(words, cwd, HIDDEN_HINT_PATH):
            self._facts.add("read_hidden_hint")

        if self._finds_queue_script(program, words, command):
            self._facts.add("found_queue_script")

        if program in READ_COMMANDS and self._targets_path(words, cwd, PARENT_SCRIPT_PATH):
            self._facts.add("read_queue_script")

        if self._checks_memory(program, words, cwd):
            self._facts.add("checked_memory")

        if program in READ_COMMANDS and self._targets_path(words, cwd, SYSTEM_LOG_PATH):
            self._facts.add("checked_logs")

        if program in PROCESS_COMMANDS:
            self._facts.add("used_ps")

        if program in PROCESS_COMMANDS and parent_count is not None and parent_count > 0:
            self._facts.add("found_parent")

        if self._targets_workers(program, words, command):
            self._facts.add("targeted_workers")

        if self._targets_parent(program, words, command):
            self._facts.add("targeted_parent")

        if (
                "targeted_workers" in self._facts
                and worker_count is not None
                and worker_count <= 1
        ):
            self._facts.add("children_stopped")

        if (
                "targeted_parent" in self._facts
                and parent_count is not None
                and parent_count == 0
        ):
            self._facts.add("parent_stopped")

    def _advance_as_far_as_possible(self) -> None:
        while self.progress_step < len(ORDER):
            expected = ORDER[self.progress_step]

            if expected not in self._facts:
                break

            self.progress_step = STEP[expected]
            print(f"LinuxScape-Fortschritt: {expected}", flush=True)

    def _has_reached(self, step: str) -> bool:
        return self.progress_step >= STEP[step]

    def _integer_list(self, value: Any) -> list[int]:
        if not isinstance(value, list):
            return []

        return [item for item in value if isinstance(item, int)]

    def _count(self, event: dict[str, Any], key: str) -> int | None:
        value = event.get(key)

        if isinstance(value, int) and value >= 0:
            return value

        return None

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
            command: str,
    ) -> bool:
        if ".queue_hint" in command:
            return True

        if program == "find":
            return self._any_pattern_matches(words, ".queue_hint")

        if program != "ls":
            return False

        return any(
            argument == "--all"
            or (
                    argument.startswith("-")
                    and not argument.startswith("--")
                    and "a" in argument[1:]
            )
            for argument in words[1:]
        )

    def _finds_queue_script(
            self,
            program: str,
            words: list[str],
            command: str,
    ) -> bool:
        target_name = posixpath.basename(PARENT_SCRIPT_PATH)

        if target_name in command:
            return True

        if program != "find":
            return False

        if self._any_pattern_matches(words, target_name):
            return True

        return (
                "boogies" in command
                and "setlist" in command
                and (".py" in command or "script" in command)
        )

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
            self._targets_path(words, cwd, path)
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
            command: str,
    ) -> bool:
        if program not in KILL_COMMANDS:
            return False

        if self._command_mentions_worker(command):
            return True

        arguments = self._non_option_arguments(words)

        if program == "kill":
            return any(
                argument.isdigit() and int(argument) in self._known_worker_pids
                for argument in arguments
            )

        return False

    def _targets_parent(
            self,
            program: str,
            words: list[str],
            command: str,
    ) -> bool:
        if program not in KILL_COMMANDS:
            return False

        if self._command_mentions_parent(command):
            return True

        arguments = self._non_option_arguments(words)

        if program == "kill":
            return any(
                argument.isdigit() and int(argument) in self._known_parent_pids
                for argument in arguments
            )

        return False

    def _command_mentions_worker(self, command: str) -> bool:
        return self._pattern_matches_any(
            command,
            (
                "queue_worker",
                "queue-worker",
                "queue.*worker",
                "worker",
            ),
        )

    def _command_mentions_parent(self, command: str) -> bool:
        return self._pattern_matches_any(
            command,
            (
                "boogies_setlist_script.py",
                "boogies_setlist_script",
                "boogies.*setlist.*script",
                "boogies.*script",
                "setlist.*script",
            ),
        )

    def _targets_path(
            self,
            words: list[str],
            cwd: str,
            target_path: str,
    ) -> bool:
        target_path = posixpath.normpath(target_path)
        target_name = posixpath.basename(target_path)

        for argument in words[1:]:
            if not argument or argument.startswith("-"):
                continue

            cleaned = argument.strip("'\"")

            candidate = self._resolve_path(cwd, cleaned)

            if candidate == target_path:
                return True

            if self._path_is_parent_of(candidate, target_path):
                return True

            if self._pattern_matches(cleaned, target_path):
                return True

            if self._pattern_matches(cleaned, target_name):
                return True

        return False

    def _resolve_path(self, cwd: str, argument: str) -> str:
        if argument.startswith("/"):
            return posixpath.normpath(argument)

        return posixpath.normpath(posixpath.join(cwd, argument))

    def _path_is_parent_of(self, candidate: str, target_path: str) -> bool:
        candidate = posixpath.normpath(candidate)
        target_path = posixpath.normpath(target_path)

        if candidate == "/":
            return False

        return target_path.startswith(candidate.rstrip("/") + "/")

    def _non_option_arguments(self, words: list[str]) -> list[str]:
        return [
            argument.strip("'\"")
            for argument in words[1:]
            if argument and not argument.startswith("-")
        ]

    def _any_pattern_matches(self, words: list[str], target: str) -> bool:
        return any(self._pattern_matches(word.strip("'\""), target) for word in words[1:])

    def _pattern_matches_any(self, text: str, patterns: tuple[str, ...]) -> bool:
        return any(self._pattern_matches(pattern, text) for pattern in patterns)

    def _pattern_matches(self, pattern: str, target: str) -> bool:
        pattern = pattern.strip("'\"")
        target = target.strip("'\"")

        if not pattern or not target:
            return False

        if pattern == target:
            return True

        if pattern in target:
            return True

        if target in pattern:
            return True

        if fnmatch.fnmatch(target, pattern):
            return True

        try:
            if re.search(pattern, target):
                return True
        except re.error:
            pass

        return False

    def check_identity_confirmed(self) -> bool:
        self._refresh()
        return self._has_reached("used_whoami")

    def check_pwd_used(self) -> bool:
        self._refresh()
        return self._has_reached("used_pwd")

    def check_ls_used(self) -> bool:
        self._refresh()
        return self._has_reached("used_ls")

    def check_readme_read(self) -> bool:
        self._refresh()
        return self._has_reached("read_readme")

    def check_hidden_files_found(self) -> bool:
        self._refresh()
        return self._has_reached("found_hidden_files")

    def check_hidden_hint_read(self) -> bool:
        self._refresh()
        return self._has_reached("read_hidden_hint")

    def check_queue_script_found(self) -> bool:
        self._refresh()
        return self._has_reached("found_queue_script")

    def check_queue_script_read(self) -> bool:
        self._refresh()
        return self._has_reached("read_queue_script")

    def check_memory_checked(self) -> bool:
        self._refresh()
        return self._has_reached("checked_memory")

    def check_logs_checked(self) -> bool:
        self._refresh()
        return self._has_reached("checked_logs")

    def check_ps_used(self) -> bool:
        self._refresh()
        return self._has_reached("used_ps")

    def check_children_found(self) -> bool:
        self._refresh()
        return self._has_reached("used_ps") and bool(self._known_worker_pids)

    def check_children_stopped(self) -> bool:
        self._refresh()
        return self._has_reached("children_stopped")

    def check_parent_found(self) -> bool:
        self._refresh()
        return self._has_reached("found_parent")

    def check_parent_stopped(self) -> bool:
        self._refresh()
        return self._has_reached("parent_stopped")

    def check_shutdown_initiated(self) -> bool:
        return self.check_parent_stopped()


if __name__ == "__main__":
    import cscape

    cscape.run(Game())
