"""Integrity check of everything on air: every deck item / reaction line has a sane audio file, numbering
matches the phrases file, every simulated driver has hello + bye, no mat for the no-mat characters."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import cb_radio as c  # noqa: E402

# 20.11: прогон против СБОРОЧНОЙ копии (ogg-контент): python tools/check_air.py <путь к CB-Radio сборки>
# (c.AUDIO — это audio/level3, не audio/)
if len(sys.argv) > 1:
    root = Path(sys.argv[1]).resolve()
    c.ROOT = root
    c.AUDIO = root / "audio" / "level3"
    c.REACT = root / "audio" / "reactions"
    c.SCENES = root / "audio" / "scenes"
    c.PHRASES_JSON = root / "phrases" / "level3_eleven.json"
BUILD_MODE = len(sys.argv) > 1
CUT_ACTORS = {"soroka"}      # персональный голос: в сборке её пулов нет by design (как PERSONAL в pack_release)      # прогон против сборки: ogg, без Сороки, вариантные строки без варианта — штатно
# сборка хранит звук в ogg, живое дерево — в wav
EXT = ".wav" if next(c.AUDIO.rglob("*.wav"), None) else ".ogg"

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
            sane(c.SCENES / it[6:] / f"{i:02d}{EXT}")
    else:
        sane(c.AUDIO / f"{it}{EXT}")
for k, a in A.items():
    if a.get("extra"):
        continue
    for i, ln in enumerate(a["phrases"], 1):
        if i in a.get("drop", []) or (c.AUDIO / k / f"{i:02d}{EXT}").exists():
            continue
        # сборка: строка с v_neutral без озвученного варианта штатно не копируется (pack skipped)
        if BUILD_MODE and isinstance(ln, dict) and "v_neutral" in ln:
            continue
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
        if BUILD_MODE and kk in CUT_ACTORS:   # пулы обращений к вырезанному персонажу (greet_reply/soroka)
            continue
        if isinstance(ls, dict):
            # вложенные пулы (knows: <actor> -> <target>) -> плоские <actor>__<target>
            for sub, subls in ls.items():
                if BUILD_MODE and sub not in A:   # пул обращений к вырезанному персонажу (Сорока)
                    continue
                pool = c.reaction_pool(g, f"{kk}__{sub}")
                lines += len(pool)
                eff = [e for e in subls if not (isinstance(e, dict) and e.get("v_pending"))]
                if BUILD_MODE:      # сборка: вариантные строки не учитываем; файлов может быть БОЛЬШЕ (варианты, v_pending)
                    eff = [e for e in eff if (e.get("actor") if isinstance(e, dict) else None) in A
                           and not (isinstance(e, dict) and "v_neutral" in e)]
                if len(pool) < len(eff):
                    problems.append(f"reactions {g}/{kk}__{sub}: файлов {len(pool)}, строк {len(eff)}")
            continue
        pool = c.reaction_pool(g, kk)
        lines += len(pool)
        eff = [e for e in ls if not (isinstance(e, dict) and e.get("v_pending"))]
        if BUILD_MODE:          # сборка: вариантные строки и вырезанные персонажи не учитываем
            eff = [e for e in eff if (e.get("actor") if isinstance(e, dict) else None) in A
                   and not (isinstance(e, dict) and "v_neutral" in e)]
        if (len(pool) < len(eff)) if BUILD_MODE else (len(pool) != len(eff)):
            problems.append(f"reactions {g}/{kk}: файлов {len(pool)}, строк {len(eff)}")
        for _, f in pool:
            sane(f)
mat = ["бля", "сука", "хрен", "херн", "ёп", "жоп", "нахрен"]
mat_re = re.compile(r"(?<![а-яё])(" + "|".join(mat) + r")")   # «тёплые» — не мат; слово целиком или с приставкой
for k in ("soroka", "professor", "petrovna", "sova"):
    if k not in A:                                  # сборка без Сороки (персональный голос)
        continue
    txt = " ".join(p if isinstance(p, str) else p["text"] for p in A[k]["phrases"]).lower()
    if mat_re.search(txt):
        problems.append(f"{k}: мат")
real = [k for k, a in A.items() if not a.get("extra")]
print(f"в колоде {len(items)} ({sum(i.startswith('scene/') for i in items)} сценок), персонажей {len(real)}, "
      f"проезжих/служебных {len(A) - len(real)}, реакций {lines}")
print("ПРОБЛЕМЫ:" if problems else "проблем нет", *problems[:40], sep="\n  ")
