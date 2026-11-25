"""Пересобрать звук (кабина + рация) реплик одного или нескольких водителей из готовых сухих записей.
Без API и кредитов. Нужно, когда у водителя появился новый звук кабины (например, лай Графа).
    python tools/rerender_actor.py vera [rustam ...]
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402
import remix  # noqa: E402

ROOT = g.ROOT


def one(base, actor, far, rng, force, out, no_music=False):
    src = remix.src(base, actor)
    if src is None:
        return False
    x = remix.dry(src) if src.suffix == ".mp3" else sf.read(src, dtype="float32")[0]
    sf.write(out, remix.render(x, actor, far, rng, force=force, no_music=no_music), g.SR)
    return True


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    no_music = "--nomusic" in sys.argv
    who = set(a for a in sys.argv[1:] if not a.startswith("--"))
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    n = 0
    for key in who:
        a = data["actors"][key]
        rng = np.random.default_rng(abs(hash(key)) % 2**32)
        for i, it in enumerate(a["phrases"], 1):
            nn = f"{i:02d}"
            force = it.get("cab") if isinstance(it, dict) else None
            n += one(ROOT / "audio" / "level3_clean" / key / nn, a, False, rng, force,
                     ROOT / "audio" / "level3" / key / f"{nn}.wav", no_music=no_music)

    def lines(d, ls):
        nonlocal n
        for i, ln in enumerate(ls, 1):
            if ln["actor"] in who:
                rng = np.random.default_rng(abs(hash((str(d), i))) % 2**32)
                n += one(d / f"{i:02d}", data["actors"][ln["actor"]], ln.get("far", False), rng, ln.get("cab"),
                         d / f"{i:02d}.wav", no_music=no_music)
    for sid, ls in data["scenes"].items():
        lines(ROOT / "audio" / "scenes" / sid, ls)
    for grp, kinds in data["reactions"].items():
        if grp.startswith("_"):
            continue
        for kind, ls in kinds.items():
            if kind.startswith("_"):
                continue
            if isinstance(ls, dict):     # вложенные пулы (knows/<actor> -> <target>) -> плоские <actor>__<target>
                for target, sub in ls.items():
                    lines(ROOT / "audio" / "reactions" / grp / f"{kind}__{target}", sub)
                continue
            lines(ROOT / "audio" / "reactions" / grp / kind, ls)
    print(f"пересобрано {n} реплик: {', '.join(sorted(who))}")


if __name__ == "__main__":
    main()
