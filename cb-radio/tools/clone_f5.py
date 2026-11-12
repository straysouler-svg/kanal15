"""Voice an actor with a cloned real voice (F5-TTS, local GPU, no credits) — clone_xtts.py twin.

  clone_f5.py <voice> <actor> [--live]
    voice  = folder in voices/ with f5_ref.wav + f5_ref.txt (reference clip + exact transcript)
    actor  = actor key in phrases/level3_eleven.json whose lines to voice
    --live = write straight into the live deck (audio/level3, scenes, reactions) instead of the
             alternative set audio/alt_<voice>/ (keep the ElevenLabs files as they are)

ElevenLabs [audio tags] and (stage directions) are removed, same as in clone_xtts.py.
Runs in the isolated venv build/venv-f5 (F5-TTS + torch cu126), NOT in the coop-buddy venv:
  build/venv-f5/Scripts/python.exe tools/clone_f5.py <voice> <actor> [--live]
Model files live in build/models/f5/ (model_last.safetensors + vocab.txt, F5TTS_Base).
ВАЖНО: чекпоинт — русский файнтюн на базе F5TTS_Base; с конфигом F5TTS_v1_Base выдаёт шум
(проверено 12.11: v1 + model_last = бормотание, Base + model_last = чисто, model_1250000 = музыка).
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
# torch живёт в coop-buddy venv и подключается через coop.pth; если .pth снесён — тот же путь явно
_COOP_SP = str(Path(__file__).resolve().parents[3] / "coop-buddy" / ".venv" / "Lib" / "site-packages")
if _COOP_SP not in sys.path:
    sys.path.append(_COOP_SP)
import gen_level3 as g  # noqa: E402
import remix  # noqa: E402

ROOT = g.ROOT
TAG = re.compile(r"\[[^\]]*\]\s*")
MODEL_DIR = Path(__file__).resolve().parents[2] / "build" / "models" / "f5"


def load_model(voice_dir, model_name="F5TTS_Base"):
    from f5_tts.api import F5TTS

    # torchaudio в связке venv-f5 -> coop-globals грузит референс через torchcodec, а его DLL не
    # находит FFmpeg -> падает. Нам нужен только wav 48k: читаем soundfile'ом и подменяем torchaudio.load.
    import torch
    import torchaudio

    def _load_sf(path, *args, **kwargs):
        x, sr = sf.read(str(path), dtype="float32", always_2d=True)   # (frames, ch)
        if x.shape[1] > 1:
            x = x.mean(axis=1)
        return torch.from_numpy(x.T.copy()), sr

    torchaudio.load = _load_sf

    model = F5TTS(
        model=model_name,
        ckpt_file=str(MODEL_DIR / "model_last.safetensors"),
        vocab_file=str(MODEL_DIR / "vocab.txt"),
        device="cuda",
    )
    ref_audio = str(voice_dir / "f5_ref.wav")
    with open(voice_dir / "f5_ref.txt", encoding="utf-8") as fh:
        ref_text = fh.read().strip()
    return model, ref_audio, ref_text


def say(m, text, seed=0):
    model, ref_audio, ref_text = m
    clean = re.sub(r"\([^)]*\)\s*", "", TAG.sub("", text)).strip()
    wav, sr, _ = model.infer(ref_audio, ref_text, clean, seed=seed)
    x = np.asarray(wav, dtype=np.float32)
    return (x if sr == g.SR else resample_poly(x, g.SR, sr).astype(np.float32)), clean


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
