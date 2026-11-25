"""Пробная генерация эмбиента для рекламы кафе: 1 короткий ролик SFX + замер квоты.
Запуск: из cb-radio: venv coop-buddy python tools/gen_ads_ambience_probe.py
"""
import io
import json
import re
import sys
import urllib.request
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
KEYS = [f.read_text(encoding="utf-8").strip()
        for f in sorted(ROOT.glob("elevenlabs_key*.txt"), key=lambda p: p.name)
        if re.fullmatch(r"elevenlabs_key\d*\.txt", f.name)]
OUT = ROOT.parent / "build" / "ads150" / "ambience"
OUT.mkdir(parents=True, exist_ok=True)


def sfx(text, dur):
    last = None
    for key in KEYS[1:]:  # ключ 2 первым: на нём квота
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/sound-generation",
            data=json.dumps({"text": text, "duration_seconds": dur,
                             "prompt_influence": 0.5}).encode(),
            headers={"xi-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:
            last = e
            print(f"  ключ не ответил: {e}")
    raise last


def quota():
    key = KEYS[1]
    req = urllib.request.Request("https://api.elevenlabs.io/v1/user/subscription",
                                 headers={"xi-api-key": key})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    return d["character_count"], d["character_limit"]


q0 = quota()
print(f"квота ключа 2 до: {q0[0]}/{q0[1]}")
mp3 = sfx("Busy roadside truck stop cafe interior ambience: quiet crowd murmur, dishes and cutlery "
          "clinking, coffee machine steaming occasionally, no music, no voices understandable, "
          "constant seamless background loop", 12.0)
q1 = quota()
print(f"квота ключа 2 после: {q1[0]}/{q1[1]}  (потрачено {q1[0]-q0[0]})")
(OUT / "probe_cafe.mp3").write_bytes(mp3)
x, sr = sf.read(io.BytesIO(mp3), dtype="float32")
x = x.mean(axis=1) if x.ndim > 1 else x
g = gcd(48000, sr)
y = resample_poly(x, 48000 // g, sr // g).astype(np.float32)
sf.write(OUT / "probe_cafe.wav", y / (np.max(np.abs(y)) + 1e-9) * 0.9, 48000)
print("готово:", OUT / "probe_cafe.wav", f"{len(y)/48000:.1f} с, RMS {np.sqrt((y**2).mean()):.3f}")
