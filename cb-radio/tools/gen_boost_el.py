# -*- coding: utf-8 -*-
"""EL-партия стрим-буста (19.11): buh-пулы (Maria, eleven_v3) + бантер EL-актёров из личного
оверлея. НЕ gen_eleven.py level3: тот плохо видит оверлей stream_banter (отдаст его во
вложенные stream_banter__<actor>) — здесь пулы перечислены явно. Сухие треки + кабина инлайн
(как voice_lines делает для всех движков), manifest-скип неизменного.

  G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_boost_el.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

ROOT = ge.ROOT
NESTED_BUH = ["viewers", "chat", "donate_pitch"]       # -> buh/<kind>__<sub> (плоские пулы)
EL_BANTER = ["mihalych", "yanek", "lastochka", "boroda", "professor", "rustam",
             "vera", "sova", "buh", "bahti", "stas"]


def main():
    data = ge.load_phrases()
    buh = data["reactions"]["buh"]
    used = 0
    for kind, node in buh.items():
        if kind.startswith("_"):
            continue
        if kind in NESTED_BUH:
            for sub, lines in node.items():
                d = ROOT / "audio" / "reactions" / "buh" / f"{kind}__{sub}"
                used += ge.voice_lines(d, lines, data, force=False, label=f"buh/{kind}__{sub}")
                (d / "index.json").write_text(
                    json.dumps({"actors": [ln["actor"] for ln in lines]}, ensure_ascii=False),
                    encoding="utf-8")
        elif isinstance(node, list):
            d = ROOT / "audio" / "reactions" / "buh" / kind
            used += ge.voice_lines(d, node, data, force=False, label=f"buh/{kind}")
            (d / "index.json").write_text(
                json.dumps({"actors": [ln["actor"] for ln in node]}, ensure_ascii=False),
                encoding="utf-8")
    personal = json.loads((ROOT / "phrases" / "personal_local.json").read_text(encoding="utf-8"))
    for actor in EL_BANTER:
        a = data["actors"][actor]
        assert (a.get("model") or a.get("engine")) != "gpt-audio", f"{actor} не EL!"
        merged = list(data["reactions"]["stream_banter"].get(actor) or [])
        pers_n = len((personal.get("reactions", {}).get("stream_banter", {}) or {}).get(actor) or [])
        print(f"== banter/{actor}: merged {len(merged)} (личных {pers_n})")
        d = ROOT / "audio" / "reactions" / "stream_banter" / actor
        used += ge.voice_lines(d, merged, data, force=False, label=f"banter/{actor}")
        (d / "index.json").write_text(
            json.dumps({"actors": [actor] * len(merged)}, ensure_ascii=False), encoding="utf-8")
    print(f"озвучено символов EL: {used}")


if __name__ == "__main__":
    main()
