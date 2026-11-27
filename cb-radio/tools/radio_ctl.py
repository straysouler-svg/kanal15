#!/usr/bin/env python3
"""Безопасный контроль процесса рации «Канал 15» по порту 47823."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

RADIO_PORT = 47823
REPO_ROOT = Path(__file__).resolve().parents[2]


def get_port_listeners(port: int) -> list[int]:
    """Возвращает уникальные PID процессов, слушающих указанный TCP-порт."""
    pids = set()
    try:
        out = subprocess.check_output(
            ["netstat", "-ano", "-p", "TCP"],
            text=True,
            encoding="cp866",
            errors="replace",
        )
        target = f":{port}"
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 5 and parts[0] == "TCP" and parts[3] == "LISTENING":
                if parts[1].endswith(target):
                    try:
                        pid = int(parts[4])
                        if pid > 0:
                            pids.add(pid)
                    except ValueError:
                        pass
    except Exception as exc:
        print(f"ERROR: netstat failed: {exc}", file=sys.stderr)
    return sorted(pids)


def get_process_tree_info(pids: list[int]) -> list[dict]:
    """Получает имя, командную строку и ParentProcessId для списка PID."""
    if not pids:
        return []
    filter_expr = " or ".join(f"ProcessId={p}" for p in pids)
    ps_cmd = (
        f"Get-CimInstance Win32_Process -Filter '{filter_expr}' | "
        "Select-Object ProcessId,ParentProcessId,Name,CommandLine | ConvertTo-Json -Compress"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", ps_cmd],
            text=True,
            encoding="utf-8",
            errors="replace",
        ).strip()
        if not out:
            return []
        data = json.loads(out)
        return [data] if isinstance(data, dict) else data
    except Exception:
        return [{"ProcessId": p} for p in pids]


def check_dirty_radio_source() -> list[str]:
    """Проверяет, есть ли незакоммиченные правки в исходниках рации."""
    try:
        out = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain", "cb-radio/"],
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        dirty = []
        for line in out.splitlines():
            path = line[3:].strip()
            if path.endswith((".py", ".json")) and not path.startswith("cb-radio/sim/"):
                dirty.append(line.strip())
        return dirty
    except Exception:
        return []


def cmd_status() -> int:
    listeners = get_port_listeners(RADIO_PORT)
    proc_info = get_process_tree_info(listeners)
    dirty_files = check_dirty_radio_source()

    if len(listeners) == 0:
        state = "STOPPED"
    elif len(listeners) == 1:
        state = "RUNNING_OK"
    else:
        state = "DUPLICATE_DETECTED"

    result = {
        "state": state,
        "port": RADIO_PORT,
        "listener_pids": listeners,
        "processes": proc_info,
        "dirty_source_files": dirty_files,
        "warning": (
            "ВНИМАНИЕ: в cb-radio/ есть незакоммиченные правки — запускать только собранный CB-Radio.exe!"
            if dirty_files
            else None
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if state == "DUPLICATE_DETECTED" else 0


def cmd_stop(force_all: bool) -> int:
    listeners = get_port_listeners(RADIO_PORT)
    if not listeners:
        print("Рация не запущена (порт 47823 свободен).")
        return 0

    if len(listeners) == 1 and not force_all:
        print(
            f"Активен ровно 1 экземпляр рации (PID {listeners[0]}). "
            "Дублей нет. Для принудительной остановки передайте --force."
        )
        return 0

    targets = listeners if force_all else listeners[1:]
    info = get_process_tree_info(targets)
    pids_to_kill = set(targets)
    for item in info:
        ppid = item.get("ParentProcessId")
        if ppid:
            parent_info = get_process_tree_info([ppid])
            for p in parent_info:
                if str(p.get("Name", "")).lower() in ("pythonw.exe", "python.exe"):
                    pids_to_kill.add(ppid)

    for pid in sorted(pids_to_kill):
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
        print(f"Остановлен процесс PID {pid}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Управление процессами рации Канал 15")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="Проверить статус и наличие реальных дублей по порту 47823")
    p_stop = sub.add_parser("stop", help="Остановить дубли или активную рацию")
    p_stop.add_argument("--force", action="store_true", help="Остановить даже единственный живой экземпляр")

    args = parser.parse_args()
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "stop":
        return cmd_stop(args.force)
    return 1


if __name__ == "__main__":
    sys.exit(main())