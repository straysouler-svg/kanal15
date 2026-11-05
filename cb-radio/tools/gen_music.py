"""Cab radio songs with Google Lyria 3 via OpenRouter (2026-11-04). Generation only; playback stays offline.
  gen_music.py clip  <name> "<prompt>"     30 s clip,  ~$0.04  -> music/<name>.<ext>
  gen_music.py song  <name> "<prompt>"     full song, ~$0.08
Prompt = style description in English + "Lyrics:" with our own Russian text (no artist names)."""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = (ROOT / "openrouter_key.txt").read_text(encoding="utf-8").strip()
MODELS = {"clip": "google/lyria-3-clip-preview", "song": "google/lyria-3-pro-preview"}


def generate(kind, prompt, audio_cfg=None):
    body = {"model": MODELS[kind], "modalities": ["text", "audio"], "stream": True, "usage": {"include": True},
            "messages": [{"role": "user", "content": prompt}]}
    if audio_cfg:
        body["audio"] = audio_cfg
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    try:
        r = urllib.request.urlopen(req, timeout=600)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"OpenRouter {e.code}: {e.read().decode('utf-8', 'replace')[:400]}")
    data, text, cost, fmt = b"", "", 0.0, None
    for line in r:
        line = line.decode("utf-8", "replace").strip()
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        d = json.loads(line[6:])
        if d.get("usage"):
            cost = d["usage"].get("cost", 0.0) or cost
        for ch in d.get("choices", []):
            delta = ch.get("delta") or {}
            au = delta.get("audio") or {}
            if au.get("data"):
                data += base64.b64decode(au["data"])
                fmt = au.get("format", fmt)
            if au.get("transcript"):
                text += au["transcript"]
            if isinstance(delta.get("content"), str):
                text += delta["content"]
    return data, fmt, text, cost


def ext_of(b, fmt):
    if b[:4] == b"RIFF":
        return "wav"
    if b[:3] == b"ID3" or b[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "mp3"
    if b[:4] == b"OggS":
        return "ogg"
    if b[:4] == b"fLaC":
        return "flac"
    return fmt or "pcm"


if __name__ == "__main__":
    kind, name, prompt = sys.argv[1], sys.argv[2], sys.argv[3]
    out_dir = ROOT / "music"
    data, fmt, text, cost = generate(kind, prompt)
    if not data:
        raise SystemExit(f"звука нет. Текст ответа: {text[:300]!r}, ${cost}")
    e = ext_of(data, fmt)
    p = out_dir / f"{name}.{e}"
    p.write_bytes(data)
    print(f"{p.name}: {len(data) // 1024} КБ, формат {e}, ${cost:.3f}")
    if text.strip():
        print("текст модели:", text.strip()[:300])
