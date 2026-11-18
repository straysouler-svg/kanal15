"""Проверка свежей озвучки ElevenLabs распознаванием: для реплик, озвученных после указанного времени,
сравнивает текст (без [тегов]) с тем, что слышит Whisper. Печатает подозрительные (< порога).
    python tools/qa_recent.py "2026-11-04 15:00" [порог=0.8] [модель=small]
    python tools/qa_recent.py "2026-11-04 15:00" --engine gigaam   — dry-треки через GigaAM v3
"""
import difflib
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]


def norm(s):
    s = re.sub(r"\[[^\]]*\]", "", s.lower()).replace("ё", "е").replace("-", " ")
    return re.sub(r"[^а-яa-z ]", "", s).split()


def items(d):
    """(mp3 path, actor, text) для всех реплик ElevenLabs."""
    for key, a in d["actors"].items():
        for i, it in enumerate(a["phrases"], 1):
            yield ROOT / "audio" / "level3_clean" / key / f"{i:02d}.mp3", key, it["text"] if isinstance(it, dict) else it
    for sid, ls in d["scenes"].items():
        for i, ln in enumerate(ls, 1):
            yield ROOT / "audio" / "scenes" / sid / f"{i:02d}.mp3", ln["actor"], ln["text"]
    for g, ks in d["reactions"].items():
        if g.startswith("_"):
            continue
        for k, ls in ks.items():
            if k.startswith("_"):
                continue
            if isinstance(ls, dict):  # вложенные пулы (knows, bond/names_*__<actor>): папка <k>__<target>
                for tgt, sub in ls.items():
                    for i, ln in enumerate(sub, 1):
                        yield ROOT / "audio" / "reactions" / g / f"{k}__{tgt}" / f"{i:02d}.mp3", ln["actor"], ln["text"]
                continue
            for i, ln in enumerate(ls, 1):
                yield ROOT / "audio" / "reactions" / g / k / f"{i:02d}.mp3", ln["actor"], ln["text"]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    engine = "whisper"
    argv = list(sys.argv)
    if "--engine" in argv:
        i = argv.index("--engine")
        engine = argv[i + 1]
        del argv[i:i + 2]
    if engine == "gigaam":
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import asr_gigaam
    since = datetime.strptime(argv[1], "%Y-%m-%d %H:%M").timestamp()
    thr = float(argv[2]) if len(argv) > 2 else 0.8
    m = None
    if engine != "gigaam":
        from faster_whisper import WhisperModel
        m = WhisperModel(argv[3] if len(argv) > 3 else "small", device="cpu", compute_type="int8")
    d = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    n = bad = 0
    for p, actor, text in items(d):
        if not p.exists() or p.stat().st_mtime < since:
            continue
        x, sr = sf.read(p, dtype="float32")
        x = x.mean(axis=1) if x.ndim > 1 else x
        x = resample_poly(x, 16000, sr).astype(np.float32)
        if engine == "gigaam":
            heard = asr_gigaam.heard_text(x)
        else:
            heard = " ".join(s.text.strip() for s in m.transcribe(x, language="ru", beam_size=5)[0])
        r = difflib.SequenceMatcher(None, norm(text), norm(heard)).ratio()
        n += 1
        if r < thr:
            bad += 1
            print(f"{r:.2f} {p.relative_to(ROOT)}\n     текст:  {re.sub(r'\[[^\]]*\] ?', '', text)}\n     слышно: {heard}")
    print(f"проверено {n}, подозрительных {bad}")


if __name__ == "__main__":
    main()
