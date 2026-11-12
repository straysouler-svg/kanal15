# -*- coding: utf-8 -*-
"""Собрать папку гостя «онлайн-конвоя» (этап 1): ../..\\build\\_guest\\ со своим config и
своими портами, audio — junction-ссылкой (не копия, ~3400 файлов).

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
    "overlay": {"enabled": False, "port": 47824},       # хозяин держит 47823
    "world": {"enabled": False},                        # мир и дружба — только у хозяина
    "mic": {"enabled": False},                          # whisper гостя выключен (этап 1)
    "update": {"auto": False},
}

COPY_PY = [p for p in SRC.glob("*.py") if ".before_" not in p.name and not p.name.startswith("test_")]
COPY_FILES = [SRC / "phrases" / "level3_eleven.json"]


def sha(p):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return "-"


def main():
    DST.mkdir(parents=True, exist_ok=True)
    for p in COPY_PY:
        shutil.copy2(p, DST / p.name)
    for p in COPY_FILES:
        (DST / p.parent.name).mkdir(exist_ok=True)
        shutil.copy2(p, DST / p.parent.name / p.name)
    cfg_f = DST / "config.json"
    cfg_f.write_text(json.dumps(GUEST_CFG, ensure_ascii=False, indent=2), encoding="utf-8")
    link, target = DST / "audio", SRC / "audio"
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
    print("фраза «как гость»: напишите текст в", DST / "guest_say.txt")
    print(hashes and (DST / "before_hashes.txt"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
