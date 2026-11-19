# -*- coding: utf-8 -*-
"""GigaAM-QA свежих gpt-audio бантер-треков стрим-буста (19.11): dry-треки vs тексты оверлея.
  build/venv/Scripts/python.exe -X utf8 tools/qa_boost_gpt.py
"""
import difflib
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asr_gigaam  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NEW = {  # actor -> новые номера (из лога gen_boost_gpt.py 19.11)
    "student": [8, 9], "petrovna": [4, 5], "ten": [4, 5], "vitek": [7, 8],
    "ment": [8, 9], "kardan": [4, 5], "lisa": [4, 5],
}


def norm(s):
    s = re.sub(r"\([^)]*\)", "", s.lower())          # ремарки не произносятся словами
    s = re.sub(r"[^а-яa-z ]", " ", s.replace("ё", "е"))
    return s.split()


def main():
    data = json.loads((ROOT / "phrases" / "personal_local.json").read_text(encoding="utf-8"))
    sb = data["reactions"]["stream_banter"]
    rec = asr_gigaam.recognizer()
    bad = []
    n = 0
    # номера в merged-пуле: level3 N3 + personal. Новые — ПОСЛЕДНИЕ личные строки.
    for actor, nums in NEW.items():
        pers = sb[actor]
        new_texts = [e["text"] for e in pers[-len(nums):]]
        for num, text in zip(nums, new_texts):
            dry = ROOT / "audio" / "reactions" / "stream_banter" / actor / f"{num:02d}_dry.wav"
            if not dry.exists():
                print(f"! нет файла {dry}")
                bad.append((actor, num, "нет файла"))
                continue
            x, sr = sf.read(dry, dtype="float32")
            y = resample_poly(x, 16000, sr).astype(np.float32) if sr != 16000 else x
            heard = asr_gigaam.heard_text(y) or ""
            r = difflib.SequenceMatcher(None, norm(text), norm(heard)).ratio()
            n += 1
            mark = "OK " if r >= 0.8 else "!!!"
            print(f"{mark} {actor}/{num:02d} ratio={r:.2f} слышно: {heard[:70]}")
            if r < 0.8:
                bad.append((actor, num, f"{r:.2f}"))
    print(f"проверено {n}, подозрительных {len(bad)}")
    if bad:
        print("ПОДОЗРИТЕЛЬНЫЕ:", bad)


if __name__ == "__main__":
    main()
