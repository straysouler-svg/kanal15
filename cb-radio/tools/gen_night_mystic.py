# -*- coding: utf-8 -*-
"""22.11: точечная озвучка night_mystic/ru (25 строк, x_ru_night). Только этот пул.

  OR_BUDGET=0.5 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_night_mystic.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

data = ge.load_phrases()
lines = data["reactions"]["night_mystic"]["ru"]
d = ge.ROOT / "audio" / "reactions" / "night_mystic" / "ru"
d.mkdir(parents=True, exist_ok=True)
used = ge.voice_lines(d, lines, data, False, "night_mystic/ru")
(d / "index.json").write_text(json.dumps({"actors": [ln["actor"] for ln in lines]}, ensure_ascii=False),
                              encoding="utf-8")
print(f"готово; EL символов: {used}; OpenRouter: ${ge._or_spent[0]:.3f}")
