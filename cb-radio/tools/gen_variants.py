"""Voice the variants of the lines that call the player by name (fields v_<variant> made by make_variants.py).
  gen_variants.py <variant> [--engine gpt-audio|eleven|all] [--dry-run]
      variant: kirill | alive | neutral
-> audio/variants/<variant>/<same path as the original>.wav (+ _dry source). Only new/changed texts are voiced
(manifest.json per variant). Сорока is never voiced here (personal). OR_BUDGET env limits OpenRouter spend."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402
import remix  # noqa: E402

ROOT = g.ROOT
F = ROOT / "phrases" / "level3_eleven.json"


def lines(d, variant):
    key = f"v_{variant}"
    for sid, ls in d.get("scenes", {}).items():
        for i, ln in enumerate(ls, 1):
            if key in ln:
                yield f"scenes/{sid}/{i:02d}", ln
    for grp, ks in d.get("reactions", {}).items():
        if grp.startswith("_"):
            continue
        for k, ls in ks.items():
            if k.startswith("_"):
                continue
            for i, ln in enumerate(ls, 1):
                if key in ln:
                    yield f"reactions/{grp}/{k}/{i:02d}", ln


def engine_of(a):
    return "gpt-audio" if a.get("engine") == "gpt-audio" else "xtts" if a.get("engine") == "xtts" else "eleven"


def main(argv):
    variant = argv[0]
    want = argv[argv.index("--engine") + 1] if "--engine" in argv else "all"
    dry_run = "--dry-run" in argv
    d = json.loads(F.read_text(encoding="utf-8"))
    actors = d["actors"]
    out = ROOT / "audio" / "variants" / variant
    man_f = out / "manifest.json"
    man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {}
    todo = []
    for rel, ln in lines(d, variant):
        a = actors[ln["actor"]]
        if ln["actor"] == "soroka" or (want != "all" and engine_of(a) != want):
            continue
        text = ln[f"v_{variant}"]
        sig = f"{a.get('voice_id', a.get('voice'))}|{text}|far={bool(ln.get('far'))}"
        if man.get(rel) == sig and (out / f"{rel}.wav").exists():
            continue
        todo.append((rel, ln, a, text, sig))
    print(f"{variant}: озвучить {len(todo)} реплик ({want})")
    if dry_run:
        for rel, ln, a, text, _ in todo:
            print(f"  {rel:34} {a['name']:10} {text}")
        return
    import gen_eleven as ge
    for rel, ln, a, text, sig in todo:
        mp3, x, _ = ge.voice(a, text)
        base = out / rel
        base.parent.mkdir(parents=True, exist_ok=True)
        ge.save_dry(base, mp3, x)
        rng = np.random.default_rng(abs(hash((variant, rel))) % 2**32)
        sf.write(base.with_suffix(".wav"), remix.render(x, a, ln.get("far", False), rng, force=ln.get("cab")), g.SR)
        man[rel] = sig
        man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"  {rel:34} {a['name']:10} {text}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
