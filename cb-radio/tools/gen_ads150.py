# Пакетная озвучка 150 рекламных роликов через ElevenLabs Voice Design.
# Ограничения боевые: ключ 2 умеет voice_generation, но НЕ voices_write (удалять голоса нельзя),
# лимит библиотеки 30 слотов, занято 4 (пилотные). Поэтому голоса КЛАСТЕРНЫЕ: один голос на
# язык/персону (25 голосов), 4 пилотных переиспользованы как кластеры de/fr/it/pl.
# Резюм-безопасно: voice_map.json (кластеры) + manifest.json (ролики).
# Запуск: py -3 tools/gen_ads150.py [--limit N]
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ADS = ROOT.parent / "build" / "ads150"
OUT = ADS / "audio"
MANIFEST = ADS / "manifest.json"
VOICES = ADS / "voice_map.json"
LOG = ADS / "gen.log"
MODEL = "eleven_v4_turbo"  # 94 языка; sq (ролик 137) не покрывает — уходит на gpt-audio

KEY = (ROOT / "elevenlabs_key2.txt").read_text(encoding="utf-8").strip()

# Кластер -> (дизайн-промт, переиспользованный voice_id или None)
CLUSTERS = {
    "de":   ("Energetic, fast-talking German male radio ad announcer, humorous, raspy warmth", "s6NK3v1ugfwWiSTz9sPG"),
    "fr":   ("Witty, theatrical French male announcer, comedic disdain turning warm", "C7HNNAN5YvGcn3QOns5x"),
    "it":   ("Passionate, loud Italian male announcer, expressive, warm and jovial", "R4VWDXSmfNsHwve4GKQW"),
    "pl":   ("Loud, hyperactive Polish male bazaar vendor, energetic, persuasive", "J94WrnsOyh8js59PFDWz"),
    "es":   ("Cheerful, fast-talking Spanish male announcer, sunny and lively", None),
    "en":   ("Rowdy British male radio ad announcer, humorous, thick regional cheer", None),
    "fi":   ("Dry, deadpan Finnish male, slow and calm, absurdly serious", None),
    "ro":   ("Boisterous Romanian male showman, fast-talking, humorous", None),
    "sv":   ("Cheerful Swedish male announcer, bright and upbeat", None),
    "nl":   ("Relaxed, witty Dutch male shopkeeper, laid-back and cheerful", None),
    "no":   ("Polite, absurdly calm Norwegian male announcer, gently teasing", None),
    "lv":   ("Jolly, booming Latvian male announcer, hearty laugh", None),
    "lv_f": ("Wise, elderly Latvian herbalist woman, warm and persuasive", None),
    "lt":   ("Loud, excited Lithuanian male, rapid fire delivery", None),
    "et":   ("Thoughtful, slow Estonian male, dry academic wit", None),
    "bg":   ("Sunny, laid-back Bulgarian male vendor, cheerful", None),
    "pt":   ("Sunny, laid-back Portuguese male bartender, warm chuckle", None),
    "tr":   ("Rapid-fire, enthusiastic Turkish male tea-house host", None),
    "cs":   ("Cheerful Czech male announcer, witty and friendly", None),
    "hu":   ("Fast, cheerful Hungarian male spice vendor", None),
    "hu_f": ("Mysterious, theatrical Hungarian fortune teller woman, dramatic", None),
    "yu":   ("Booming, warm Balkan male announcer, hearty laugh, party-loving", None),
    "el":   ("Lively, persuasive Greek male port barker, energetic", None),
    "da":   ("Upbeat Danish male hot-dog vendor, cheerful", None),
    "lb":   ("Jolly, wealthy-sounding Luxembourgish male shopkeeper, friendly", None),
}

# Кластер по языку; исключения по номерам роликов
LANG2CLUSTER = {"de": "de", "fr": "fr", "it": "it", "pl": "pl", "es": "es", "en": "en",
                "fi": "fi", "ro": "ro", "sv": "sv", "nl": "nl", "no": "no", "lv": "lv",
                "lt": "lt", "et": "et", "bg": "bg", "pt": "pt", "tr": "tr", "cs": "cs",
                "sk": "cs", "hu": "hu", "sr": "yu", "hr": "yu", "bs": "yu", "el": "el",
                "da": "da", "lb": "lb"}
OVERRIDE = {15: "hu_f", 24: "lv_f", 137: "gpt-audio"}


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def api(method, url, payload=None, accept=None, tries=8):
    body = json.dumps(payload).encode() if payload is not None else None
    for attempt in range(1, tries + 1):
        req = urllib.request.Request(url, data=body, method=method,
            headers={"xi-api-key": KEY, "Content-Type": "application/json"}
                    | ({"Accept": accept} if accept else {}))
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                if "geo-restriction" in r.url:
                    raise RuntimeError("geo-restriction")
                return r.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:300]
            if e.code in (429, 500, 502, 503):
                log(f"  HTTP {e.code} попытка {attempt}/{tries}: {detail[:120]}")
                time.sleep(min(5 * attempt, 30))
                continue
            raise RuntimeError(f"HTTP {e.code}: {detail}") from None
        except Exception as e:
            log(f"  {type(e).__name__} попытка {attempt}/{tries}: {e}")
            time.sleep(min(5 * attempt, 30))
    raise RuntimeError(f"не удалось после {tries} попыток: {url}")


def main():
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None

    ads = json.load((ADS / "ads_150.json").open(encoding="utf-8"))
    manifest = json.load(MANIFEST.open(encoding="utf-8")) if MANIFEST.exists() else {}
    voice_map = json.load(VOICES.open(encoding="utf-8")) if VOICES.exists() else {}
    OUT.mkdir(parents=True, exist_ok=True)

    # 1. Создаём недостающие кластерные голоса (дизайн-текст — самый длинный ролик кластера)
    for cname, (prompt, reuse) in CLUSTERS.items():
        if cname in voice_map:
            continue
        if reuse:
            voice_map[cname] = {"voice_id": reuse, "reused": True}
            log(f"кластер {cname}: переиспользуем пилотный голос {reuse}")
            continue
        members = [a for a in ads if OVERRIDE.get(a["n"], LANG2CLUSTER.get(a["lang"])) == cname]
        if not members:
            continue
        design_text = max((a["foreign"] for a in members), key=len)
        while len(design_text) < 100:
            design_text += " " + design_text
        d = json.loads(api("POST", "https://api.elevenlabs.io/v1/text-to-voice/design",
                           {"voice_description": prompt, "text": design_text}))
        gvid = d["previews"][0]["generated_voice_id"]
        v = json.loads(api("POST", "https://api.elevenlabs.io/v1/text-to-voice",
                           {"voice_name": f"ads150_{cname}", "voice_description": prompt,
                            "generated_voice_id": gvid}))
        voice_map[cname] = {"voice_id": v["voice_id"], "reused": False}
        with VOICES.open("w", encoding="utf-8") as f:
            json.dump(voice_map, f, ensure_ascii=False, indent=1)
        log(f"кластер {cname}: создан голос {v['voice_id']}")

    with VOICES.open("w", encoding="utf-8") as f:
        json.dump(voice_map, f, ensure_ascii=False, indent=1)

    # 2. TTS всех роликов
    done = 0
    for ad in ads:
        n = ad["n"]
        if limit and done >= limit:
            break
        if str(n) in manifest and manifest[str(n)].get("status") == "ok":
            continue
        cluster = OVERRIDE.get(n, LANG2CLUSTER.get(ad["lang"]))
        if cluster == "gpt-audio":
            manifest[str(n)] = {"status": "skip", "engine": "gpt-audio"}
            continue
        vid = voice_map[cluster]["voice_id"]
        try:
            audio = api("POST", f"https://api.elevenlabs.io/v1/text-to-speech/{vid}",
                        {"text": ad["foreign"], "model_id": MODEL}, accept="audio/mpeg")
            (OUT / f"{n:03d}.mp3").write_bytes(audio)
            log(f"#{n} [{cluster}] OK {len(audio)} байт")
            manifest[str(n)] = {"status": "ok", "chars": len(ad["foreign"]), "cluster": cluster}
            done += 1
        except Exception as e:
            log(f"#{n} FAIL: {e}")
            manifest[str(n)] = {"status": "fail", "error": str(e)[:300]}
        with MANIFEST.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)

    log(f"готово: озвучено {done} роликов")


if __name__ == "__main__":
    main()
