# -*- coding: utf-8 -*-
"""QA партии стрима #11 (20.11): сухие треки новых пулов против эталонных текстов.
RU-реплики — GigaAM v3 (build/venv, sherpa-onnx); иноязычные — faster-whisper (GigaAM мультиязык? нет — whisper).

  build/venv/Scripts/python.exe -X utf8 tools/qa_stream11.py
"""
import difflib
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]

# пул -> список (номер, эталон) для новых строк
def collect():
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    r = data["reactions"]
    pools = {}  # dir -> [(num, text, lang)]
    def add(d, lines, lang="ru"):
        rows = []
        for i, ln in enumerate(lines, 1):
            rows.append((i, ln["text"], lang))
        pools[d] = rows
    add(ROOT / "audio/reactions/foreign/fi", r["foreign"]["fi"], "fi")
    add(ROOT / "audio/reactions/foreign_reply/fi", r["foreign_reply"]["fi"], "fi")
    for lang, lines in r["foreign_warm"].items():
        if not lang.startswith("_"):
            add(ROOT / f"audio/reactions/foreign_warm/{lang}", lines, lang)
    # police: новые — последние 32
    pol = r["intent"]["police"]
    pools[ROOT / "audio/reactions/intent/police"] = [(i, pol[i - 1]["text"], "ru")
                                                      for i in range(len(pol) - 31, len(pol) + 1)]
    for actor, lines in r["joke"].items():
        if actor.startswith("_"):
            continue
        add(ROOT / f"audio/reactions/joke/{actor}", lines, "ru")
    return pools


def norm_ru(s):
    s = re.sub(r"\[[^\]]*\]", " ", s)          # EL-теги не произносятся
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^а-яa-z0-9 ]", " ", s.replace("ё", "е").lower())
    return s.split()


def main():
    import asr_gigaam
    rec = asr_gigaam.recognizer()
    from faster_whisper import WhisperModel
    wh = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=8)
    pools = collect()
    bad, n = [], 0
    for d, rows in pools.items():
        for num, text, lang in rows:
            dry = d / f"{num:02d}_dry.wav"
            if not dry.exists():
                dry = d / f"{num:02d}.wav"
            if not dry.exists():
                print(f"! НЕТ ФАЙЛА {dry}")
                bad.append((str(d), num, "нет файла"))
                continue
            x, sr = sf.read(dry, dtype="float32")
            if x.ndim > 1:
                x = x.mean(axis=1)
            y = resample_poly(x, 16000, sr).astype(np.float32) if sr != 16000 else x
            if lang == "ru":
                heard = asr_gigaam.heard_text(y) or ""
                r_ = difflib.SequenceMatcher(None, norm_ru(text), norm_ru(heard)).ratio()
            else:
                segs, _ = wh.transcribe(y, language=lang, beam_size=5)
                heard = " ".join(s.text for s in segs)
                r_ = difflib.SequenceMatcher(None, re.sub(r"[^a-zà-ÿ ]", " ", text.lower()).split(),
                                             re.sub(r"[^a-zà-ÿ ]", " ", heard.lower()).split()).ratio()
            n += 1
            mark = "OK " if r_ >= 0.8 else "!!!"
            print(f"{mark} {d.name}/{num:02d} [{lang}] ratio={r_:.2f} | {heard[:75]}")
            if r_ < 0.8:
                bad.append((d.name, num, f"{r_:.2f}"))
    print(f"проверено {n}, подозрительных {len(bad)}")
    if bad:
        print("БРАК:", bad)


if __name__ == "__main__":
    main()
