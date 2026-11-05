"""Озвучить ТОЛЬКО одну группу reactions (например graf или lane), без прогона всей базы.
    python tools/voice_group.py graf [вид ...]"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

data = json.loads(ge.g.ROOT.joinpath("phrases", "level3_eleven.json").read_text(encoding="utf-8"))
group, only = sys.argv[1], set(sys.argv[2:])
used = 0
for kind, lines in data["reactions"][group].items():
    if kind.startswith("_") or (only and kind not in only):
        continue
    d = ge.ROOT / "audio" / "reactions" / group / kind
    used += ge.voice_lines(d, lines, data, False, f"{group}/{kind}")
    (d / "index.json").write_text(json.dumps({"actors": [ln["actor"] for ln in lines]}), encoding="utf-8")
print("ElevenLabs символов:", used, "| OpenRouter $:", round(ge._or_spent[0], 3))
