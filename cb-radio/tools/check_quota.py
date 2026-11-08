# Проверка остатков на ключах. Ключи не печатает — только балансы.
# Образец загрузки ключей — как в gen_eleven.py / gen_openrouter.py.
import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def get(url, key):
    req = urllib.request.Request(url, headers={"xi-api-key": key} if "elevenlabs" in url
                                 else {"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            if "geo-restriction" in r.url:
                raise RuntimeError("гео-блокировка ElevenLabs: VPN выходит в стране, которую "
                                   "сервис не обслуживает — смените регион VPN")
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read(200)!r}") from None
    except json.JSONDecodeError:
        # повторим вручную, чтобы увидеть, что прислали вместо JSON
        with urllib.request.urlopen(urllib.request.Request(url, headers=req.headers), timeout=30) as r:
            body = r.read(300)
            raise RuntimeError(f"не JSON (HTTP {r.status}, url {r.url}): {body!r}") from None


def elevenlabs():
    key = (ROOT / "elevenlabs_key.txt").read_text(encoding="utf-8").strip()
    d = get("https://api.elevenlabs.io/v1/user/subscription", key)
    used, limit = d.get("character_count"), d.get("character_limit")
    reset = (d.get("next_character_count_reset_unix") or 0) / 86400
    import datetime
    reset_d = datetime.datetime.fromtimestamp(d["next_character_count_reset_unix"]).date() \
        if d.get("next_character_count_reset_unix") else "?"
    print(f"ElevenLabs: {used:,} / {limit:,} символов (осталось {limit - used:,}), "
          f"тариф {d.get('tier')}, сброс {reset_d}")
    print(f"  voice cloning (instant): {d.get('can_use_instant_voice_cloning')}")


def openrouter():
    key = (ROOT / "openrouter_key.txt").read_text(encoding="utf-8").strip()
    d = get("https://openrouter.ai/api/v1/auth/key", key).get("data", {})
    usage, limit = d.get("usage"), d.get("limit")
    left = (limit - usage) if (usage is not None and limit is not None) else None
    print(f"OpenRouter: потрачено ${usage:.2f} / лимит ${limit:.2f}"
          + (f" (осталось ${left:.2f})" if left is not None else " (безлимит)"))


if __name__ == "__main__":
    for name, fn in (("ElevenLabs", elevenlabs), ("OpenRouter", openrouter)):
        try:
            fn()
        except Exception as e:
            print(f"{name}: не вышло ({e!r})")
