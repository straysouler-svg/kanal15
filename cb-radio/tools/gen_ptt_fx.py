"""Sounds of the player's own push-to-talk (what you hear in your cab when you key the mic).

  audio/fx/ptt_press_beep.wav     key click + short beep
  audio/fx/ptt_press_click.wav    key click only
  audio/fx/ptt_release_roger.wav  roger beep (two tones) + squelch tail "кшш"
  audio/fx/ptt_release_hiss.wav   squelch tail only
config.json "ptt_sounds": {"press": "beep"|"click"|null, "release": "roger"|"hiss"|null, "volume": 0.5}
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402

SR = g.SR
OUT = g.ROOT / "audio" / "fx"
rng = np.random.default_rng(23)


def env(n, a=0.004, r=0.01):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    e[:na] = np.linspace(0, 1, na)
    e[-nr:] = np.linspace(1, 0, nr)
    return e


def tone(f, sec):
    n = int(sec * SR)
    t = np.arange(n) / SR
    # slightly square-ish, like a cheap radio beeper
    x = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 3 * f * t)
    return x * env(n)


def click():
    n = int(0.03 * SR)
    k = np.arange(n)
    thump = np.exp(-k / (0.004 * SR)) * np.sin(2 * np.pi * 180 * k / SR)
    tick = np.exp(-k / (0.0008 * SR)) * rng.standard_normal(n) * 0.6
    return (thump + tick) * 0.9


def hiss(sec, start=0.5, end=0.0):
    n = int(sec * SR)
    x = g._noise(n, rng) * 3.0
    return x * np.linspace(start, end, n) * env(n, 0.003, 0.02)


def save(name, x, peak_db=-6):
    x = g._band(x, 250, 4000, 2)
    x = x / (np.max(np.abs(x)) + 1e-9) * 10 ** (peak_db / 20)
    sf.write(OUT / name, x.astype(np.float32), SR)
    print(name, f"{len(x) / SR:.2f}s")


OUT.mkdir(parents=True, exist_ok=True)
gap = np.zeros(int(0.03 * SR))
save("ptt_press_click.wav", np.concatenate([click(), np.zeros(int(0.05 * SR))]))
save("ptt_press_beep.wav", np.concatenate([click(), gap, tone(1750, 0.07)]))
save("ptt_release_hiss.wav", np.concatenate([np.zeros(int(0.02 * SR)), hiss(0.22, 0.6, 0.15)]))
save("ptt_release_roger.wav", np.concatenate([tone(1250, 0.08), tone(950, 0.1), gap, hiss(0.22, 0.6, 0.15)]))
