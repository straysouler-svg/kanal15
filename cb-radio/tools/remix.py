"""Re-render every transmission from the saved dry ElevenLabs mp3s: cab background + radio FX.
No API calls, no credits.

  remix.py              everything (singles, scenes, reactions, kerchunks)
  remix.py --backup     first copy the current wavs to audio/_backup_<time>
  remix.py --nocab      render without the cab background (old sound)
"""
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cab  # noqa: E402
import gen_level3 as g  # noqa: E402

ROOT = g.ROOT
A = ROOT / "audio"


def dry(mp3):
    x, sr = sf.read(mp3, dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != g.SR:
        x = resample_poly(x, g.SR, sr).astype(np.float32)
    return x


def src(base, actor):
    """Dry source for a line: NN.mp3 (ElevenLabs) or NN_dry.wav (local clone), by the actor's engine."""
    mp3, wav = base.with_suffix(".mp3"), base.parent / f"{base.name}_dry.wav"
    order = (wav, mp3) if actor.get("engine") in ("xtts", "gpt-audio") else (mp3, wav)
    return next((p for p in order if p.exists()), None)


def phone(x):
    """A messenger voice note: narrow phone band, a little compression, no CB static/squelch."""
    v = x / (np.max(np.abs(x)) + 1e-9)
    v = g._band(v, 300, 3600, 4)
    v = np.tanh(v * 1.4) / np.tanh(1.4)
    pad = np.zeros(int(0.15 * g.SR))
    v = np.concatenate([pad, v, pad]) + np.random.default_rng(1).standard_normal(len(v) + 2 * len(pad)) * 0.002
    return (v / (np.max(np.abs(v)) + 1e-9) * 10 ** (-3 / 20)).astype(np.float32)


def forced_cab(c, force):
    """A line that talks about a sound ("сделаю потише", "Дизель, слезь") gets exactly that sound:
    force = ["rock"] / ["meow"] -> those extras always on, his other extras off."""
    if not c or not force:
        return c
    c = dict(c)
    ex = []
    for e in c.get("extras", []):
        e = dict(e)
        e["chance"] = 1.0 if (e.get("style") in force or e["kind"] in force) else 0.0
        ex.append(e)
    have = {e.get("style", e["kind"]) for e in ex} | {e["kind"] for e in ex}
    for k in force:
        if k not in have:
            ex.append({"kind": "music", "style": k, "db": -14} if k in ("retro", "rock", "pop", "dance", "hiphop",
                      "classic", "romance", "folk", "dutar", "uzpop", "course") else {"kind": k, "db": -14})
    c["extras"] = ex
    return c


def render(x, actor, far, rng, use_cab=True, force=None):
    if actor.get("fx") == "phone":
        return phone(x)
    x2 = cab.with_bed(x, forced_cab(actor.get("cab"), force) if use_cab else None, rng)
    return g.radio(x2, dict(actor.get("radio", {}), far=far), rng)


def seed(*parts):
    return np.random.default_rng(abs(hash("|".join(map(str, parts)))) % 2**32)


def main(argv):
    use_cab = "--nocab" not in argv
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    actors = data["actors"]
    if "--backup" in argv:
        b = A / f"_backup_{time.strftime('%Y%m%d_%H%M%S')}"
        for sub in ("level3", "scenes", "reactions", "fx"):
            for f in (A / sub).rglob("*.wav"):
                dst = b / f.relative_to(A)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dst)
        print("копия:", b)
    n = 0
    # singles (dropped ones are kept in level3_clean as NN_dropped.wav)
    for key, a in actors.items():
        drop = set(a.get("drop", []))
        for i in range(1, len(a["phrases"]) + 1):
            mp3 = src(A / "level3_clean" / key / f"{i:02d}", a)
            if not mp3:
                continue
            out = (A / "level3_clean" / key / f"{i:02d}_dropped.wav") if i in drop else (A / "level3" / key / f"{i:02d}.wav")
            item = a["phrases"][i - 1]
            force = item.get("cab") if isinstance(item, dict) else None
            sf.write(out, render(dry(mp3), a, False, seed(key, i), use_cab, force), g.SR)
            n += 1
    # scenes
    for sid, lines in data.get("scenes", {}).items():
        for i, ln in enumerate(lines, 1):
            mp3 = src(A / "scenes" / sid / f"{i:02d}", actors[ln["actor"]])
            if mp3:
                sf.write(A / "scenes" / sid / f"{i:02d}.wav",
                         render(dry(mp3), actors[ln["actor"]], ln.get("far", False), seed(sid, i), use_cab, ln.get("cab")), g.SR)
                n += 1
    # reactions
    def render_reactions(group, kind, lines):
        nonlocal n
        for i, ln in enumerate(lines, 1):
            mp3 = src(A / "reactions" / group / kind / f"{i:02d}", actors[ln["actor"]])
            if mp3:
                sf.write(A / "reactions" / group / kind / f"{i:02d}.wav",
                         render(dry(mp3), actors[ln["actor"]], ln.get("far", False), seed(group, kind, i), use_cab,
                                ln.get("cab")),
                         g.SR)
                n += 1

    for group, kinds in data.get("reactions", {}).items():
        if group.startswith("_"):
            continue
        for kind, lines in kinds.items():
            if kind.startswith("_"):
                continue
            if isinstance(lines, dict):
                # вложенные пулы (knows: <actor> -> <target> -> [lines]) -> плоские <actor>__<target>
                for sub, sublines in lines.items():
                    render_reactions(group, f"{kind}__{sub}", sublines)
            else:
                render_reactions(group, kind, lines)
    # kerchunks: somebody keys up in his cab and says nothing
    rng = np.random.default_rng(2026)
    keys = list(actors)
    for i in range(1, 9):
        a = actors[keys[i % len(keys)]]
        secs = rng.uniform(0.15, 0.8)
        x = cab.kerchunk_bed(secs, a.get("cab") if use_cab else None, rng)
        cfg = {"noise_db": rng.uniform(-30, -20), "far": bool(rng.integers(0, 2)), "roger_beep": i == 8}
        w = g.radio(x if np.any(x) else np.zeros(int(secs * g.SR), np.float32), cfg, rng) * rng.uniform(0.35, 0.7)
        sf.write(A / "fx" / f"kerchunk_{i:02d}.wav", w.astype(np.float32), g.SR)
        n += 1
    print(f"пересобрано файлов: {n} ({'с фоном кабины' if use_cab else 'без фона'})")


if __name__ == "__main__":
    main(sys.argv[1:])
