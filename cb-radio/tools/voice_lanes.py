"""Озвучить ТОЛЬКО группу reactions.lane (ответы «куда едешь»), без прогона остальной базы.
    OR_BUDGET=1.8 python tools/voice_lanes.py [город ...]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

data = json.loads(ge.g.ROOT.joinpath("phrases", "level3_eleven.json").read_text(encoding="utf-8"))
only = set(sys.argv[1:])
used = 0
for city, lines in data["reactions"]["lane"].items():
    if city.startswith("_") or (only and city not in only):
        continue
    d = ge.ROOT / "audio" / "reactions" / "lane" / city
    used += ge.voice_lines(d, lines, data, False, f"lane/{city}")
    (d / "index.json").write_text(json.dumps({"actors": [ln["actor"] for ln in lines]}), encoding="utf-8")
print("ElevenLabs символов:", used, "| OpenRouter $:", round(ge._or_spent[0], 3))
