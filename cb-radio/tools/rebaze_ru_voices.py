# -*- coding: utf-8 -*-
"""22.11: перебазирование русских проезжих: x_ru/x_ru_night -> onyx; новая женская линия
x_ru_f (nova, style x_ru) + 8 гендерно-нейтральных строк foreign.ru переведены на неё.
Только дописывание/замена полей; пулы, номера и тексты не сдвигаем."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))

for key in ("x_ru", "x_ru_night"):
    a = d["actors"][key]
    assert a["voice"] == "coral", f"{key} уже не coral: {a['voice']}"
    a["voice"] = "onyx"
    a["voice_id"] = "gpt-audio:onyx:ru"

src_style = d["actors"]["x_ru"]["style"]
d["actors"].setdefault("x_ru_f", {
    "name": "проезжая (рус)", "extra": True, "lang": "ru", "engine": "gpt-audio", "voice": "nova",
    "voice_id": "gpt-audio:nova:ru", "style": src_style,
    "radio": {"noise_db": -27, "drive": 2.0, "roger_beep": False},
    "cab": {"_": "проезжий", "road_db": -18, "window": 0.5, "wind_db": -21, "traffic": 0.1,
            "traffic_db": -18, "horn_chance": 0.1, "engine_db": -25, "rpm": 1450},
    "phrases": []})

# 8 гендерно-нейтральных строк (без мужских форм; правки текстов не потребовались)
FEM = {1, 3, 6, 10, 13, 19, 26, 29}
ru = d["reactions"]["foreign"]["ru"]
moved = []
for i in sorted(FEM):
    e = ru[i - 1]
    assert e["actor"] == "x_ru", f"строка {i} уже у {e['actor']}"
    e["actor"] = "x_ru_f"
    moved.append(i)

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print(f"x_ru, x_ru_night -> onyx; x_ru_f (nova) создан; на x_ru_f переведены строки: {moved}")
