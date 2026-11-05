"""2026-11-04: Граф (овчарка Веры «Кинолог») — лай и скулёж для кабины, ElevenLabs Sound Effects
-> audio/fx/graf_bark_N.wav, graf_whine_N.wav (48 kHz mono). Уже сделанные не переделывает.
Ключу нужно право Sound Effects (включено 2026-11-04)."""
import io
import json
import sys
import urllib.request
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
KEY = (ROOT / "elevenlabs_key.txt").read_text(encoding="utf-8").strip()
FX = ROOT / "audio" / "fx"
TAKES = {
    "graf_bark": ("An old German shepherd dog barks two or three times, deep and loud, inside a small truck cabin, "
                  "close to the microphone, no music, no other sounds", 1.8, 3),
    "graf_whine": ("An old German shepherd dog softly whines and sighs impatiently, close up inside a quiet truck "
                   "cabin, wants to go for a walk, no barking, no music", 2.5, 2),
}


def sfx(text, dur):
    req = urllib.request.Request("https://api.elevenlabs.io/v1/sound-generation",
                                 data=json.dumps({"text": text, "duration_seconds": dur,
                                                  "prompt_influence": 0.6}).encode("utf-8"),
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    FX.mkdir(parents=True, exist_ok=True)
    for prefix, (text, dur, n) in TAKES.items():
        for i in range(1, n + 1):
            out = FX / f"{prefix}_{i}.wav"
            if out.exists():
                continue
            mp3 = sfx(text, dur)
            (FX / f"{prefix}_{i}.mp3").write_bytes(mp3)
            x, sr = sf.read(io.BytesIO(mp3), dtype="float32")
            x = x.mean(axis=1) if x.ndim > 1 else x
            g = gcd(48000, sr)
            y = resample_poly(x, 48000 // g, sr // g).astype(np.float32)
            sf.write(out, y / (np.max(np.abs(y)) + 1e-9) * 0.9, 48000)
            print(out.name, f"{len(y) / 48000:.1f} с")


if __name__ == "__main__":
    main()
