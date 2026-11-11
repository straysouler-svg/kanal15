"""QA переозвучки: Whisper-проверка свежих реплик актёра + сборка прослушки.

  qa_recast.py professor mihalych [n]

Для каждого актёра берёт n случайных реплик из reactions/scenes, прогоняет
Whisper (как в gen_eleven._heard_ratio) и печатает совпадение текста.
Плохое совпадение = мямлит/глотает слова/кривое ударение — кандидат на переслушку.
Плюс собирает samples/recast_<actor>.wav — 6 wet-реплик подряд для прослушки.
"""
import json
import random
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402
from gen_eleven import _heard_ratio  # noqa: E402  (ленивый whisper внутри)

ROOT = g.ROOT


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
    actors = [a for a in sys.argv[1:] if not a.isdigit()]
    n = int(next((a for a in sys.argv[1:] if a.isdigit()), 12))
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
            if sr != g.SR:
                from scipy.signal import resample_poly
                x = resample_poly(x, g.SR, sr).astype(np.float32)
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
            sf.write(out, np.concatenate(parts), g.SR)
            print(f"  прослушка: {out}")


if __name__ == "__main__":
    main()
