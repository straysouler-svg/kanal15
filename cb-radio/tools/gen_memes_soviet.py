"""Voice memes 03/04 for 18 actors (approved drafts_memes_soviet_2026-11-10.md).

ElevenLabs is geo-blocked today, so the eight EL actors are voiced with gpt-audio via OpenRouter
using the casting table below (recast on EL when it returns: delete manifest 03/04 + files and run
gen_eleven.py level3). gpt-audio actors and Сорока (local XTTS clone) go through their standard engines.

English [tags] from level3_eleven.json are converted to Russian round-bracket remarks for prep():
sounds -> (смеётся), [pause] -> (пауза), manner words -> (восторженно) etc.
Whisper QA per line (>=0.8), trap words («збс», «Хёфн», «ауте») checked in the transcript;
on miss the line is respelled and regenerated (<=2 extra takes). Appends manifest.json and
index.json, never touches 01/02."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402
import gen_level3 as g  # noqa: E402
import gen_openrouter as gor  # noqa: E402
import remix  # noqa: E402

D = g.ROOT / "audio" / "reactions" / "memes"

# gpt-audio casting for the eight ElevenLabs actors (voice, style). Free standard voices only.
GPT_CAST = {
    "mihalych": ("onyx", "пожилой дальнобойщик за шестьдесят, хрипловатый, неторопливый, добродушный, с усмешкой"),
    "stas": ("verse", "молодой парень двадцати четырёх лет, балагур, тараторит, восторженный, блогер"),
    "yanek": ("alloy", "мужчина лет тридцати восьми, спокойный, обаятельный, уверенный, мягкий юмор, говорит ровно"),
    "lastochka": ("coral", "женщина лет сорока, энергичная, дерзкая, весёлая, говорит быстро, с характером"),
    "boroda": ("fable", "громкий напористый мужик под сорок, лихач и хвастун, говорит с азартом"),
    "rustam": ("ballad", "мужчина средних лет из Самарканда, говорит по-русски с лёгким восточным акцентом, тёплый, добродушный, как повар"),
    "bahti": ("ash", "парень двадцати шести лет, восторженный, эмоциональный, говорит как блогер, обращается «бро»"),
    "vera": ("sage", "женщина сорока пяти лет, сдержанная, суховатая, служила в МЧС, говорит коротко и по делу"),
}
FALLBACK_VOICE = {"mihalych": "fable", "rustam": "alloy", "bahti": "echo", "stas": "echo"}

TAG_RU = {  # english json tag -> russian remark for prep()
    "laughing": "(смеётся)", "laughs": "(смеётся)", "giggles": "(хихикает)",
    "pause": "(пауза)",
    "excited": "(восторженно)", "nervous": "(нервно)", "calm": "(спокойно)",
    "grumbling": "(ворча)", "dry": "(сухо)", "warming": "(ласково)",
    "precise": "(чётко и обстоятельно)", "smug": "(с самодовольной усмешкой)",
    "softly": "(мягко)", "gossipy": "(со смешинкой)", "sassy": "(дерзко и с улыбкой)",
    "loud": "(громко)", "wry": "(с кривой усмешкой)", "gently": "(нежно)",
    "soft": "(мягко)", "mocking": "(с издёвкой)", "quiet": "(тихо)",
    "cheerful": "(бодро и весело)", "sly": "(хитро)", "teasing": "(поддразнивая)",
    "rushed": "(торопливо)",
}
SOUND_TAGS = {"laughing", "laughs", "giggles", "pause"}
SOUNDS_RU = {"смеётся", "хихикает", "пауза"}

TRAPS = {  # trap word -> accepted heard variants (ё->е normalized, compacted)
    "збс": {"збс", "зэбээс"},
    "хёфн": {"хёфн", "хофн", "хёвн", "хоун", "хефн"},
    "ауте": {"ауте", "аут"},
}


def _compact(s):
    import re
    return re.sub(r"[^а-я0-9]", "", s)


def to_ru(text):
    import re
    def repl(m):
        w = m.group(1)
        return TAG_RU.get(w.lower(), "")
    return re.sub(r"\[(\w+)\]", repl, text)


def heard_text(x):
    from scipy.signal import resample_poly
    y = resample_poly(x, 16000, g.SR).astype(np.float32)
    return " ".join(s.text for s in ge._whisper[0].transcribe(y, language="ru", beam_size=5)[0]).lower().replace("ё", "е")


def trap_miss(x, text):
    """-> (missing_trap, heard) or None. Only checks traps present in the text."""
    h = _compact(heard_text(x))
    t = text.lower().replace("ё", "е")
    for word, ok in TRAPS.items():
        if word in t:
            if not any(_compact(v) in h for v in ok):
                return word, h
    return None


def respell(text):
    return (text.replace("Збс-збс", "Зэ-бэ-эс, зэ-бэ-эс")
            .replace("Хёфн", "Хьофн")
            .replace("Я в ауте", "Я в ауте, полном ауте"))


def gen_cfg(actor_key, a):
    if a.get("engine") == "gpt-audio":
        return a
    if a.get("engine") == "xtts":
        return {"engine": "xtts", "voice": a["voice"], "temperature": a.get("temperature", 0.65)}
    voice, style = GPT_CAST[actor_key]
    return {"engine": "gpt-audio", "voice": voice, "style": style,
            "voice_id": f"gpt-audio:{voice}", "model": "eleven_v3", "stability": 0.5}


def voice_gpt(text, cfg):
    """gpt-audio with Whisper QA, <=3 takes. Returns (audio, spent, ok, why)."""
    best = None
    spent = 0.0
    for attempt in range(3):
        x, cost = gor.tts(text, cfg["voice"], cfg.get("style", ""))
        spent += cost
        ge._or_spent[0] += cost
        ok, r, why = gor.check(x, text, cfg.get("style", ""))
        print(f"   попытка {attempt + 1}: ${cost:.4f} (всего ${ge._or_spent[0]:.3f}) {'OK' if ok else why}")
        if best is None or (ok, r) > (best[0], best[1]):
            best = (ok, r, x)
        if ok:
            break
    return best[2], spent, best[0], "" if best[0] else "ratio<0.8"


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    data = json.loads((g.ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    memes = data["reactions"]["memes"]
    total = 0.0
    respelled = []
    for actor_key, lines in memes.items():
        if only and actor_key != only:
            continue
        new_lines = lines[2:]          # 03/04 appended by append_memes_soviet_texts.py
        if not new_lines:
            continue
        a = data["actors"][actor_key]
        cfg = gen_cfg(actor_key, a)
        d = D / actor_key
        man_f = d / "manifest.json"
        man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {}
        idx = json.loads((d / "index.json").read_text(encoding="utf-8"))
        for off, ln in enumerate(new_lines, 3):
            n = f"{off:02d}"
            text = ln["text"]
            sig = (f"{cfg.get('voice_id', cfg['engine'] + ':' + cfg['voice'])}|{cfg.get('model', 'eleven_v3')}|{cfg.get('stability', 0.5)}"
                   f"|{text}|far=False")
            if man.get(n) == sig and (d / f"{n}.wav").exists():
                print(f"{actor_key} {n}: уже озвучено, пропуск")
                continue
            ru = to_ru(text)
            print(f"{actor_key} {n}: {ru}")
            if cfg["engine"] == "gpt-audio":
                x, spent, ok, why = voice_gpt(ru, cfg)
                total += spent
                miss = trap_miss(x, ru)
                tries = 0
                while ok and miss and tries < 2:
                    tries += 1
                    ru2 = respell(ru)
                    print(f"   ловушка «{miss[0]}» (слышно: ...{miss[1][-40:]}) — переспеллинг, попытка {tries}")
                    x2, spent2, ok2, _ = voice_gpt(ru2, cfg)
                    total += spent2
                    miss2 = trap_miss(x2, ru2)
                    if ok2 and (miss2 is None or trap_miss(x2, ru) is None):
                        x, ok = x2, ok2
                        miss = None
                        respelled.append(f"{actor_key}/{n}")
                    else:
                        miss = miss2 or miss
                if miss:
                    print(f"   ! ловушка «{miss[0]}» не решена — оставляю лучший вариант, послушать")
            else:  # xtts (Сорока), локально; clone_xtts сам вырезает [теги] — даём исходный текст
                _, x, _ = ge.voice(cfg, text)
            sf.write(d / f"{n}_dry.wav", x, g.SR)
            rng = np.random.default_rng(abs(hash((str(d), off))) % 2**32)
            sf.write(d / f"{n}.wav", remix.render(x, a, False, rng), g.SR)
            man[n] = sig
            man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
            idx["actors"].append(actor_key)
            (d / "index.json").write_text(json.dumps(idx), encoding="utf-8")
            print(f"   -> {d.name}/{n}.wav {len(x) / g.SR:.1f}s")
    print(f"итого потрачено OpenRouter: ${total:.3f}")
    if respelled:
        print("переспеллинг сработал:", ", ".join(respelled))


if __name__ == "__main__":
    main()
