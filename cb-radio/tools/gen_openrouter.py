"""Voice lines with OpenAI gpt-audio via OpenRouter (pre-generation only; playback stays offline).

Stage directions in round brackets - (смеётся), (вздыхает) - are ACTED, never read out.
  gen_openrouter.py test            three test lines -> samples/openrouter_full/
Key: openrouter_key.txt. Audio output on OpenRouter requires stream=true, pcm16 24 kHz.
Also: listen(wav, question) - ask an audio-input model about a file ("ears" for QA).
"""
import base64
import io
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402
import remix  # noqa: E402

ROOT = g.ROOT
KEY = (ROOT / "openrouter_key.txt").read_text(encoding="utf-8").strip()
URL = "https://openrouter.ai/api/v1/chat/completions"

SYSTEM = ("Ты озвучиваешь реплику водителя в CB-рации. Твой ответ — ТОЛЬКО эта реплика голосом, по-русски, "
          "дословно, с первого её слова до последнего. Ничего не говори от себя: никаких «понял», «начинаю», "
          "подтверждений, вступлений и пояснений. Не произноси вслух ремарки и описание манеры. "
          "В тексте в круглых скобках бывают только звуки, их исполняй голосом, а не читай: (смеётся) — живой смех, "
          "(усмехается) — короткий смешок, (вздыхает) — вздох, (зевает) — зевок, (покашливает) — кашель. "
          "Многоточие — пауза или запинка. Персонаж: ")

# sounds the model can act; everything else in brackets is a manner word -> moved out of the text
SOUNDS = {"смеётся": "смеётся", "смеется": "смеётся", "усмехается": "усмехается", "вздыхает": "вздыхает",
          "зевает": "зевает", "покашливает": "покашливает", "откашливается": "покашливает",
          "охает": "вздыхает", "стонет": "вздыхает", "выдыхает": "вздыхает"}


def prep(text):
    """Split stage directions: (пауза) -> '...', manner words -> separate instruction, keep only sounds.
    Returns (text for the model, manner list, list of all remark words for QA)."""
    import re
    manner, words = [], []

    def repl(m):
        parts = m.group(1).lower().split()
        words.extend(parts)
        if parts == ["пауза"]:
            return "..."
        snd = [SOUNDS[p] for p in parts if p in SOUNDS]
        manner.extend(p for p in parts if p not in SOUNDS)
        return f"({snd[0]})" if snd else ""

    t = re.sub(r"\(([^)]*)\)", repl, text)
    t = re.sub(r"\s+", " ", t).replace(" .", ".").replace(" ,", ",").strip()
    return t, manner, words


def trim(x, sr=48000, keep=0.12):
    """Cut silence at both ends (gpt-audio sometimes leaves 1-3 s)."""
    idx = np.nonzero(np.abs(x) > 0.02 * (np.max(np.abs(x)) + 1e-9))[0]
    if not len(idx):
        return x
    s, e = max(0, idx[0] - int(keep * sr)), min(len(x), idx[-1] + int(keep * sr))
    return x[s:e]


def _post(body):
    req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    try:
        return urllib.request.urlopen(req, timeout=180)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"OpenRouter {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")


LANGS = {"de": "по-немецки", "pl": "по-польски", "fr": "по-французски", "es": "по-испански",
         "it": "по-итальянски", "nl": "по-нидерландски", "cs": "по-чешски"}


def tts(text, voice, style, model="openai/gpt-audio", lang="ru"):
    """-> (48 kHz float32 audio, cost $). Stage directions are prepared by prep()."""
    t, manner, _ = prep(text)
    # the line goes into the instruction, not as a user message: lines that are questions ("Петровна, вы умеете…?")
    # were otherwise ANSWERED by the model instead of being voiced
    base = SYSTEM if lang == "ru" else SYSTEM.replace("по-русски", LANGS.get(lang, "на родном языке") +
                                                      " (носитель языка, без русского акцента)")
    sys_text = (base + style + (f". Эту реплику произнеси {', '.join(manner)}." if manner else "")
                + f"\n\nРеплика (произнеси её дословно, это не вопрос к тебе): «{t}»")
    r = _post({"model": model, "modalities": ["text", "audio"], "audio": {"voice": voice, "format": "pcm16"},
               "stream": True, "usage": {"include": True},
               "messages": [{"role": "system", "content": sys_text},
                            {"role": "user", "content": "Произнеси реплику."}]})
    pcm, cost = b"", 0.0
    for line in r:
        line = line.decode("utf-8", "replace").strip()
        if not line.startswith("data: ") or line == "data: [DONE]":
            continue
        d = json.loads(line[6:])
        if d.get("usage"):
            cost = d["usage"].get("cost", 0.0)
        for ch in d.get("choices", []):
            au = (ch.get("delta") or {}).get("audio") or {}
            if au.get("data"):
                pcm += base64.b64decode(au["data"])
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768
    return trim(resample_poly(x, 2, 1).astype(np.float32)), cost


def check(x, text, style=""):
    """Whisper QA for a gpt-audio line: (ok, ratio, problem). Fails if a stage direction, a word of the
    character description or assistant chatter was spoken, or the words don't match."""
    import re
    import gen_eleven as ge
    t, manner, words = prep(text)
    words = words + [w for w in re.findall(r"[а-яё]{5,}", style.lower())]
    spoken_ref = re.sub(r"\([^)]*\)", "", t)
    r = ge._heard_ratio(x, spoken_ref)
    y = resample_poly(x, 16000, g.SR).astype(np.float32)
    heard = " ".join(s.text for s in ge._whisper[0].transcribe(y, language="ru", beam_size=5)[0]).lower().replace("ё", "е")
    ref = spoken_ref.lower().replace("ё", "е")
    leaked = [w for w in set(words) | {"пауза", "озвуч", "начинаю", "готов передавать"}
              if w[:5].replace("ё", "е") in heard and w[:5].replace("ё", "е") not in ref]
    if leaked:
        return False, r, f"вслух: {leaked}"
    return r >= 0.8, r, "" if r >= 0.8 else f"не совпадает ({r:.2f}): {heard[:80]}"


def listen(wav_path, question, model="google/gemini-3.5-flash"):
    """'Ears': send an audio file to an audio-input model and get its text answer."""
    x, sr = sf.read(wav_path, dtype="float32")
    buf = io.BytesIO()
    sf.write(buf, resample_poly(x, 16000, sr).astype(np.float32), 16000, format="WAV", subtype="PCM_16")
    b64 = base64.b64encode(buf.getvalue()).decode()
    r = _post({"model": model, "usage": {"include": True}, "messages": [{"role": "user", "content": [
        {"type": "text", "text": question},
        {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}}]}]})
    d = json.loads(r.read())
    return d["choices"][0]["message"]["content"].strip(), d.get("usage", {}).get("cost", 0.0)


TESTS = [
    ("mihalych", "ash", "пожилой дальнобойщик за шестьдесят, хрипловатый, неторопливый, добродушный, с усмешкой",
     "Анекдот слышали? Дальнобойщик спрашивает навигатор: куда едем? А тот ему: я думал, ты знаешь. (смеётся)"),
    ("boroda", "onyx", "громкий напористый мужик под сорок, лихач и хвастун, говорит с азартом",
     "Бродяги, двадцать третий штраф в коллекцию! Юбилейный почти! (смеётся) Обмыть надо!"),
    ("stas", "verse", "молодой парень двадцати четырёх лет, балагур, тараторит, восторженный",
     "Короче, пацаны, мой ролик сорок просмотров набрал! Сорок! (смеётся) Я почти блогер, реально."),
]
QUESTION = ("Это реплика дальнобойщика по рации. Ответь коротко по-русски: 1) Есть ли в записи НАСТОЯЩИЙ смех "
            "(смеётся голосом), или человек произносит слова «ха-ха»/«смеётся»? 2) Говорит ли он по-русски без "
            "иностранного акцента? 3) Насколько живо звучит, по шкале 1-10?")


def test():
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    out = ROOT / "samples" / "openrouter_full"
    out.mkdir(parents=True, exist_ok=True)
    total = 0.0
    for key, voice, style, text in TESTS:
        x, cost = tts(text, voice, style)
        total += cost
        dry = out / f"{key}_{voice}_dry.wav"
        sf.write(dry, x, g.SR)
        sf.write(out / f"{key}_{voice}_radio.wav", remix.render(x, data["actors"][key], False, remix.seed(key, voice)), g.SR)
        verdict, c2 = listen(dry, QUESTION)
        total += c2
        print(f"{key} ({voice}) {len(x) / g.SR:.1f}s ${cost:.4f}\n   уши: {verdict}")
    print(f"всего: ${total:.4f}")


if __name__ == "__main__":
    test()
