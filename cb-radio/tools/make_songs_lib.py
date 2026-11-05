"""Shared: generate songs with Lyria (gen_music) -> music/lyria_src/<name>.mp3 + music/<name>.wav (mono 22.05 kHz)."""
from math import gcd

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

import gen_music as gm

M = gm.ROOT / "music"


def to_wav(src, wav):
    x, sr = sf.read(src, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    g = gcd(22050, sr)
    y = resample_poly(x, 22050 // g, sr // g).astype(np.float32)
    sf.write(wav, y / (np.max(np.abs(y)) + 1e-9) * 0.9, 22050, subtype="PCM_16")
    return len(y) / 22050


def run(songs):
    total = 0.0
    for name, (style, lyrics) in songs.items():
        if (M / f"{name}.wav").exists():
            continue
        data, fmt, text, cost = gm.generate("song", f"{style}\nLyrics:\n{lyrics}")
        total += cost
        if not data:
            print(f"{name}: звука нет (${cost:.3f}) {text[:200]!r}", flush=True)
            continue
        src = M / "lyria_src" / f"{name}.{gm.ext_of(data, fmt)}"
        src.parent.mkdir(exist_ok=True)
        src.write_bytes(data)
        print(f"{name}: {to_wav(src, M / f'{name}.wav') / 60:.1f} мин, ${cost:.3f}", flush=True)
    print(f"итого ${total:.3f}")
