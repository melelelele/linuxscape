from __future__ import annotations

import fnmatch
import json
import os
import posixpath
import re
import shlex
from pathlib import Path
from typing import Any


STATE_DIR = Path(
    os.environ.get(
        "LINUXSCAPE_STATE_DIR",
        "/run/linuxscape",
    )
)

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

STEP = {
    name: index + 1
    for index, name in enumerate(ORDER)
}


class Game:
    title = "LinuxScape: Groove Rescue"

    def __init__(self) -> None:
        self.progress_step = 0
        self._last_sequence = 0
        self._run_id: str | None = None

        self._known_worker_pids: set[int] = set()
        self._known_parent_pids: set[int] = set()

        self._current_worker_pids: set[int] = set()
        self._current_parent_pids: set[int] = set()


        self._worker_snapshot_pids: set[int] = set()
        self._worker_snapshot_parent_pids: set[int] = set()
        self._worker_kill_attempted = False


        self._parent_snapshot_pids: set[int] = set()
        self._parent_kill_attempted = False

        self._refresh()

    def _reset_round_state(
        self,
        run_id: str | None = None,
    ) -> None:
        self.progress_step = 0
        self._last_sequence = 0
        self._run_id = run_id

        self._known_worker_pids.clear()
        self._known_parent_pids.clear()

        self._current_worker_pids.clear()
        self._current_parent_pids.clear()

        self._worker_snapshot_pids.clear()
        self._worker_snapshot_parent_pids.clear()
        self._worker_kill_attempted = False

        self._parent_snapshot_pids.clear()
        self._parent_kill_attempted = False

        print(
            "LinuxScape: neue Spielrunde erkannt",
            flush=True,
        )

    def _read_latest_state(
        self,
    ) -> dict[str, Any] | None:
        try:
            state = json.loads(
                STATE_PATH.read_text(
                    encoding="utf-8",
                )
            )
        except (
            OSError,
            json.JSONDecodeError,
        ):
            return None

        if not isinstance(state, dict):
            return None

        return state

    def _detect_round_reset(self) -> None:
        state = self._read_latest_state()

        if state is None:
            return

        sequence = state.get("sequence")
        run_id = state.get("run_id")

        normalized_run_id = (
            run_id
            if isinstance(run_id, str) and run_id
            else None
        )

        if (
            self._run_id is None
            and normalized_run_id is not None
        ):
            self._run_id = normalized_run_id

        elif (
            normalized_run_id is not None
            and self._run_id is not None
            and normalized_run_id != self._run_id
        ):
            self._reset_round_state(
                normalized_run_id,
            )
            return


        if (
            isinstance(sequence, int)
            and sequence >= 0
            and sequence < self._last_sequence
        ):
            self._reset_round_state(
                normalized_run_id,
            )

    def _load_events_after(
        self,
        sequence: int,
    ) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        try:
            with EVENTS_PATH.open(
                "r",
                encoding="utf-8",
            ) as events_file:
                for line in events_file:
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if not isinstance(event, dict):
                        continue

                    event_sequence = event.get(
                        "sequence",
                    )

                    if (
                        isinstance(event_sequence, int)
                        and event_sequence > sequence
                    ):
                        events.append(event)

        except OSError:
            return self._load_latest_state_after(
                sequence,
            )

        events.sort(
            key=lambda event: event["sequence"],
        )

        return events

    def _load_latest_state_after(
        self,
        sequence: int,
    ) -> list[dict[str, Any]]:
        state = self._read_latest_state()

        if state is None:
            return []

        state_sequence = state.get("sequence")

        if (
            isinstance(state_sequence, int)
            and state_sequence > sequence
        ):
            return [state]

        return []

    def _refresh(self) -> None:
        self._detect_round_reset()

        events = self._load_events_after(
            self._last_sequence,
        )

        for event in events:
            sequence = event.get("sequence")

            if not isinstance(sequence, int):
                continue

            event_run_id = event.get("run_id")

            if (
                isinstance(event_run_id, str)
                and event_run_id
            ):
                if self._run_id is None:
                    self._run_id = event_run_id

                elif event_run_id != self._run_id:
                    self._reset_round_state(
                        event_run_id,
                    )

            self._last_sequence = max(
                self._last_sequence,
                sequence,
            )

            self._remember_processes(event)
            self._consume_event(event)

    def _remember_processes(
        self,
        event: dict[str, Any],
    ) -> None:
        worker_pids = set(
            self._integer_list(
                event.get("worker_pids"),
            )
        )

        parent_pids = set(
            self._integer_list(
                event.get("parent_pids"),
            )
        )

        self._current_worker_pids = worker_pids
        self._current_parent_pids = parent_pids

        self._known_worker_pids.update(
            worker_pids,
        )

        self._known_parent_pids.update(
            parent_pids,
        )

    def _consume_event(
        self,
        event: dict[str, Any],
    ) -> None:
        command = event.get("last_command")
        cwd = event.get("cwd")
        exit_code = event.get("last_exit_code")

        if (
            not isinstance(command, str)
            or not command.strip()
        ):
            return

        if not isinstance(cwd, str) or not cwd:
            cwd = "/escape/home/newbie"

        words = self._split_command(command)
        program = self._program(words)


        self._try_complete_worker_stop()
        self._try_complete_parent_stop()

        if exit_code != 0:
            return

        while self.progress_step < len(ORDER):
            expected = ORDER[
                self.progress_step
            ]

            completed = False

            if expected == "used_whoami":
                completed = (
                    program == "whoami"
                )

            elif expected == "used_pwd":
                completed = (
                    program == "pwd"
                )

            elif expected == "used_ls":
                completed = (
                    program == "ls"
                )

            elif expected == "read_readme":
                completed = (
                    program in READ_COMMANDS
                    and self._targets_path(
                        words,
                        cwd,
                        README_PATH,
                    )
                )

            elif expected == "found_hidden_files":
                completed = self._finds_hidden_hint(
                    program,
                    words,
                    command,
                )

            elif expected == "read_hidden_hint":
                completed = (
                    program in READ_COMMANDS
                    and self._targets_path(
                        words,
                        cwd,
                        HIDDEN_HINT_PATH,
                    )
                )

            elif expected == "found_queue_script":
                completed = (
                    self._finds_queue_script(
                        program,
                        words,
                        command,
                    )
                )

            elif expected == "read_queue_script":
                completed = (
                    program in READ_COMMANDS
                    and self._targets_path(
                        words,
                        cwd,
                        PARENT_SCRIPT_PATH,
                    )
                )

            elif expected == "checked_memory":
                completed = (
                    self._checks_memory(
                        program,
                        words,
                        cwd,
                    )
                )

            elif expected == "checked_logs":
                completed = (
                    program in READ_COMMANDS
                    and self._targets_path(
                        words,
                        cwd,
                        SYSTEM_LOG_PATH,
                    )
                )

            elif expected == "used_ps":
                completed = (
                    program in PROCESS_COMMANDS
                )

                if completed:

                    self._worker_snapshot_pids = set(
                        self._current_worker_pids,
                    )

                    self._worker_snapshot_parent_pids = set(
                        self._current_parent_pids,
                    )

            elif expected == "children_stopped":
                if (
                    program in KILL_COMMANDS
                    and self._targets_workers(
                        program,
                        words,
                    )
                ):
                    self._worker_kill_attempted = True

                completed = (
                    self._worker_generation_was_stopped()
                )

            elif expected == "found_parent":
                completed = (
                    program in PROCESS_COMMANDS
                    and bool(
                        self._current_parent_pids
                    )
                )

                if completed:
                    self._parent_snapshot_pids = set(
                        self._current_parent_pids,
                    )

            elif expected == "parent_stopped":
                if (
                    program in KILL_COMMANDS
                    and self._targets_parent(
                        program,
                        words,
                    )
                ):
                    self._parent_kill_attempted = True

                completed = (
                    self._parent_was_stopped()
                )

            if not completed:
                break

            self._advance(expected)


            if expected != "children_stopped":
                break

    def _advance(
        self,
        step: str,
    ) -> None:
        self.progress_step = STEP[step]

        print(
            f"LinuxScape-Fortschritt: {step}",
            flush=True,
        )

    def _try_complete_worker_stop(
        self,
    ) -> None:
        if (
            self.progress_step + 1
            != STEP["children_stopped"]
        ):
            return

        if self._worker_generation_was_stopped():
            self._advance(
                "children_stopped",
            )

    def _try_complete_parent_stop(
        self,
    ) -> None:
        if (
            self.progress_step + 1
            != STEP["parent_stopped"]
        ):
            return

        if self._parent_was_stopped():
            self._advance(
                "parent_stopped",
            )

    def _worker_generation_was_stopped(
        self,
    ) -> bool:
        if not self._worker_kill_attempted:
            return False

        if not self._worker_snapshot_pids:
            return False


        previous_workers_gone = (
            self._worker_snapshot_pids.isdisjoint(
                self._current_worker_pids,
            )
        )


        if self._worker_snapshot_parent_pids:
            same_parent_survived = bool(
                self._worker_snapshot_parent_pids.intersection(
                    self._current_parent_pids,
                )
            )
        else:
            same_parent_survived = bool(
                self._current_parent_pids
            )

        if not (
            previous_workers_gone
            and same_parent_survived
        ):
            return False

        print(
            "LinuxScape: alte Worker-Generation gestoppt; "
            f"alt={sorted(self._worker_snapshot_pids)} "
            f"neu={sorted(self._current_worker_pids)} "
            f"parent={sorted(self._current_parent_pids)}",
            flush=True,
        )

        return True

    def _parent_was_stopped(
        self,
    ) -> bool:
        if not self._parent_kill_attempted:
            return False

        if not self._parent_snapshot_pids:
            return False

        return self._parent_snapshot_pids.isdisjoint(
            self._current_parent_pids,
        )

    def _targets_workers(
        self,
        program: str,
        words: list[str],
    ) -> bool:
        arguments = self._non_option_arguments(
            words,
        )

        if program == "kill":
            return any(
                argument.isdigit()
                and int(argument)
                in self._worker_snapshot_pids
                for argument in arguments
            )

        return any(
            self._selector_matches_worker(
                argument,
            )
            for argument in arguments
        )

    def _targets_parent(
        self,
        program: str,
        words: list[str],
    ) -> bool:
        arguments = self._non_option_arguments(
            words,
        )

        if program == "kill":
            return any(
                argument.isdigit()
                and int(argument)
                in self._parent_snapshot_pids
                for argument in arguments
            )

        return any(
            self._selector_matches_parent(
                argument,
            )
            for argument in arguments
        )

    def _selector_matches_worker(
        self,
        selector: str,
    ) -> bool:
        selector = selector.strip("'\"")

        if not selector:
            return False


        targets = (
            "queue_worker_example_00",
            "queue-worker-example-00",
            "/usr/local/bin/queue-worker-mem",
        )

        return any(
            self._safe_regex_search(
                selector,
                target,
            )
            for target in targets
        )

    def _selector_matches_parent(
        self,
        selector: str,
    ) -> bool:
        selector = selector.strip("'\"")

        if not selector:
            return False

        targets = (
            "boogies_setlist_script.py",
            PARENT_SCRIPT_PATH,
            f"python3 {PARENT_SCRIPT_PATH}",
        )

        return any(
            self._safe_regex_search(
                selector,
                target,
            )
            for target in targets
        )

    def _safe_regex_search(
        self,
        pattern: str,
        target: str,
    ) -> bool:
        try:
            return (
                re.search(
                    pattern,
                    target,
                )
                is not None
            )
        except re.error:
            return (
                fnmatch.fnmatch(
                    target,
                    pattern,
                )
                or pattern in target
            )

    def _integer_list(
        self,
        value: Any,
    ) -> list[int]:
        if not isinstance(value, list):
            return []

        return [
            item
            for item in value
            if isinstance(item, int)
        ]

    def _split_command(
        self,
        command: str,
    ) -> list[str]:
        try:
            return shlex.split(command)
        except ValueError:
            return command.split()

    def _program(
        self,
        words: list[str],
    ) -> str:
        if not words:
            return ""

        return posixpath.basename(
            words[0],
        )

    def _finds_hidden_hint(
        self,
        program: str,
        words: list[str],
        command: str,
    ) -> bool:
        if program == "find":
            return self._any_pattern_matches(
                words,
                ".queue_hint",
            )

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

        return False

    def _finds_queue_script(
        self,
        program: str,
        words: list[str],
        command: str,
    ) -> bool:
        if program != "find":
            return False

        target_name = posixpath.basename(
            PARENT_SCRIPT_PATH,
        )

        if self._any_pattern_matches(
            words,
            target_name,
        ):
            return True

        return (
            "boogies" in command
            and "setlist" in command
            and (
                ".py" in command
                or "script" in command
            )
        )

    def _checks_memory(
        self,
        program: str,
        words: list[str],
        cwd: str,
    ) -> bool:
        if program in {
            "free",
            "vmstat",
            "top",
            "htop",
        }:
            return True

        if program not in READ_COMMANDS:
            return False

        return any(
            self._targets_path(
                words,
                cwd,
                path,
            )
            for path in (
                "/proc/meminfo",
                "/sys/fs/cgroup/memory.current",
                "/sys/fs/cgroup/memory.max",
            )
        )

    def _targets_path(
        self,
        words: list[str],
        cwd: str,
        target_path: str,
    ) -> bool:
        target_path = posixpath.normpath(
            target_path,
        )

        target_name = posixpath.basename(
            target_path,
        )

        for argument in words[1:]:
            if (
                not argument
                or argument.startswith("-")
            ):
                continue

            cleaned = argument.strip("'\"")

            candidate = self._resolve_path(
                cwd,
                cleaned,
            )

            if candidate == target_path:
                return True


            if fnmatch.fnmatch(
                target_path,
                candidate,
            ):
                return True

            if fnmatch.fnmatch(
                target_name,
                cleaned,
            ):
                return True

        return False

    def _resolve_path(
        self,
        cwd: str,
        argument: str,
    ) -> str:
        if argument.startswith("/"):
            return posixpath.normpath(
                argument,
            )

        return posixpath.normpath(
            posixpath.join(
                cwd,
                argument,
            )
        )

    def _non_option_arguments(
        self,
        words: list[str],
    ) -> list[str]:
        return [
            argument.strip("'\"")
            for argument in words[1:]
            if (
                argument
                and not argument.startswith("-")
            )
        ]

    def _any_pattern_matches(
        self,
        words: list[str],
        target: str,
    ) -> bool:
        return any(
            (
                self._safe_regex_search(
                    word.strip("'\""),
                    target,
                )
                or fnmatch.fnmatch(
                    target,
                    word.strip("'\""),
                )
            )
            for word in words[1:]
            if (
                word
                and not word.startswith("-")
            )
        )

    def _has_reached(
        self,
        step: str,
    ) -> bool:
        return (
            self.progress_step
            >= STEP[step]
        )

    def check_identity_confirmed(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "used_whoami",
        )

    def check_pwd_used(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "used_pwd",
        )

    def check_ls_used(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "used_ls",
        )

    def check_readme_read(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "read_readme",
        )

    def check_hidden_files_found(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "found_hidden_files",
        )

    def check_hidden_hint_read(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "read_hidden_hint",
        )

    def check_queue_script_found(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "found_queue_script",
        )

    def check_queue_script_read(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "read_queue_script",
        )

    def check_memory_checked(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "checked_memory",
        )

    def check_logs_checked(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "checked_logs",
        )

    def check_ps_used(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "used_ps",
        )

    def check_children_found(
        self,
    ) -> bool:
        self._refresh()

        return (
            self._has_reached(
                "used_ps",
            )
            and bool(
                self._worker_snapshot_pids
            )
        )

    def check_children_stopped(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "children_stopped",
        )

    def check_parent_found(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "found_parent",
        )

    def check_parent_stopped(
        self,
    ) -> bool:
        self._refresh()

        return self._has_reached(
            "parent_stopped",
        )

    def check_shutdown_initiated(
        self,
    ) -> bool:
        return self.check_parent_stopped()


if __name__ == "__main__":
    import cscape

    cscape.run(
        Game(),
    )