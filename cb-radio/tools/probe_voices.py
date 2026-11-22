# -*- coding: utf-8 -*-
"""22.11: слепая проба базовых голосов для x_ru — 2 строки пула foreign.ru
(№29 «штрафы», №32 «обочечники») × 4 голоса (onyx, ash, sage, ballad / nova, shimmer).
Подача = style x_ru, кабина/радио = профиль x_ru. Только build/voice_probe/, пулы не трогаем.

  OR_BUDGET=0.3 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/probe_voices.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402
import gen_openrouter as gor  # noqa: E402
import remix  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "build" / "voice_probe"
OUT.mkdir(parents=True, exist_ok=True)

data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
a = data["actors"]["x_ru"]
ru = data["reactions"]["foreign"]["ru"]
lines = {29: ru[28]["text"], 32: ru[31]["text"]}

spent = 0.0
for n, text in lines.items():
    for voice in ("nova", "shimmer"):
        x, cost = gor.tts(text, voice, a.get("style", ""), lang="ru")
        spent += cost
        rng = np.random.default_rng(abs(hash(("probe", voice, n))) % 2**32)
        wet = remix.render(x, a, False, rng)
        f = OUT / f"base_{voice}_{n}.wav"
        sf.write(f, wet, ge.g.SR)
        print(f"{f.name}: {len(wet) / ge.g.SR:.1f}s ${cost:.4f}")
print(f"всего: ${spent:.3f}")
