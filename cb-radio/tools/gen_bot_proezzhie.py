# -*- coding: utf-8 -*-
"""22.11: точечная озвучка батча «бот-проезжие» — ТОЛЬКО новые строки, чужие пулы не трогаем.
foreign/ru (6), streambot (15, плоский каталог), foreign/{pl,de,en,fr,es,it,cs,ro,fi} (25).

  OR_BUDGET=0.6 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_bot_proezzhie.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

data = ge.load_phrases()
REACT = ge.ROOT / "audio" / "reactions"


def voice(group, kind, flat_dir=None):
    lines = data["reactions"][group][kind]
    d = REACT / (flat_dir or f"{group}/{kind}")
    d.mkdir(parents=True, exist_ok=True)
    used = ge.voice_lines(d, lines, data, False, str(d.relative_to(REACT)))
    (d / "index.json").write_text(json.dumps({"actors": [ln["actor"] for ln in lines]}, ensure_ascii=False),
                                  encoding="utf-8")
    return used


total_el = 0
total_el += voice("foreign", "ru")
total_el += voice("streambot", "ru")
for lang in ("pl", "de", "en", "fr", "es", "it", "cs", "ro", "fi"):
    total_el += voice("foreign", lang)
print(f"готово; EL символов: {total_el}; OpenRouter: ${ge._or_spent[0]:.3f}")
