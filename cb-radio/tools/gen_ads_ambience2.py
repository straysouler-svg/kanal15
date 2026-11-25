"""Персональный эмбиент под КАЖДЫЙ ролик рекламы (решение Дмитрия 25.11: фон = смысл рекламы).
Шаг 1: GigaChat-2-Pro пишет английский SFX-промпт по русскому тексту ролика -> ambience_prompts.json.
Шаг 2 (флаг --gen): генерация через ElevenLabs SFX -> build/ads150/ambience/ad_<NNN>.wav (48k mono).
Запуск из cb-radio: venv coop-buddy python tools/gen_ads_ambience2.py [--gen] [--limit N]
"""
import io
import json
import re
import sys
import time
import urllib.request
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

ROOT = Path(__file__).resolve().parents[1]
WS = ROOT.parent
KEYS = [f.read_text(encoding="utf-8").strip()
        for f in sorted(ROOT.glob("elevenlabs_key*.txt"), key=lambda p: p.name)
        if re.fullmatch(r"elevenlabs_key\d*\.txt", f.name)]
GIGA_KEY_F = WS / "build" / "gigachat_key.txt"
ADS_DIR = WS / "build" / "ads150"
OUT = ADS_DIR / "ambience"
OUT.mkdir(parents=True, exist_ok=True)
PROMPTS_F = ADS_DIR / "ambience_prompts.json"
DUR = 25.0

INSTR = (
    "Ты звукорежиссёр радиорекламы. По тексту рекламного ролика придумай ЗВУКОВОЙ ФОН (эмбиент), "
    "который будет играть за диктором. Фон обязан соответствовать смыслу: место действия ролика и его "
    "фирменная шутка должны угадываться на слух (например: шиномонтаж с пробками шампанского = гул "
    "компрессора, лязг инструмента, иногда хлопки пробок; забегаловка у парома = чайки, волны, гудок). "
    "Напиши ОДИН английский промпт для генератора звуковых эффектов: 1-2 предложения, перечисли "
    "3-5 конкретных звуков места + 1 фирменный звук из шутки ролика, если он звучащий. "
    "Всегда заканчивай фразой: ', no music, no distinct words, seamless background loop'. "
    "Ответ — только сам промпт, без пояснений и кавычек."
)


def giga_prompts(ads, have):
    from gigachat import GigaChat
    key = GIGA_KEY_F.read_text(encoding="utf-8").strip()
    out = dict(have)
    with GigaChat(credentials=key, verify_ssl_certs=False, scope="GIGACHAT_API_PERS",
                  model="GigaChat-2-Pro") as giga:
        for ad in ads:
            n = str(ad["n"])
            if n in out and out[n].get("prompt"):
                continue
            body = f"{ad.get('head', '')}\n{ad.get('name', '')}\n{ad.get('text', '')}"
            for attempt in range(3):
                try:
                    r = giga.chat(f"{INSTR}\n\nТекст ролика:\n{body}")
                    p = r.choices[0].message.content.strip().strip('"')
                    if not p.lower().endswith("seamless background loop"):
                        p = p.rstrip(". ") + ", no music, no distinct words, seamless background loop"
                    out[n] = {"prompt": p}
                    print(f"#{n}: {p[:110]}", flush=True)
                    break
                except Exception as e:
                    print(f"#{n} попытка {attempt+1}: {e}", flush=True)
                    time.sleep(5 * (attempt + 1))
            if len(out) % 10 == 0:
                PROMPTS_F.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    PROMPTS_F.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def sfx(text, dur):
    last = None
    for key in KEYS[1:]:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/sound-generation",
            data=json.dumps({"text": text, "duration_seconds": dur,
                             "prompt_influence": 0.6, "loop": True}).encode(),
            headers={"xi-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:
            last = e
            print(f"  ключ: {e}", flush=True)
    raise last


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    gen = "--gen" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    ads = json.load((ADS_DIR / "ads_150.json").open(encoding="utf-8"))
    have = json.load(PROMPTS_F.open(encoding="utf-8")) if PROMPTS_F.exists() else {}
    prompts = giga_prompts(ads, have)
    if not gen:
        print(f"промптов: {len(prompts)}/{len(ads)} — проверь {PROMPTS_F.name}, затем --gen")
        return
    made = 0
    for ad in ads:
        n = str(ad["n"])
        if limit and made >= limit:
            break
        out = OUT / f"ad_{int(n):03d}.wav"
        if out.exists() or n not in prompts:
            continue
        t0 = time.time()
        mp3 = sfx(prompts[n]["prompt"], DUR)
        (OUT / f"ad_{int(n):03d}.mp3").write_bytes(mp3)
        x, sr = sf.read(io.BytesIO(mp3), dtype="float32")
        x = x.mean(axis=1) if x.ndim > 1 else x
        g = gcd(48000, sr)
        y = resample_poly(x, 48000 // g, sr // g).astype(np.float32)
        sf.write(out, y / (np.max(np.abs(y)) + 1e-9) * 0.9, 48000)
        made += 1
        print(f"ad_{int(n):03d}: {len(y)/48000:.1f} с ({time.time()-t0:.0f} с)", flush=True)
    print(f"сгенерировано: {made}")


if __name__ == "__main__":
    main()
