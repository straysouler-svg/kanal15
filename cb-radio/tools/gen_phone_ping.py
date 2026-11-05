"""Messenger notification chime -> audio/fx/phone_ping.wav (played before the accountant's voice note)."""
import sys
from pathlib import Path
import numpy as np, soundfile as sf
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g
SR = g.SR
def tone(f, d, a=1.0):
    t = np.arange(int(d * SR)) / SR
    return a * np.sin(2 * np.pi * f * t) * np.exp(-t / (d / 3)) * np.minimum(1, t / 0.005)
x = np.concatenate([tone(1046, 0.16), np.zeros(int(0.03 * SR)), tone(1568, 0.28, 0.8)])
x = x / np.max(np.abs(x)) * 10 ** (-10 / 20)
sf.write(g.ROOT / "audio" / "fx" / "phone_ping.wav", x.astype(np.float32), SR)
print("phone_ping.wav", round(len(x) / SR, 2), "s")
