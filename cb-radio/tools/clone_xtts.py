"""Voice an actor with a cloned real voice (XTTS-v2, local GPU, no credits).

  clone_xtts.py <voice> <actor> [--live]
    voice  = folder in voices/ with raw48k.wav (the friend's recording, part 1 of the instruction)
    actor  = actor key in phrases/level3_eleven.json whose lines to voice
    --live = write straight into the live deck (audio/level3, scenes, reactions) instead of the
             alternative set audio/alt_<voice>/ (keep the ElevenLabs files as they are)

ElevenLabs [audio tags] and (stage directions) are removed: XTTS copies the manner of the reference
recording, it cannot act tags — and it READS "(смеётся)" aloud (found 2026-11-11, QA scan).
Coqui CPML licence (non-commercial) was accepted by the user on 2026-10-27 for coop-buddy.
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import resample_poly

os.environ["COQUI_TOS_AGREED"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402
import remix  # noqa: E402

ROOT = g.ROOT
TAG = re.compile(r"\[[^\]]*\]\s*")


def load_model(voice_dir):
    from TTS.api import TTS
    model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cuda").synthesizer.tts_model
    cache = voice_dir / "latents.pt"
    ref = voice_dir / "raw48k.wav"
    if cache.exists() and cache.stat().st_mtime >= ref.stat().st_mtime:
        lat = torch.load(cache)
        return model, lat["gpt"].to("cuda"), lat["spk"].to("cuda")
    a, sr = sf.read(ref, dtype="float32")
    a = a[int(3.5 * sr):]                                 # skip the silence before the first word
    a = a / (np.max(np.abs(a)) + 1e-9) * 0.9
    with torch.inference_mode():
        audio = torch.tensor(a)[None]
        gpt = model.get_gpt_cond_latents(audio, sr, length=45)
        spk = model.get_speaker_embedding(audio, sr)
    torch.save({"gpt": gpt.cpu(), "spk": spk.cpu()}, cache)
    return model, gpt, spk


def say(m, text, temperature=0.7):
    model, gpt, spk = m
    clean = re.sub(r"\([^)]*\)\s*", "", TAG.sub("", text)).strip()
    with torch.inference_mode():
        out = model.inference(clean, "ru", gpt, spk, temperature=temperature, speed=1.0,
                              enable_text_splitting=True)
    x = np.asarray(out["wav"], dtype=np.float32)
    return resample_poly(x, g.SR, 24000).astype(np.float32), clean


def main(argv):
    voice, actor_key = argv[0], argv[1]
    live = "--live" in argv
    vdir = ROOT / "voices" / voice
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    a = data["actors"][actor_key]
    m = load_model(vdir)
    base = ROOT / "audio" if live else ROOT / "audio" / f"alt_{voice}"
    jobs = []                                            # (out wav, text, far, seed parts)
    for i, t in enumerate(a["phrases"], 1):
        if i not in set(a.get("drop", [])):
            jobs.append((base / "level3" / actor_key / f"{i:02d}.wav", t, False, (actor_key, i)))
    for sid, lines in data.get("scenes", {}).items():
        for i, ln in enumerate(lines, 1):
            if ln["actor"] == actor_key:
                jobs.append((base / "scenes" / sid / f"{i:02d}.wav", ln["text"], ln.get("far", False), (sid, i)))
    for group, kinds in data.get("reactions", {}).items():
        if group.startswith("_"):
            continue
        for kind, lines in kinds.items():
            for i, ln in enumerate(lines, 1):
                if ln["actor"] == actor_key:
                    jobs.append((base / "reactions" / group / kind / f"{i:02d}.wav", ln["text"],
                                 ln.get("far", False), (group, kind, i)))
    for out, text, far, sp in jobs:
        x, clean = say(m, text)
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(out.with_name(out.stem + "_dry.wav") if not live else vdir / f"dry_{'_'.join(map(str, sp))}.wav", x, g.SR)
        sf.write(out, remix.render(x, a, far, remix.seed(*sp, voice)), g.SR)
        print(f"{out.relative_to(ROOT)}  {len(x) / g.SR:4.1f}s  {clean}")


if __name__ == "__main__":
    main(sys.argv[1:])
