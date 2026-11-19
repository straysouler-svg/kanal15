# -*- coding: utf-8 -*-
"""Озвучка новых gpt-audio бантер-строк стрим-буста (19.11) — только engine gpt-audio,
ElevenLabs сейчас недоступен (geo-restriction, нужен VPN) и сюда не зовётся.
Порядок строк = level3 stream_banter/<actor> + личный оверлей personal_local.json
(как merge в gen_eleven.load_phrases): неизменные строки manifest пропускает,
новые получают следующие номера. Index.json переписываем под итоговый список.

  G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_boost_gpt.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

ROOT = ge.ROOT
GPT_ACTORS = ["student", "petrovna", "ten", "vitek", "ment", "kardan", "lisa"]


def main():
    data = ge.load_phrases()          # level3 + personal overlay, merge как в рации
    personal = json.loads((ROOT / "phrases" / "personal_local.json").read_text(encoding="utf-8"))
    total = 0
    for actor in GPT_ACTORS:
        a = data["actors"][actor]
        assert (a.get("model") or a.get("engine")) == "gpt-audio", f"{actor} не gpt-audio!"
        merged = list(data["reactions"]["stream_banter"].get(actor) or [])
        d = ROOT / "audio" / "reactions" / "stream_banter" / actor
        # индекс = level3-строки + личные; защита от рассинхрона с уже озвученным
        pers_n = len((personal.get("reactions", {}).get("stream_banter", {}) or {}).get(actor) or [])
        print(f"== {actor}: level3+overlay {len(merged)} строк (личных {pers_n})")
        used = ge.voice_lines(d, merged, data, force=False, label=f"banter/{actor}")
        (d / "index.json").write_text(
            json.dumps({"actors": [actor] * len(merged)}, ensure_ascii=False), encoding="utf-8")
        total += used
    print("готово; EL не трогали (geo-restriction), OpenRouter — см. лог выше")


if __name__ == "__main__":
    main()
