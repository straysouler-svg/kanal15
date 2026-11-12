# -*- coding: utf-8 -*-
"""Проба F5-TTS для Сороки: одна реплика -> build/f5_probe_01.wav (сухой, 48 кГц) + Whisper score.
Продакшн-файлы не трогает. Запуск: build/venv-f5/Scripts/python.exe tools/f5_probe.py"""
import sys
import time
from pathlib import Path

import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import clone_f5  # noqa: E402
import gen_eleven  # noqa: E402

LINE = "Железяка, я навстречу, в двухстах метрах буду. Бибикни — сверюсь с расписанием, хи-хи."
OUT = Path(__file__).resolve().parents[1] / "build" / "f5_probe_01.wav"

m = clone_f5.load_model(clone_f5.ROOT / "voices" / "tatiana")
t0 = time.monotonic()
x, clean = clone_f5.say(m, LINE)
dt = time.monotonic() - t0
OUT.parent.mkdir(parents=True, exist_ok=True)
sf.write(OUT, x, clone_f5.g.SR)
r = gen_eleven._heard_ratio(x, clean)
print(f"wav: {OUT}  {len(x) / clone_f5.g.SR:.2f} с  (синтез {dt:.1f} с)")
print(f"whisper score: {r:.3f}")
print(f"clean: {clean}")
