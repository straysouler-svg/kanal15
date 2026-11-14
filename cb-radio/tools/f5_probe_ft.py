# -*- coding: utf-8 -*-
"""Проба F5-TTS с конкретным чекпоинтом дообучения (не трогает продакшн):
  build/venv-f5/Scripts/python.exe tools/f5_probe_ft.py [ckpt.pt] [prefix]
Пишет cb-radio/build/<prefix>_1.wav, <prefix>_2.wav + whisper score по каждому."""
import sys
import time
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clone_f5  # noqa: E402
import gen_eleven  # noqa: E402

ROOT = clone_f5.ROOT
CKPT = sys.argv[1] if len(sys.argv) > 1 else str(
    ROOT.parent / "build" / "venv-f5" / "Lib" / "ckpts" / "tatiana" / "model_last.pt")
PREFIX = sys.argv[2] if len(sys.argv) > 2 else "f5_ckpt"

LINES = [
    "Железяка, я навстречу, в двухстах метрах буду. Бибикни — сверюсь с расписанием, хи-хи.",
    "Привет, это Сорока! Еду по эм четыре, километров сорок до поворота. Как слышно, приём?",
]

m = clone_f5.load_model(ROOT / "voices" / "tatiana", ckpt_file=CKPT)
for i, line in enumerate(LINES, 1):
    t0 = time.monotonic()
    x, clean = clone_f5.say(m, line)
    dt = time.monotonic() - t0
    out = ROOT / "build" / f"{PREFIX}_{i}.wav"
    sf.write(out, x, clone_f5.g.SR)
    r = gen_eleven._heard_ratio(x, clean)
    print(f"wav: {out}  {len(x) / clone_f5.g.SR:.2f} с  (синтез {dt:.1f} с)")
    print(f"whisper score: {r:.3f}")
    print(f"clean: {clean}")
