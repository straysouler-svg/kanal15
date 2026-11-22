# -*- coding: utf-8 -*-
"""22.11: ash-доля русских проезжих. x_ru_ash (ash, style x_ru); 12 мужских строк
foreign/ru равномерно по номерам (без №23 — QA-флаг, остаётся onyx) -> x_ru_ash.
Только замена поля actor; номера файлов и тексты не сдвигаются."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))

a = d["actors"]["x_ru"]
d["actors"].setdefault("x_ru_ash", {
    "name": "проезжий 2 (рус)", "extra": True, "lang": "ru", "engine": "gpt-audio", "voice": "ash",
    "voice_id": "gpt-audio:ash:ru", "style": a["style"],
    "radio": dict(a["radio"]), "cab": dict(a["cab"]), "phrases": []})

ASH = [2, 5, 8, 11, 14, 16, 18, 21, 24, 27, 30, 33]
ru = d["reactions"]["foreign"]["ru"]
for i in ASH:
    e = ru[i - 1]
    assert e["actor"] == "x_ru", f"№{i} уже у {e['actor']}"
    e["actor"] = "x_ru_ash"

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("x_ru_ash создан; на ash переведены:", ASH)
