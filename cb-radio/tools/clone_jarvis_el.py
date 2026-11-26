"""Джарвис (Вячеслав Баранов): клонирование через ElevenLabs Instant Voice Cloning.
Вход: build/jarvis/clips/*.wav (только реплики Джарвиса, чистые).
Делает: голос 'jarvis_baranov' -> voice_id в build/jarvis/voice.json,
затем пробные TTS-реплики -> build/jarvis/preview/*.wav.
Запуск из cb-radio: G:/Claude/gruzovichki/build/venv/Scripts/python.exe tools/clone_jarvis_el.py [--tts-only <voice_id>]
"""
import io
import json
import re
import sys
import time
import urllib.request
import uuid
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
KEYS = [f.read_text(encoding="utf-8").strip()
        for f in sorted(ROOT.glob("elevenlabs_key*.txt"), key=lambda p: p.name)
        if re.fullmatch(r"elevenlabs_key\d*\.txt", f.name)]
JARVIS = ROOT.parent / "build" / "jarvis"
PREVIEW = JARVIS / "preview"
PREVIEW.mkdir(parents=True, exist_ok=True)

LINES = [
    ("privet", "Доброе утро, сэр. Все системы Канала пятнадцать в норме. Погода за бортом — как заказывали."),
    ("boleet", "Сэр, чем сильнее вы сопротивляетесь, тем больнее будет."),
    ("obed", "Напоминаю: вы давно не ели. Рекомендую поставить греться обед, пока вы не голодный."),
    ("doklad", "Заряд реактора сорок восемь процентов. Сэр, позвольте заметить: это немного вызывающе."),
]


def _multipart(fields, files):
    boundary = uuid.uuid4().hex
    body = io.BytesIO()
    for name, val in fields:
        body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{val}\r\n'.encode())
    for name, path in files:
        data = path.read_bytes()
        body.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                   f'filename="{path.name}"\r\nContent-Type: audio/wav\r\n\r\n'.encode())
        body.write(data)
        body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode())
    return body.getvalue(), f"multipart/form-data; boundary={boundary}"


def api(url, data=None, headers=None, method=None):
    last = None
    for key in KEYS:
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"xi-api-key": key, **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400]
            print(f"  HTTP {e.code}: {detail}", flush=True)
            last = RuntimeError(detail)
            if e.code == 400:
                raise last
        except Exception as e:
            print(f"  {e}", flush=True)
            last = e
        time.sleep(3)
    raise last


def add_voice():
    clips = sorted((JARVIS / "clips").glob("*.wav"))
    assert clips, "нет клипов в build/jarvis/clips"
    total = 0.0
    for c in clips:
        x, sr = sf.read(c, dtype="float32")
        total += len(x) / sr
    print(f"клипов: {len(clips)}, суммарно {total:.0f} с")
    files = [("files", c) for c in clips]
    fields = [("name", "jarvis_baranov"),
              ("description", "Джарвис — русский дубляж (Вячеслав Баранов), для личного голосового моста")]
    body, ctype = _multipart(fields, files)
    resp = json.loads(api("https://api.elevenlabs.io/v1/voices/add", body, {"Content-Type": ctype}, "POST"))
    print("voice_id:", resp["voice_id"])
    (JARVIS / "voice.json").write_text(json.dumps(resp, ensure_ascii=False, indent=1), encoding="utf-8")
    return resp["voice_id"]


def tts(voice_id):
    for name, text in LINES:
        out = PREVIEW / f"jarvis_{name}.wav"
        if out.exists():
            continue
        payload = json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                              "voice_settings": {"stability": 0.72, "similarity_boost": 0.85,
                                                 "style": 0.15}}).encode()
        mp3 = api(f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}", payload,
                  {"Content-Type": "application/json"}, "POST")
        x, sr = sf.read(io.BytesIO(mp3), dtype="float32")
        x = x.mean(axis=1) if x.ndim > 1 else x
        sf.write(out, x, sr)
        print(f"{out.name}: {len(x)/sr:.1f} с", flush=True)
    print("прослушка:", PREVIEW)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--tts-only" in sys.argv:
        tts(sys.argv[sys.argv.index("--tts-only") + 1])
    else:
        tts(add_voice())
