# -*- coding: utf-8 -*-
"""GigaAM-QA свежих EL-треков стрим-буста (19.11): buh-пулы + бантер EL-актёров.
  build/venv/Scripts/python.exe -X utf8 tools/qa_boost_el.py
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
NESTED_BUH = ["viewers", "chat", "donate_pitch"]
EL_BANTER = ["mihalych", "yanek", "lastochka", "boroda", "professor", "rustam",
             "vera", "sova", "buh", "bahti", "stas"]


def norm(s):
    s = re.sub(r"\[[^\]]*\]", "", s.lower())          # EL-теги не произносятся
    s = re.sub(r"[^а-яa-z ]", " ", s.replace("ё", "е"))
    return s.split()


def main():
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    personal = json.loads((ROOT / "phrases" / "personal_local.json").read_text(encoding="utf-8"))
    # merge как в рации/load_phrases: оверлей дописывается в конец пулов
    for gr, kinds in (personal.get("reactions") or {}).items():
        dst = data.setdefault("reactions", {}).setdefault(gr, {})
        for k, lines in (kinds or {}).items():
            if isinstance(lines, list) and isinstance(dst.get(k), list):
                dst[k].extend(lines)
    asr_gigaam.recognizer()      # прогрев модели
    bad, n = [], 0

    def check(d, num, text, label):
        nonlocal n
        dry = d / f"{num:02d}.mp3"            # EL: сухой трек = mp3
        if not dry.exists():
            dry = d / f"{num:02d}_dry.wav"    # локальные голоса: wav
        if not dry.exists():
            print(f"! нет файла {label}/{num:02d}")
            bad.append((label, num, "нет файла"))
            return
        x, sr = sf.read(dry, dtype="float32")
        y = resample_poly(x, 16000, sr).astype(np.float32) if sr != 16000 else np.asarray(x, dtype=np.float32)
        heard = asr_gigaam.heard_text(y) or ""
        r = difflib.SequenceMatcher(None, norm(text), norm(heard)).ratio()
        n += 1
        mark = "OK " if r >= 0.8 else "!!!"
        print(f"{mark} {label}/{num:02d} ratio={r:.2f} слышно: {heard[:70]}")
        if r < 0.8:
            bad.append((label, num, f"{r:.2f}"))

    buh = data["reactions"]["buh"]
    for kind, node in buh.items():
        if kind in NESTED_BUH:
            for sub, lines in node.items():
                d = ROOT / "audio" / "reactions" / "buh" / f"{kind}__{sub}"
                for i, ln in enumerate(lines, 1):
                    check(d, i, ln["text"], f"buh/{kind}__{sub}")
        elif isinstance(node, list) and kind in ("subs", "subs_none", "superchat"):
            d = ROOT / "audio" / "reactions" / "buh" / kind
            for i, ln in enumerate(node, 1):
                check(d, i, ln["text"], f"buh/{kind}")
    # добор 19.11 (разделы 1-2): только новые номера
    NEW_RANGES = {"stream_news": (3, 6), "stream_greet": (4, 7),
                  "escalation": (8, 10), "delivery_many": (3, 4)}
    for kind, (a_, b_) in NEW_RANGES.items():
        d = ROOT / "audio" / "reactions" / "buh" / kind
        lines = buh[kind]
        for i in range(a_, b_ + 1):
            check(d, i, lines[i - 1]["text"], f"buh/{kind}")
    for actor in EL_BANTER:
        merged = list(data["reactions"]["stream_banter"].get(actor) or [])
        pers = (personal.get("reactions", {}).get("stream_banter", {}) or {}).get(actor) or []
        if not merged and pers:                   # бухгалтерия живёт только в оверлее
            merged = list(pers)
        new_texts = [e["text"] for e in pers[-2:]]            # новые = последние 2 личных
        nums = range(len(merged) - 1, len(merged) + 1)        # их номера в конце merged
        d = ROOT / "audio" / "reactions" / "stream_banter" / actor
        for num, text in zip(nums, new_texts):
            check(d, num, text, f"banter/{actor}")
    print(f"проверено {n}, подозрительных {len(bad)}")
    if bad:
        print("ПОДОЗРИТЕЛЬНЫЕ:", bad)


if __name__ == "__main__":
    main()
