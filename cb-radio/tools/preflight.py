#!/usr/bin/env python3
"""Предстримовая проверка «Канала 15» (инциденты 15.11):
1. Пилотные флаги в config.json: какие pilot-ключи включены, какие из них выключены в дефолте.
2. Грязный код + рация из исходников = СТРИМ ИЗ ГРЯЗНЫХ ИСХОДНИКОВ.
Телеметрию не проверяет — это отдельное правило по логам рации.
Запуск из корня репо или из cb-radio/: python tools/preflight.py
Код возврата: 0 — ок, 1 — есть предупреждения."""
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CB = os.path.join(ROOT, "cb-radio")
CFG = os.path.join(CB, "config.json")
CB_RADIO = os.path.join(CB, "cb_radio.py")
CORE = ("cb_radio.py", "intents.py", "bonds.py")


def load_pilot_defaults():
    """pilot-ключи из DEFAULT_CFG в cb_radio.py: {key: default}."""
    src = open(CB_RADIO, encoding="utf-8").read()
    m = re.search(r"DEFAULT_CFG\s*=\s*\{(.*?)\n\}", src, re.S)
    if not m:
        return {}
    out = {}
    for km in re.finditer(r"""['"]([a-zA-Z0-9_]*pilot[a-zA-Z0-9_]*)['"]\s*:\s*(True|False)""",
                          m.group(1), re.I):
        out[km.group(1)] = km.group(2) == "True"
    return out


def check_pilots():
    warns = 0
    defaults = load_pilot_defaults()
    if not os.path.exists(CFG):
        print("КОНФИГ: cb-radio/config.json не найден — будут дефолты.")
        return 0
    cfg = json.loads(open(CFG, encoding="utf-8-sig").read())
    on = sorted(k for k in cfg if "pilot" in k.lower() and cfg[k])
    if not on:
        print("ПИЛОТЫ: включённых pilot-флагов нет.")
        return 0
    print("ПИЛОТЫ: включены — " + ", ".join(on))
    for k in on:
        if k in defaults and not defaults[k]:
            print(f"  ПИЛОТ ВКЛЮЧЁН: {k} (в дефолте False) — код под этим флагом непроверен для эфира")
            warns += 1
        elif k not in defaults:
            print(f"  ? {k} есть в конфиге, но не в DEFAULT_CFG — проверь опечатку")
            warns += 1
    return warns


def dirty_core():
    r = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True)
    dirty = []
    for line in r.stdout.splitlines():
        path = line[3:].strip().strip('"')
        if not path.startswith("cb-radio/"):
            continue
        base = os.path.basename(path)
        if base in CORE and line[:2] != "??" and line[:2].strip():
            if base not in [d[0] for d in dirty]:
                dirty.append((base, line[:2].strip()))
    return dirty


def radio_from_sources():
    cmd = ["powershell", "-NoProfile", "-Command",
           "Get-CimInstance Win32_Process -Filter \"Name='python.exe' or Name='pythonw.exe'\" "
           "| Select-Object ProcessId,CommandLine | ConvertTo-Json"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    out = r.stdout.strip()
    if not out:
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        data = [data]
    return [p["ProcessId"] for p in data
            if p.get("CommandLine") and "cb_radio.py" in p["CommandLine"]]


def check_dirty():
    dirty = dirty_core()
    if dirty:
        print("КОД: незакоммиченные изменения ядра: "
              + ", ".join(f"{b} [{s}]" for b, s in dirty))
    else:
        print("КОД: cb_radio.py / intents.py / bonds.py — чисто (коммичены).")
    try:
        pids = radio_from_sources()
    except Exception as e:
        print(f"  ? не удалось опросить процессы: {e}")
        return 1 if dirty else 0
    if pids:
        print(f"РАЦИЯ: запущена из исходников (pid {', '.join(map(str, pids))}).")
    else:
        print("РАЦИЯ: из исходников не запущена — ок.")
    if dirty and pids:
        print("!!! СТРИМ ИЗ ГРЯЗНЫХ ИСХОДНИКОВ: рация работает из незакоммиченного кода. "
              "Правило: езда и стрим — только из собранного release\\neutral\\CB-Radio.exe "
              "или после коммита. Перезапусти рацию из чистого состояния!")
        return 1
    return 1 if dirty else 0


def main():
    warns = 0
    print("=== PREFLIGHT «Канал 15» ===")
    warns += check_pilots()
    warns += check_dirty()
    print("ИТОГ: " + ("предупреждений нет — можно стримить." if not warns
                        else f"{warns} предупреждение(я) — разобраться ДО стрима."))
    return 1 if warns else 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main())
