# -*- coding: utf-8 -*-
"""22.11: эксперимент V2V — принимает ли gpt-4o-audio-preview (OpenRouter) аудио-вход?
Референс: build/voice_probe/base_onyx_29.wav (тот же голос onyx). Два дубля ->
build/voice_probe/v2v_onyx_29_a.wav / _b.wav. Если аудио-вход отвергнут — скрипт падает
с ошибкой API, тогда делаем обходной вариант (смена ремарки подачи).

  OR_BUDGET=0.2 G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/probe_v2v.py
"""
import base64
import io
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402
import gen_openrouter as gor  # noqa: E402
import remix  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parent / "build" / "voice_probe"
REF = OUT / "base_onyx_29.wav"
a = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))["actors"]["x_ru"]
TEXT = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(
    encoding="utf-8"))["reactions"]["foreign"]["ru"][28]["text"]
STYLE = a.get("style", "")

x, sr = sf.read(REF, dtype="float32")
buf = io.BytesIO()
sf.write(buf, resample_poly(x, 16000, sr).astype(np.float32), 16000, format="WAV", subtype="PCM_16")
b64 = base64.b64encode(buf.getvalue()).decode()

for tag, note in (("a", "чуть мягче, разговорнее"), ("b", "чуть жёстче, напористее")):
    body = {"model": "openai/gpt-audio",
            "modalities": ["text", "audio"], "audio": {"voice": "onyx", "format": "pcm16"},
            "stream": True, "usage": {"include": True},
            "messages": [
                {"role": "system", "content": STYLE + ". Это твоя же готовая запись: переиграй реплику "
                 f"дословно заново, в своём исполнении, {note}."},
                {"role": "user", "content": [
                    {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}},
                    {"type": "text", "text": f"Переиграй дословно: «{TEXT}»"}]}]}
    req = gor.urllib.request.Request(gor.URL, data=json.dumps(body).encode(),
                                     headers={"Authorization": "Bearer " + gor.KEY,
                                              "Content-Type": "application/json"})
    r = gor.urllib.request.urlopen(req, timeout=180)
    pcm, cost = b"", 0.0
    for line in r:
        line = line.decode("utf-8", "replace").strip()
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        dd = json.loads(line[6:])
        if dd.get("usage"):
            cost = dd["usage"].get("cost", 0.0)
        for ch in dd.get("choices", []):
            au = (ch.get("delta") or {}).get("audio") or {}
            if au.get("data"):
                pcm += base64.b64decode(au["data"])
    y = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    if len(y) < 1000:
        raise SystemExit("пустой аудио-ответ — V2V не сработал")
    y = gor.trim(gor.resample_poly(y, 2, 1).astype(np.float32))
    rng = np.random.default_rng(abs(hash("v2v_" + tag)) % 2**32)
    f = OUT / f"v2v_onyx_29_{tag}.wav"
    sf.write(f, remix.render(y, a, False, rng), ge.g.SR)
    print(f"{f.name}: {len(y) / ge.g.SR:.1f}s ${cost:.4f}")
