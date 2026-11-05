"""Generate level-3 CB chatter: Silero TTS -> CB radio effect -> WAV files.

Usage (coop-buddy venv python):
  gen_level3.py                 all actors, all phrases
  gen_level3.py stas            one actor
  gen_level3.py stas 3          one phrase (1-based)
Output: audio/level3_silero/<actor>/NN.wav (radio) and audio/level3_silero_clean/ (dry).
Fallback voices only: the live deck (audio/level3) is voiced by ElevenLabs, see gen_eleven.py.
To switch the radio back to Silero, copy audio/level3_silero/* over audio/level3/*.
"""
import json
import sys
from html import escape
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parents[1]
SR = 48000
_models = {}


def model(name):
    if name not in _models:
        imp = torch.package.PackageImporter(str(ROOT / "models" / f"{name}.pt"))
        m = imp.load_pickle("tts_models", "model")
        m.to(torch.device("cpu"))
        _models[name] = m
    return _models[name]


def synth(actor, text):
    m = model(actor["model"])
    ssml = (f'<speak><prosody pitch="{actor.get("pitch", "medium")}" '
            f'rate="{actor.get("rate", "medium")}">{escape(text)}</prosody></speak>')
    audio = m.apply_tts(ssml_text=ssml, speaker=actor["speaker"], sample_rate=SR)
    return audio.numpy().astype(np.float32)


# ---------------------------------------------------------------- radio FX
def _band(x, lo, hi, order=4):
    sos = butter(order, [lo, hi], btype="bandpass", fs=SR, output="sos")
    return sosfilt(sos, x)


def _noise(n, rng):
    """Hiss with a bit of low rumble, shaped like an AM CB channel."""
    white = rng.standard_normal(n)
    hiss = _band(white, 500, 4000, 2)
    rumble = _band(rng.standard_normal(n), 80, 300, 2) * 0.4
    return (hiss + rumble) / 2.0


def _db(v):
    return 10 ** (v / 20)


def radio(voice, cfg, rng):
    """Key-up click -> open carrier -> band-limited, driven voice -> squelch tail."""
    v = voice / (np.max(np.abs(voice)) + 1e-9)
    v = _band(v, 320, 3000)
    drive = cfg.get("drive", 1.8)
    v = np.tanh(v * drive) / np.tanh(drive)          # AM-ish saturation
    v = _band(v, 300, 3200, 2)                       # cut the harmonics again
    far = bool(cfg.get("far"))
    # slow fading, like a moving transmitter (deeper when far away)
    t = np.arange(len(v)) / SR
    depth = 0.38 if far else 0.12
    fade = 1.0 - depth * (0.5 + 0.5 * np.sin(2 * np.pi * rng.uniform(0.2, 0.6) * t + rng.uniform(0, 6.3)))
    v = v * fade
    if far:  # one or two short drop-outs of the signal
        for _ in range(rng.integers(1, 3)):
            n = int(rng.uniform(0.06, 0.15) * SR)
            s = int(rng.uniform(0.25, 0.85) * max(1, len(v) - n))
            v[s:s + n] *= np.concatenate([np.linspace(1, 0.12, n // 4), np.full(n - 2 * (n // 4), 0.12),
                                          np.linspace(0.12, 1, n // 4)])

    pre, post_tail = int(0.12 * SR), int(rng.uniform(0.18, 0.28) * SR)
    roger = int(0.16 * SR) if cfg.get("roger_beep") else 0
    total = pre + len(v) + roger + post_tail
    out = np.zeros(total)

    carrier = _noise(total, rng) * _db(cfg.get("noise_db", -30) + (9 if far else 0) + rng.uniform(-3, 3))
    carrier[: int(0.01 * SR)] *= np.linspace(0, 1, int(0.01 * SR))
    out += carrier[:]

    # key-up click: short DC thump + burst
    click = int(0.012 * SR)
    out[:click] += np.hanning(click * 2)[:click] * 0.35

    out[pre: pre + len(v)] += v * 0.85

    if roger:
        k = np.arange(roger)
        beep = np.concatenate([np.sin(2 * np.pi * 1200 * k[: roger // 2] / SR),
                               np.sin(2 * np.pi * 900 * k[roger // 2:] / SR)])
        env = np.minimum(1, np.minimum(k, roger - k) / (0.005 * SR))
        out[pre + len(v): pre + len(v) + roger] += _band(beep * env, 300, 3200, 2) * 0.25

    # squelch tail: loud burst of hiss when the other side lets go of the key
    s0 = pre + len(v) + roger
    tail = _noise(post_tail, rng) * 0.32
    tail *= np.linspace(1.0, 0.6, post_tail)
    out[s0:] = tail
    out[-int(0.004 * SR):] *= np.linspace(1, 0, int(0.004 * SR))  # hard cut, no click

    out = out / (np.max(np.abs(out)) + 1e-9) * _db(-3)
    return out.astype(np.float32)


# ---------------------------------------------------------------- main
def main(argv):
    data = json.loads((ROOT / "phrases" / "level3.json").read_text(encoding="utf-8"))
    actors = data["actors"]
    only = argv[0] if argv else None
    idx = int(argv[1]) if len(argv) > 1 else None
    for key, actor in actors.items():
        if only and key != only:
            continue
        rng = np.random.default_rng(abs(hash(key)) % 2**32)
        dry_dir = ROOT / "audio" / "level3_silero_clean" / key
        wet_dir = ROOT / "audio" / "level3_silero" / key
        dry_dir.mkdir(parents=True, exist_ok=True)
        wet_dir.mkdir(parents=True, exist_ok=True)
        for i, text in enumerate(actor["phrases"], 1):
            if idx and i != idx:
                continue
            dry = synth(actor, text)
            sf.write(dry_dir / f"{i:02d}.wav", dry, SR)
            wet = radio(dry, actor.get("radio", {}), rng)
            sf.write(wet_dir / f"{i:02d}.wav", wet, SR)
            print(f"{actor['name']} {i:02d}  {len(wet) / SR:4.1f}s  {text}")


if __name__ == "__main__":
    main(sys.argv[1:])
