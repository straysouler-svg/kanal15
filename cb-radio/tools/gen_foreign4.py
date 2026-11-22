# -*- coding: utf-8 -*-
"""22.11: озвучка скандинавско-турецкой четвёрки проезжих (x_no, x_sv, x_tr + расширение x_pl).
Только gpt-audio (EL geo-restriction). Новые пулы: foreign/reply/warm no|sv|tr, +foreign.pl, +warm.pl.

  OR_BUDGET=3 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_foreign4.py
"""
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
    before = ge._or_spent[0]
    used = ge.reactions(data)
    print(f"готово; OpenRouter: ${ge._or_spent[0] - before:.3f} (за прогон), "
          f"всего за сессию ${ge._or_spent[0]:.3f}; EL символов: {used}")


if __name__ == "__main__":
    main()
