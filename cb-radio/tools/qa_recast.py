"""QA переозвучки: Whisper-проверка свежих реплик актёра + сборка прослушки.

  qa_recast.py professor mihalych [n]
  qa_recast.py professor --engine gigaam   — распознавание dry-треков через GigaAM v3

Для каждого актёра берёт n случайных реплик из reactions/scenes, прогоняет
Whisper (как в gen_eleven._heard_ratio) и печатает совпадение текста.
Плохое совпадение = мямлит/глотает слова/кривое ударение — кандидат на переслушку.
Плюс собирает samples/recast_<actor>.wav — 6 wet-реплик подряд для прослушки.
"""
import json
import random
import re
import sys
import difflib
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
SR = 48000  # рабочая частота конвейера (gen_level3.SR) — для сборки прослушки


def _norm(s):
    s = re.sub(r"\[[^\]]*\]", "", s.lower()).replace("ё", "е").replace("-", " ")
    return re.sub(r"[^а-яa-z ]", "", s).split()


def collect(actor):
    """(wet_path, dry_source, text) по всем реакциям и сценкам актёра."""
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    out = []

    def add(d, lines):
        for i, ln in enumerate(lines, 1):
            if ln["actor"] != actor:
                continue
            wet = d / f"{i:02d}.wav"
            dry = d / f"{i:02d}.mp3"
            if wet.exists() and dry.exists():
                out.append((wet, dry, ln["text"]))

    for sid, lines in data.get("scenes", {}).items():
        add(ROOT / "audio" / "scenes" / sid, lines)
    for group, kinds in data.get("reactions", {}).items():
        if group.startswith("_"):
            continue
        for kind, lines in kinds.items():
            if kind.startswith("_"):
                continue
            if isinstance(lines, dict):
                for target, sub in lines.items():
                    add(ROOT / "audio" / "reactions" / group / f"{kind}__{target}", sub)
            else:
                add(ROOT / "audio" / "reactions" / group / kind, lines)
    return out


def main():
    engine = "whisper"
    args = list(sys.argv[1:])
    if "--engine" in args:
        i = args.index("--engine")
        engine = args[i + 1]
        del args[i:i + 2]
    actors = [a for a in args if not a.isdigit()]
    n = int(next((a for a in args if a.isdigit()), 12))
    if engine == "gigaam":
        import asr_gigaam
    rng = random.Random(15)
    for actor in actors:
        pool = collect(actor)
        print(f"\n== {actor}: реплик в реакциях/сценках {len(pool)}, проверяю {min(n, len(pool))} ==")
        worst = []
        preview = []
        for wet, dry, text in rng.sample(pool, min(n, len(pool))):
            x, sr = sf.read(dry, dtype="float32")
            if x.ndim > 1:
                x = x.mean(axis=1)
            from scipy.signal import resample_poly
            x = resample_poly(x, 16000, sr).astype(np.float32)
            if engine == "gigaam":
                r = difflib.SequenceMatcher(None, _norm(text), _norm(asr_gigaam.heard_text(x))).ratio()
            else:
                from gen_eleven import _heard_ratio  # тянет whisper/torch — только для whisper-движка
                r = _heard_ratio(x, text)
            tag = wet.parent.name
            print(f"  {r:.2f}  {tag}/{wet.stem}  {text[:70]}")
            worst.append((r, tag, wet.stem, text))
            preview.append(wet)
        worst.sort()
        print("  худшие:", "; ".join(f"{t}/{s}={r:.2f}" for r, t, s, _ in worst[:3]))
        parts = []
        for wet in preview[:6]:
            x, sr = sf.read(wet, dtype="float32")
            parts += [x, np.zeros(int(0.9 * sr), np.float32)]
        if parts:
            out = ROOT / "samples" / f"recast_{actor}.wav"
            sf.write(out, np.concatenate(parts), SR)
            print(f"  прослушка: {out}")


if __name__ == "__main__":
    main()
