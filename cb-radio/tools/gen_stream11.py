# -*- coding: utf-8 -*-
"""Озвучка партии стрима #11 (20.11): foreign.fi/reply.fi, police +32, foreign_warm, joke.
EL-строки пропускаем (geo-restriction 302, нужен VPN) — в manifest не попадают,
догенерируем позже. gpt-audio генерируем сейчас.

  OR_BUDGET=3 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_stream11.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

_VOICE = ge.voice


def voice_gpt_only(a, text, rec=None):
    if a.get("engine") != "gpt-audio":
        raise ge.SkipLine(f"EL отложен (VPN): {a.get('name')}")
    return _VOICE(a, text, rec)


def main():
    ge.voice = voice_gpt_only
    data = ge.load_phrases()
    used = ge.reactions(data)
    print(f"готово; EL символов: {used} (только уже сгенерированное до блока); "
          f"OpenRouter: ${ge._or_spent[0]:.3f}")


if __name__ == "__main__":
    main()
