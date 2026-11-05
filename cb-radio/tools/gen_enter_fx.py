"""'Somebody came into range' cue: a short burst of static with crackles (the squelch opening on a distant
carrier). audio/fx/enter_NN.wav, quiet. Played by cb_radio.py when a driver enters radio range."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402

SR = g.SR
OUT = g.ROOT / "audio" / "fx"
OUT.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(77)
for i in range(1, 7):
    dur = rng.uniform(0.35, 0.8)
    n = int(dur * SR)
    t = np.arange(n) / SR
    hiss = g._noise(n, rng) * 2.5
    # the carrier swells in and fades - not a clean on/off
    env = np.minimum(1, t / rng.uniform(0.03, 0.1)) * np.clip((dur - t) / rng.uniform(0.08, 0.25), 0, 1)
    env *= 0.7 + 0.3 * np.sin(2 * np.pi * rng.uniform(3, 9) * t + rng.uniform(0, 6))
    x = hiss * env
    # crackles: short clicks/pops at random moments
    for _ in range(rng.integers(3, 9)):
        s = rng.integers(0, max(1, n - 400))
        k = np.arange(rng.integers(40, 300))
        x[s:s + len(k)] += rng.uniform(-1, 1) * np.exp(-k / rng.uniform(10, 60)) * rng.uniform(0.5, 1.5)
    # sometimes a faint garbled voice-like murmur far away (band-limited, modulated)
    if rng.random() < 0.5:
        mur = g._band(rng.standard_normal(n), 400, 1200, 2) * (0.5 + 0.5 * np.sin(2 * np.pi * 5 * t)) * 0.6
        x += mur * env
    x = g._band(x, 280, 3500, 2)
    x = x / (np.max(np.abs(x)) + 1e-9) * 10 ** (-9 / 20)
    sf.write(OUT / f"enter_{i:02d}.wav", x.astype(np.float32), SR)
    print(f"enter_{i:02d}.wav {dur:.2f}s")
