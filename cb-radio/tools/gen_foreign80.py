# -*- coding: utf-8 -*-
"""22.11: партия foreign80 — филлеры (gpt-audio/OR) + ответы наших (ElevenLabs).
Прогон через ge.reactions: сам разруливает движки по engine актёра. EL-обрывы -> пропуск с логом.

  OR_BUDGET=1.5 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_foreign80.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

_VOICE = ge.voice


def voice_safe(a, text, rec=None):
    try:
        return _VOICE(a, text, rec)
    except ge.SkipLine:
        raise
    except Exception as e:                       # EL geo-restriction/сеть — не ронять прогон
        print(f"! пропуск ({type(e).__name__}: {e}) {a.get('name')}: {text[:60]}")
        raise ge.SkipLine(str(e))


def main():
    ge.voice = voice_safe
    data = ge.load_phrases()
    before = ge._or_spent[0]
    used = ge.reactions(data)
    print(f"готово; OpenRouter: ${ge._or_spent[0] - before:.3f} (за прогон); EL символов: {used}")


if __name__ == "__main__":
    main()
