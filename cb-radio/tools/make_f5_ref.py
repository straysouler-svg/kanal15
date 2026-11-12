# -*- coding: utf-8 -*-
"""Одноразово: вырезать референс для F5 из voices/tatiana/rec41_48k.wav -> voices/tatiana/f5_ref.wav.
Сегмент 72.50-83.68: 11.2 с сплошной речи (по rec41_transcript.json), без пауз-обрывов."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt

ROOT = Path(__file__).resolve().parents[1]
src = ROOT / "voices" / "tatiana" / "rec41_48k.wav"
dst = ROOT / "voices" / "tatiana" / "f5_ref.wav"

x, sr = sf.read(src, dtype="float32")
assert sr == 48000, sr
seg = x[int(72.50 * sr): int(83.68 * sr)].copy()
f = int(0.02 * sr)
seg[:f] *= np.linspace(0, 1, f)
seg[-f:] *= np.linspace(1, 0, f)
seg = sosfilt(butter(2, 80, btype="highpass", fs=sr, output="sos"), seg).astype(np.float32)
seg = seg / (np.max(np.abs(seg)) + 1e-9) * 0.9
sf.write(dst, seg, sr)
print(dst, f"{len(seg)/sr:.2f}s peak={np.abs(seg).max():.2f}")
