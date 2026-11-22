# -*- coding: utf-8 -*-
"""22.11: заплатки-3 — озвучка 10 intent-пулов (traffic_local … swear_q).
Только эти пулы; движки — по полю engine актёров (gpt-audio/OR + EL + xtts).

  OR_BUDGET=1.0 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_zaplatki3.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

POOLS = ["traffic_local", "tech_cab", "health_small", "family_edge", "station_detail",
         "season_local", "road_rage3rd", "nostalgia_echo", "barter", "swear_q",
         "alert_other", "help", "swear_calm", "radio_check", "haul_work"]

data = ge.load_phrases()
REACT = ge.ROOT / "audio" / "reactions" / "intent"
el_total = 0
for name in POOLS:
    lines = data["reactions"]["intent"][name]
    d = REACT / name
    d.mkdir(parents=True, exist_ok=True)
    el_total += ge.voice_lines(d, lines, data, False, f"intent/{name}")
    (d / "index.json").write_text(json.dumps({"actors": [ln["actor"] for ln in lines]}, ensure_ascii=False),
                                  encoding="utf-8")
print(f"готово; EL символов: {el_total}; OpenRouter: ${ge._or_spent[0]:.3f}")
