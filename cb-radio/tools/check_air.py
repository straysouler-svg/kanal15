"""Integrity check of everything on air: every deck item / reaction line has a sane audio file, numbering
matches the phrases file, every simulated driver has hello + bye, no mat for the no-mat characters."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cb_radio as c  # noqa: E402

d = json.loads(c.PHRASES_JSON.read_text(encoding="utf-8"))
A = d["actors"]
problems = []


def sane(f):
    if not f.exists():
        problems.append(f"нет файла {f.relative_to(c.ROOT)}")
        return
    x, sr = sf.read(f)
    if sr != 48000 or not np.isfinite(x).all() or np.abs(x).max() > 1.0 or len(x) < sr * 0.4:
        problems.append(f"битый звук {f.relative_to(c.ROOT)}")


items = c.all_phrases()
for it in items:
    if it.startswith("scene/"):
        meta = json.loads((c.SCENES / it[6:] / "scene.json").read_text(encoding="utf-8"))
        if len(meta["actors"]) != len(d["scenes"].get(it[6:], [])):
            problems.append(f"{it}: scene.json устарел")
        for i in range(1, len(meta["actors"]) + 1):
            sane(c.SCENES / it[6:] / f"{i:02d}.wav")
    else:
        sane(c.AUDIO / f"{it}.wav")
for k, a in A.items():
    if a.get("extra"):
        continue
    for i in range(1, len(a["phrases"]) + 1):
        if i not in a.get("drop", []) and not (c.AUDIO / k / f"{i:02d}.wav").exists():
            problems.append(f"нет звука {k}/{i:02d}")
    roles = c.load_roles().get(k, {})
    if not roles.get("greet") or not roles.get("signoff"):
        problems.append(f"{k}: нет приветствия/прощания")
lines = 0
for g, ks in d["reactions"].items():
    if g.startswith("_"):
        continue
    for kk, ls in ks.items():
        if kk.startswith("_"):
            continue
        pool = c.reaction_pool(g, kk)
        lines += len(pool)
        if len(pool) != len(ls):
            problems.append(f"reactions {g}/{kk}: файлов {len(pool)}, строк {len(ls)}")
        for _, f in pool:
            sane(f)
mat = ["бля", "сука", "хрен", "херн", "ёп", "жоп", "нахрен"]
for k in ("soroka", "professor", "petrovna", "sova"):
    txt = " ".join(p if isinstance(p, str) else p["text"] for p in A[k]["phrases"]).lower()
    if any(m in txt for m in mat):
        problems.append(f"{k}: мат")
real = [k for k, a in A.items() if not a.get("extra")]
print(f"в колоде {len(items)} ({sum(i.startswith('scene/') for i in items)} сценок), персонажей {len(real)}, "
      f"проезжих/служебных {len(A) - len(real)}, реакций {lines}")
print("ПРОБЛЕМЫ:" if problems else "проблем нет", *problems[:40], sep="\n  ")
