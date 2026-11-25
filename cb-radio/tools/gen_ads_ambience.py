"""Пул эмбиентов для рекламы кафе (ElevenLabs Sound Effects, квоту не ест — замер 25.11).
Генерирует 2 дубля x 22 с на каждый тип атмосферы -> build/ads150/ambience/<type>_<1,2>.wav (48k mono).
Плюс пишет build/ads150/ambience_map.json: номер ролика -> тип эмбиента (правила по ключевым словам).
Запуск из cb-radio: venv coop-buddy python tools/gen_ads_ambience.py [только_тип]
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
KEYS = [f.read_text(encoding="utf-8").strip()
        for f in sorted(ROOT.glob("elevenlabs_key*.txt"), key=lambda p: p.name)
        if re.fullmatch(r"elevenlabs_key\d*\.txt", f.name)]
ADS_DIR = ROOT.parent / "build" / "ads150"
OUT = ADS_DIR / "ambience"
OUT.mkdir(parents=True, exist_ok=True)
DUR, TAKES = 22.0, 2

POOL = {
    "cafe": "Roadside truck stop cafe interior ambience: soft crowd murmur, dishes and cutlery clinking, "
            "coffee machine steaming sometimes, no music, no distinct words, seamless background",
    "diner": "Big canteen hall ambience: trays and cutlery clatter, many people eating and talking softly, "
             "large room reverb, no music, no distinct words, seamless background",
    "garage": "Auto repair workshop ambience: impact wrench short bursts, metal tools clanking, car engine "
              "idling in the bay, radio very faint, no music, seamless background",
    "tire": "Tire service shop ambience: air compressor hum, impact gun short bursts, wheel balancing machine "
            "spinning, rubber and metal sounds, no voices, seamless background",
    "gas": "Gas station ambience: car engines idling, fuel pump handle clicks and beeps, distant highway "
           "traffic, light wind, no music, seamless background",
    "port": "Seaport ambience: seagulls crying, distant ship horn, water lapping against the pier, container "
            "crane far away, steady sea wind, seamless background",
    "ferry": "Ferry deck ambience: strong sea wind, deep engine rumble, waves splashing against the hull, "
             "seagulls far away, no voices, seamless background",
    "beach": "Sunny beach ambience: gentle sea waves rolling in, seagulls, distant happy people and children, "
             "soft wind, no music, seamless background",
    "mountain": "High mountain pass ambience: strong steady wind gusts, sparse alpine birds, distant cowbells, "
                "cold thin air feeling, no voices, seamless background",
    "farm": "Farmyard ambience: chickens clucking, a rooster far away, a cow mooing sometimes, a tractor "
            "idling, light wind in grass, seamless background",
    "market": "Covered food market ambience: dense crowd murmur, faint seller calls, shopping trolley wheels, "
              "paper bags rustling, large hall acoustics, no distinct words, seamless background",
    "bar": "Cosy pub evening ambience: warm crowd murmur, beer glasses clinking, soft laughter, very faint "
           "background music, no distinct words, seamless background",
    "bakery": "Small bakery interior ambience: oven door opening, metal trays, paper bags rustling, a quiet "
              "door bell sometimes, morning calm, no music, seamless background",
    "spa": "Thermal spa ambience: gentle water splashing, steam room door, echoing tiled hall, water dripping, "
           "calm and quiet, no voices, seamless background",
    "blizzard": "Arctic blizzard ambience: howling wind, strong snow gusts, cold winter storm outside, "
                "no voices, seamless background",
    "rain": "Rainy highway ambience: steady rain on asphalt, wet car tires passing, very distant thunder, "
            "no voices, seamless background",
    "traffic": "Highway roadside ambience: trucks and cars passing at speed, doppler whooshes, steady wind "
               "in the grass, daytime, no voices, seamless background",
}


def sfx(text, dur):
    last = None
    for key in KEYS[1:]:
        req = urllib.request.Request(
            "https://api.elevenlabs.io/v1/sound-generation",
            data=json.dumps({"text": text, "duration_seconds": dur,
                             "prompt_influence": 0.5, "loop": True}).encode(),
            headers={"xi-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return r.read()
        except Exception as e:
            last = e
            print(f"  ошибка ключа: {e}", flush=True)
    raise last


# --- маппинг роликов на типы эмбиента: правила по приоритету, первое совпадение
RULES = [
    ("tire", r"шиномонтаж|шин[ыу]|колес|колёс|прокол|балансиров|подкач|запаск|резин[ауы]"),
    ("garage", r"\bсто\b|автосервис|мастерск|гараж|ремонт|механик|мойк[ауи]|детейлинг|сход-?развал|"
               r"диагностик|эвакуатор|стапел|покраск|жестянк|масл[оа] в коробк|тормоз"),
    ("gas", r"заправк|топлив|дизел|бензин|adblue|газометр"),
    ("ferry", r"паром|переправ|трап\b|на борт|кают|палуб"),
    ("port", r"\bпорт|гаван|маяк|терминал|причал|контейнер|кран[ыов]?\b|бюро"),
    ("beach", r"пляж|песок|шезлонг|загар|прибой|мор[ея]\b|креветк|солярий|купан|пальм"),
    ("farm", r"ферм|сыр[оа]?\b|коров|коз[аы]|молок|эко|деревен|огород|фермер"),
    ("market", r"рын[оа]к|ярмарк|базар|барахолк|сувенир|лавк[ауе]|торг\b|обменник|вещев"),
    ("bar", r"\bбар\b|\bпаб|клуб|дискотек|караоке|ночн|казино|вин[оа]\b|пивовар|пив[оа]\b|виски|сидр"),
    ("bakery", r"пекарн|выпечк|круассан|булоч|хлеб|багет|пирог[иов]|брецель|пончик|булк[ау]"),
    ("spa", r"саун|бан[яие]|спа\b|терм[ыа]|бассейн|массаж|купель|источник|гряз[ье]"),
    ("mountain", r"горн|перевал|трамплин|серпантин|высот|альп|подъ[её]м|канатн|фуникул[её]р|спуск\b"),
    ("rain", r"дожд|ливен|гроз[аы]|шторм|зонт"),
    ("blizzard", r"снег|вьюг|метел|мороз|полярн|олен|северн|айсберг|вулкан|гейзер|исланд|аркти|ночь полярн"),
    ("traffic", r"стоянк|паркинг|парковк|трасс|автобан|шоссе|обочин|тир-?парк|развязк|кольц[оа]|пробк[ауи]|"
                r"скорост|ограничени|платн[ауы]|дорог[ауи]"),
    ("diner", r"столов|шведск|бизнес-?ланч|комплексн|столовая|придорожн[а-я]+ (еда|кухн)"),
    ("cafe", r"кафе|закусочн|таверн|ресторан|бистро|стейк|суши|пицц|шаурм|бургер|гриль|еда\b|завтрак|обед|"
             r"ужин|кофе|чай|чайхан|кофейн|кухн[яи]|меню|повар|суп|борщ|плов|сосиск|выпечк"),
]


def classify(ad):
    text = f"{ad.get('head', '')} {ad.get('name', '')} {ad.get('text', '')}".lower()
    for kind, pat in RULES:
        if re.search(pat, text):
            return kind
    return "cafe"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    only = sys.argv[1] if len(sys.argv) > 1 else None
    ads = json.load((ADS_DIR / "ads_150.json").open(encoding="utf-8"))
    amap = {str(a["n"]): classify(a) for a in ads}
    (ADS_DIR / "ambience_map.json").write_text(
        json.dumps(amap, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    from collections import Counter
    print("маппинг:", dict(Counter(amap.values())))

    for kind, prompt in POOL.items():
        if only and kind != only:
            continue
        for i in range(1, TAKES + 1):
            out = OUT / f"{kind}_{i}.wav"
            if out.exists():
                continue
            t0 = time.time()
            mp3 = sfx(prompt, DUR)
            (OUT / f"{kind}_{i}.mp3").write_bytes(mp3)
            x, sr = sf.read(io.BytesIO(mp3), dtype="float32")
            x = x.mean(axis=1) if x.ndim > 1 else x
            g = gcd(48000, sr)
            y = resample_poly(x, 48000 // g, sr // g).astype(np.float32)
            sf.write(out, y / (np.max(np.abs(y)) + 1e-9) * 0.9, 48000)
            print(f"{kind}_{i}: {len(y)/48000:.1f} с ({time.time()-t0:.0f} с)", flush=True)


if __name__ == "__main__":
    main()
