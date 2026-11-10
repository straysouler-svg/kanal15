"""ElevenLabs TTS (v3 audio tags) -> CB radio effect.

  gen_eleven.py audition          one test phrase per candidate voice -> samples/eleven/
  gen_eleven.py level3 [actor]    voice CHANGED phrases of level3_eleven.json -> audio/level3/<actor>/NN.wav
  gen_eleven.py force [actor]     re-voice everything (spends credits)
  gen_eleven.py seed [actor]      mark current texts as voiced (no API calls)
Key: elevenlabs_key.txt (one line). Network is used only here, never in cb_radio.py.
"""
import io
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402  (radio FX, SR = 48000)
import remix  # noqa: E402  (cab background + radio FX: remix.render)

ROOT = g.ROOT
KEY = (ROOT / "elevenlabs_key.txt").read_text(encoding="utf-8").strip()
API = "https://api.elevenlabs.io/v1/text-to-speech/{vid}?output_format=mp3_44100_128"

# Free tier: only premade voices work via API (library voices -> 402 paid_plan_required).
CANDIDATES = {
    "mihalych": {"Bill": "pqHfZKP75CvOlQylNhV4", "Callum": "N2lVS1w4EtoT3dr4eOWO"},
    "stas": {"Liam": "TX3LPaxmHKxFdv7VOQHJ", "Roger": "CwhRBWXzGAHq8TQ4Fs17"},
    "yanek": {"Chris": "iP95p4xoKVk53GoZ742B", "Brian": "nPczCjzI2devNBz1zQrb"},
}
AUDITION = {
    "mihalych": "[clears throat] Анекдот слышали? [chuckles] Дальнобойщик спрашивает навигатор: куда едем? "
                "[pause] А тот ему: [deadpan] я думал, ты знаешь. [laughs]",
    "stas": "[excited] Пацаны, я сегодня на заправке хот-дог взял за шесть евро. [outraged] Шесть! "
            "[laughing] Он что, из золота?",
    "yanek": "[calm] Сосед мне говорит: дальнобой, это как отпуск. [pause] Только без моря. "
             "[sighs] И без отпуска. [chuckles softly]",
}


def tts(vid, text, model="eleven_v3", stability=0.5):
    body = json.dumps({"text": text, "model_id": model,
                       "voice_settings": {"stability": stability, "similarity_boost": 0.75}}).encode("utf-8")
    req = urllib.request.Request(API.format(vid=vid), data=body, method="POST",
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                mp3 = r.read()
            break
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")
            if e.code == 429 and attempt < 2:
                time.sleep(5)
                continue
            raise SystemExit(f"ElevenLabs {e.code}: {msg}")
    x, sr = sf.read(io.BytesIO(mp3), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != g.SR:
        x = resample_poly(x, g.SR, sr).astype(np.float32)
    return mp3, x


_xtts = {}
_whisper = []
_or_spent = [0.0]          # OpenRouter $ spent in this run (OR_BUDGET env = stop limit, default 1.0)

import re as _re_mod  # noqa: E402

XTTS_STRESS_RX = None


def xtts_fix_stress(text):
    """Фонетическая подмена коварных ударений (XTTS-клон): 'километр' -> 'киломеетр'. Только для синтеза."""
    global XTTS_STRESS_RX
    if XTTS_STRESS_RX is None:
        XTTS_STRESS_RX = _re_mod.compile("|".join(XTTS_STRESS), _re_mod.IGNORECASE)
    return XTTS_STRESS_RX.sub(lambda m: XTTS_STRESS[m.group(0).lower()], text)


XTTS_STRESS = {          # коварные слова для клона (ударение удвоением гласной), только синтез
    "километр": "киломеетр", "километра": "киломеетра", "километров": "киломеетров",
    "красивые": "красиивые", "красивый": "красиивый", "красивее": "красиивее",
    "договор": "договоор", "торты": "тоорты", "категор": "категоор",
}


def _heard_ratio(x, text):
    """How well Whisper hears the intended text in x (0..1) - catches XTTS mumbling/skips."""
    import difflib
    import re
    if not _whisper:
        from faster_whisper import WhisperModel
        import os
        # GPU: no cublas dll. "small" is ~3-4x faster than medium on CPU and fine for short Russian lines
        _whisper.append(WhisperModel(os.environ.get("QA_MODEL", "small"), device="cpu", compute_type="int8"))
    norm = lambda s: re.sub(r"[^а-яё ]", "", re.sub(r"\[[^\]]*\]", "", s.lower()).replace("ё", "е")  # noqa: E731
                            .replace("-", " ")).split()
    y = resample_poly(x, 16000, g.SR).astype(np.float32)
    heard = " ".join(s.text for s in _whisper[0].transcribe(y, language="ru", beam_size=5)[0])
    return difflib.SequenceMatcher(None, norm(text), norm(heard)).ratio()


def cut_rec(spec):
    """A real recording instead of synthesis: "rec41:3.75-8.55" = voices/<voice>/rec41_48k.wav from 3.75 s
    to 8.55 s (several ranges: "rec41:48.7-53.2+54.7-57.6", joined with a short breath pause)."""
    from scipy.signal import butter, sosfilt
    name, ranges = spec.split(":")
    voice_dir, name = (name.split("/") if "/" in name else ("tatiana", name))
    x, sr = sf.read(ROOT / "voices" / voice_dir / f"{name}_48k.wav", dtype="float32")
    parts = []
    for r in ranges.split("+"):
        s, e = (float(v) for v in r.split("-"))
        seg = x[int(s * sr): int(e * sr)].copy()
        f = int(0.015 * sr)
        seg[:f] *= np.linspace(0, 1, f)
        seg[-f:] *= np.linspace(1, 0, f)
        parts += [seg, np.zeros(int(0.35 * sr), np.float32)]
    y = np.concatenate(parts[:-1])
    y = sosfilt(butter(2, 80, btype="highpass", fs=sr, output="sos"), y).astype(np.float32)
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.89
    return y if sr == g.SR else resample_poly(y, g.SR, sr).astype(np.float32)


def voice(a, text, rec=None):
    """(mp3 bytes or None, dry 48 kHz audio, ElevenLabs chars spent). engine "xtts" = local clone,
    rec = cut from a real recording."""
    if rec:
        return None, cut_rec(rec), 0
    if a.get("engine") == "gpt-audio":
        import os
        import gen_openrouter as gor
        budget = float(os.environ.get("OR_BUDGET", "1.0"))
        if _or_spent[0] >= budget:
            raise SystemExit(f"бюджет OpenRouter {budget}$ исчерпан (потрачено {_or_spent[0]:.3f}$) — остановка")
        best = None
        lang = a.get("lang", "ru")
        for attempt in range(3):            # retry if a stage direction leaked or words don't match
            if _or_spent[0] >= budget:
                print(f"   бюджет {budget}$ исчерпан, беру лучший вариант")
                break
            x, cost = gor.tts(text, a["voice"], a.get("style", ""), a.get("model", "openai/gpt-audio"), lang)
            _or_spent[0] += cost
            if lang != "ru":                 # our Whisper check is Russian-only: one take, no retries
                print(f"   ({lang}) ${cost:.4f} (всего ${_or_spent[0]:.3f})")
                return None, x, 0
            ok, r, why = gor.check(x, text, a.get("style", ""))
            print(f"   попытка {attempt + 1}: ${cost:.4f} (всего ${_or_spent[0]:.3f}) {'OK' if ok else why}")
            if best is None or (ok, r) > (best[0], best[1]):
                best = (ok, r, x)
            if ok:
                break
        if best is None:
            raise SystemExit("бюджет OpenRouter исчерпан")
        if not best[0]:
            print("   ! так и не вышло чисто — послушать")
        return None, best[2], 0
    if a.get("engine") != "xtts":
        mp3, x = tts(a["voice_id"], text, a.get("model", "eleven_v3"), a.get("stability", 0.5))
        return mp3, x, len(text)
    import clone_xtts as cx
    v = a["voice"]
    # 1.33: коварные ударения у XTTS-клона (Сорока) — фонетическая подмена ТОЛЬКО в тексте для синтеза,
    # отображаемые тексты не трогаем (приём проекта «железяака» — удвоение ударной гласной).
    text = xtts_fix_stress(text)
    if v not in _xtts:
        _xtts[v] = cx.load_model(ROOT / "voices" / v)
    best = (-1.0, None)
    for _ in range(3):                      # XTTS sometimes swallows words: keep the best of 3
        x, clean = cx.say(_xtts[v], text, temperature=a.get("temperature", 0.65))
        r = _heard_ratio(x, clean)
        if r > best[0]:
            best = (r, x)
        if r >= 0.95:
            break
    if best[0] < 0.85:
        print(f"   ! распознаётся только на {best[0]:.2f} — послушать")
    return None, best[1], 0


def save_dry(base, mp3, x):
    """base = path without extension: NN.mp3 for ElevenLabs, NN_dry.wav for local voices."""
    if mp3:
        base.with_suffix(".mp3").write_bytes(mp3)
    else:
        sf.write(base.parent / f"{base.name}_dry.wav", x, g.SR)


CANDIDATES2 = {
    "lastochka": {"Laura": "FGY2WhTYpPnrIDTdsKH5", "Sarah": "EXAVITQu4vr4xnSDxMaL"},
    "boroda": {"Harry": "SOYHLrjzK2X1ezoPC6cr", "Adam": "pNInz6obpgDQGcFmaJgB"},
}
AUDITION2 = {
    "lastochka": "[sassy] Стасян, ты опять в эфире? [scoffs] Иди проспись, жених. [laughs] Ласточка, приём.",
    "boroda": "[aggressive] Мужики, на развязке полосатые с радаром! [laughs] А я сто десять валю, мне похер. Отбой.",
}


def audition(cands=None, texts=None, out_name="eleven"):
    cands, texts = cands or CANDIDATES, texts or AUDITION
    out = ROOT / "samples" / out_name
    out.mkdir(parents=True, exist_ok=True)
    for key, voices in cands.items():
        rng = np.random.default_rng(7)
        for name, vid in voices.items():
            mp3, x = tts(vid, texts[key])
            (out / f"{key}_{name}_clean.mp3").write_bytes(mp3)
            sf.write(out / f"{key}_{name}_radio.wav", g.radio(x, {"noise_db": -30, "drive": 1.8}, rng), g.SR)
            print(f"{key:10} {name:14} {len(x) / g.SR:4.1f} c")


def _sig(a, text):
    return f"{a['voice_id']}|{a.get('model', 'eleven_v3')}|{a.get('stability', 0.5)}|{text}"


def level3(only=None, force=False, seed=False):
    """Voice only phrases whose text/voice changed (manifest.json per actor) - saves free credits.
    seed=True: just record the current texts as already voiced."""
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    used = 0
    for key, a in data["actors"].items():
        if only and key != only:
            continue
        rng = np.random.default_rng(abs(hash(key)) % 2**32)
        wet = ROOT / "audio" / "level3" / key
        dry = ROOT / "audio" / "level3_clean" / key
        wet.mkdir(parents=True, exist_ok=True)
        dry.mkdir(parents=True, exist_ok=True)
        man_f = dry / "manifest.json"
        man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {}
        drop = set(a.get("drop", []))
        for i, item in enumerate(a["phrases"], 1):
            n = f"{i:02d}"
            rec = item.get("rec") if isinstance(item, dict) else None
            text = item["text"] if isinstance(item, dict) else item
            if rec:
                text = f"{text} @{rec}"         # signature changes if the cut changes
            if i in drop:  # out of the deck; manifest kept so it can come back without credits
                if (wet / f"{n}.wav").exists():
                    (wet / f"{n}.wav").replace(dry / f"{n}_dropped.wav")
                continue
            if (dry / f"{n}_dropped.wav").exists() and man.get(n) == _sig(a, text):
                (dry / f"{n}_dropped.wav").replace(wet / f"{n}.wav")
            if seed:
                man[n] = _sig(a, text)
                continue
            if not force and man.get(n) == _sig(a, text) and (wet / f"{n}.wav").exists():
                continue
            mp3, x, spent = voice(a, text, rec)
            save_dry(dry / n, mp3, x)
            cab_force = item.get("cab") if isinstance(item, dict) else None
            sf.write(wet / f"{n}.wav", remix.render(x, a, False, rng, force=cab_force), g.SR)
            man[n] = _sig(a, text)
            man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
            used += spent
            print(f"{a['name']} {n} {len(x) / g.SR:4.1f}s  {text}")
        # phrases removed from the list -> drop their audio so the deck won't play them
        for f in wet.glob("*.wav"):
            if f.stem.isdigit() and int(f.stem) > len(a["phrases"]):
                f.unlink()
                man.pop(f.stem, None)
        man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    if not only and not seed:
        used += scenes(data, force)
        used += reactions(data, force)
    print("seeded" if seed else f"озвучено символов: {used}")


def voice_lines(d, lines, data, force=False, label=""):
    """Voice a list of {actor, text, far?} into d/NN.wav (only changed ones). Returns chars used."""
    used = 0
    d.mkdir(parents=True, exist_ok=True)
    man_f = d / "manifest.json"
    man = json.loads(man_f.read_text(encoding="utf-8")) if man_f.exists() else {}
    for i, ln in enumerate(lines, 1):
        n = f"{i:02d}"
        a = data["actors"][ln["actor"]]
        sig = _sig(a, ln["text"]) + f"|far={bool(ln.get('far'))}" + (f"|rec={ln['rec']}" if ln.get("rec") else "")
        if not force and man.get(n) == sig and (d / f"{n}.wav").exists():
            continue
        rng = np.random.default_rng(abs(hash((str(d), i))) % 2**32)
        mp3, x, spent = voice(a, ln["text"], ln.get("rec"))
        save_dry(d / n, mp3, x)
        sf.write(d / f"{n}.wav", remix.render(x, a, ln.get("far", False), rng, force=ln.get("cab")), g.SR)
        man[n] = sig
        man_f.write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
        used += spent
        print(f"[{label}] {a['name']} {n} {len(x) / g.SR:4.1f}s  {ln['text']}")
    for f in d.glob("*.wav"):
        if f.stem.isdigit() and int(f.stem) > len(lines):
            f.unlink()
        elif f.stem.endswith("_dry") and f.stem[:2].isdigit() and int(f.stem[:2]) > len(lines):
            f.unlink()
    return used


def reactions(data, force=False):
    """audio/reactions/<group>/<kind>/NN.wav + index.json ({"actors": [...]})."""
    used = 0
    root = ROOT / "audio" / "reactions"
    for group, kinds in data.get("reactions", {}).items():
        if group.startswith("_"):
            continue
        for kind, lines in kinds.items():
            if kind.startswith("_"):
                continue
            d = root / group / kind
            used += voice_lines(d, lines, data, force, f"{group}/{kind}")
            (d / "index.json").write_text(json.dumps({"actors": [ln["actor"] for ln in lines]}), encoding="utf-8")
    return used


def scenes(data, force=False):
    """audio/scenes/<id>/NN.wav + scene.json (pauses). Re-voices only changed lines."""
    used = 0
    root = ROOT / "audio" / "scenes"
    for sid, lines in data.get("scenes", {}).items():
        d = root / sid
        used += voice_lines(d, lines, data, force, sid)
        (d / "scene.json").write_text(json.dumps(
            {"actors": [ln["actor"] for ln in lines], "pauses": [ln.get("pause", 0.8) for ln in lines]},
            ensure_ascii=False), encoding="utf-8")
    for d in root.glob("*"):  # scenes removed from the json
        if d.is_dir() and d.name not in data.get("scenes", {}):
            for f in d.glob("*"):
                f.unlink()
            d.rmdir()
    return used


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "audition"
    if cmd == "audition":
        audition()
    elif cmd == "audition2":
        audition(CANDIDATES2, AUDITION2, "eleven2")
    elif cmd in ("level3", "force", "seed"):
        args = [x for x in sys.argv[2:]]
        level3(args[0] if args else None, force=cmd == "force", seed=cmd == "seed")
