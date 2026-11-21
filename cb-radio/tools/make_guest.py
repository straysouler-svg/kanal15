# -*- coding: utf-8 -*-
"""Собрать папку гостя «онлайн-конвоя»: ../..\\build\\_guest\\ со своим config и
своими портами, audio — junction-ссылкой (не копия, ~3400 файлов; для передачи
через интернет ключ --copy-audio копирует папку реально).

Этап 2 (21.11): микрофон гостя ВКЛЮЧЁН — речь распознаётся локально (whisper),
в сеть уходит только текст; хозяин/пин — в convoy секции config гостя
(НЕ в командной строке); рядом кладётся start_guest.cmd.

Основная папка cb-radio НЕ меняется — проверка и есть пункт приёмки.
Повторный запуск обновляет копии .py и пересоздаёт junction.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent          # cb-radio/
DST = SRC.parent / "build" / "_guest"                  # build/_guest/

GUEST_CFG = {
    "gap_min_s": 300, "gap_max_s": 720, "first_after_s": [60, 180],
    "volume": 0.8, "device": None, "require_engine_on": True,
    "kerchunk_gap_s": [], "greet_reply_chance": 0.85,
    "ptt": {"device": "keyboard", "button": "f9"},     # тангента гостя — клавиша (хозяин — на руле)
    "lock_port": 47820,                                 # хозяин держит 47819
    "guest": {"port": 47821, "enabled": False},         # гость — клиент, порт хозяина только для справки
    "convoy": {"host": "127.0.0.1:47821",               # АДРЕС ХОЗЯИНА: поменять под его внешний ip:port
               "pin": "",                               # пин хозяина (секрет — только здесь, не в cmdline)
               "bind": "127.0.0.1"},                    # bind у гостя не слушает, поле для совместимости
    "overlay": {"enabled": False, "port": 47824},       # хозяин держит 47823
    "world": {"enabled": False},                        # мир и дружба — только у хозяина
    "mic": {"enabled": True},                           # этап 2: голос гостя — локальный whisper, в сеть текст
    "update": {"auto": False},
}

COPY_PY = [p for p in SRC.glob("*.py") if ".before_" not in p.name and not p.name.startswith("test_")]
COPY_FILES = [SRC / "phrases" / "level3_eleven.json"]

START_CMD = """@echo off
chcp 65001 >nul
rem Гость «онлайн-конвоя»: адрес и pin берутся из config.json (раздел convoy) — здесь только запуск.
rem Необязательный аргумент: адрес хозяина, например  start_guest.cmd 203.0.113.5:47821
set ROOT=%~dp0
set PY=%ROOT%python\\python.exe
if not exist "%PY%" set PY=python
set ADDR=%~1
if "%ADDR%"=="" ("%PY%" "%ROOT%cb_radio.py" --guest) else ("%PY%" "%ROOT%cb_radio.py" --guest %ADDR%)
pause
"""


def sha(p):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return "-"


def main():
    copy_audio = "--copy-audio" in sys.argv          # для передачи папки через интернет (junction бесполезен)
    DST.mkdir(parents=True, exist_ok=True)
    for p in COPY_PY:
        shutil.copy2(p, DST / p.name)
    for p in COPY_FILES:
        (DST / p.parent.name).mkdir(exist_ok=True)
        shutil.copy2(p, DST / p.parent.name / p.name)
    cfg_f = DST / "config.json"
    if cfg_f.exists():                               # адрес/pin гостя не затираем пересборкой
        try:
            old = json.loads(cfg_f.read_text(encoding="utf-8"))
            GUEST_CFG["convoy"].update((old.get("convoy") or {}))
        except (OSError, ValueError):
            pass
    cfg_f.write_text(json.dumps(GUEST_CFG, ensure_ascii=False, indent=2), encoding="utf-8")
    (DST / "start_guest.cmd").write_text(START_CMD, encoding="utf-8")
    link, target = DST / "audio", SRC / "audio"
    if copy_audio:
        if link.is_symlink():
            link.unlink()
        if not link.exists():
            print("копирую audio/ (долго, ~несколько ГБ)...")
            shutil.copytree(target, link)
    else:
        if link.is_symlink() or link.exists():
            if link.is_dir() and not link.is_symlink():
                if (link / "level3").exists():      # случайно скопированное аудио не трогаем молча
                    print(f"ВНИМАНИЕ: {link} — реальная папка, junction не создан")
                    return 1
            else:
                link.unlink()
        if not link.exists():
            r = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                               capture_output=True, text=True)
            if r.returncode != 0:
                print("junction не создался:", r.stdout, r.stderr)
                return 1
    hashes = {n: sha(SRC / n) for n in ("config.json", "bonds.json", "state.json", "world_state.json")}
    (DST / "before_hashes.txt").write_text(
        "Хэши основной папки ДО теста (сверить ПОСЛЕ):\n" +
        "\n".join(f"{h}  {n}" for n, h in hashes.items()) + "\n", encoding="utf-8")
    print("гость собран:", DST)
    print("порты: lock 47820 (хозяин 47819), overlay выкл (хозяин 47823), конвой 47821")
    print("тангента гостя: клавиша F9 (можно переназначить из меню значка гостя)")
    print("голос гостя: микрофон + локальный whisper (mic.enabled=true), в сеть уходит только текст")
    print("запуск: start_guest.cmd (адрес/pin — в config.json, раздел convoy)")
    print("фраза «как гость» (fallback): напишите текст в", DST / "guest_say.txt")
    print(hashes and (DST / "before_hashes.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
