"""A/B/C test of livelier intonation on 4 phrases.

A = current (one prosody for the whole phrase)
B = SSML per sentence: own pitch/rate, pauses
C = B + pitch contour widened with the WORLD vocoder (k = PITCH_K)
Output: samples/emotion/<actor>_<NN>_<A|B|C>.wav (radio) + prints pitch spread.
"""
import sys
from pathlib import Path

import numpy as np
import pyworld as pw
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402

PITCH_K = 1.8
OUT = g.ROOT / "samples" / "emotion"

TESTS = {
    ("mihalych", 8): '<prosody pitch="low" rate="medium">Анекдот слышали?</prosody><break time="450ms"/>'
                     '<prosody pitch="x-low" rate="slow">Дальнобойщик спрашивает навигатор:</prosody><break time="150ms"/>'
                     '<prosody pitch="medium" rate="medium">куда едем?</prosody><break time="500ms"/>'
                     '<prosody pitch="x-low" rate="x-slow">А тот ему:</prosody><break time="300ms"/>'
                     '<prosody pitch="low" rate="slow">я думал, ты знаешь.</prosody>',
    ("stas", 2): '<prosody pitch="high" rate="fast">Пацаны, я сегодня на заправке хот-дог взял за шесть евро.</prosody>'
                 '<break time="300ms"/><prosody pitch="x-high" rate="medium">Шесть!</prosody><break time="250ms"/>'
                 '<prosody pitch="high" rate="x-fast">Он что, из золота?</prosody>',
    ("stas", 11): '<prosody pitch="medium" rate="fast">Дождик, дворники, музыка погромче.</prosody><break time="250ms"/>'
                  '<prosody pitch="x-high" rate="medium">Вот это жизнь!</prosody>',
    ("yanek", 9): '<prosody pitch="medium" rate="slow">Сосед мне говорит:</prosody><break time="200ms"/>'
                  '<prosody pitch="high" rate="medium">дальнобой, это как отпуск.</prosody><break time="450ms"/>'
                  '<prosody pitch="low" rate="slow">Только без моря.</prosody><break time="650ms"/>'
                  '<prosody pitch="x-low" rate="x-slow">И без отпуска.</prosody>',
}


def widen(x, k):
    x = x.astype(np.float64)
    f0, t = pw.harvest(x, g.SR, f0_floor=60, f0_ceil=400)
    sp = pw.cheaptrick(x, f0, t, g.SR)
    ap = pw.d4c(x, f0, t, g.SR)
    v = f0 > 0
    lf = np.log(f0[v])
    m = np.median(lf)
    f0b = f0.copy()
    f0b[v] = np.exp(m + (lf - m) * k)
    y = pw.synthesize(f0b, sp, ap, g.SR)
    return y.astype(np.float32)


def spread(x):
    """Pitch spread in semitones (p10..p90) - how 'lively' the melody is."""
    f0, _ = pw.harvest(x.astype(np.float64), g.SR, f0_floor=60, f0_ceil=400)
    f = f0[f0 > 0]
    lo, hi = np.percentile(f, [10, 90])
    return 12 * np.log2(hi / lo), np.median(f)


def main():
    import json
    OUT.mkdir(parents=True, exist_ok=True)
    actors = json.loads((g.ROOT / "phrases" / "level3.json").read_text(encoding="utf-8"))["actors"]
    for (key, n), ssml_body in TESTS.items():
        a = actors[key]
        rng = np.random.default_rng(n)
        flat = g.synth(a, a["phrases"][n - 1])
        m = g.model(a["model"])
        expr = m.apply_tts(ssml_text=f"<speak>{ssml_body}</speak>", speaker=a["speaker"],
                           sample_rate=g.SR).numpy().astype(np.float32)
        wide = widen(expr, PITCH_K)
        for tag, x in (("A", flat), ("B", expr), ("C", wide)):
            sf.write(OUT / f"{key}_{n:02d}_{tag}.wav", g.radio(x, a.get("radio", {}), rng), g.SR)
            st, med = spread(x)
            print(f"{a['name']:8} {n:02d} {tag}: разброс {st:4.1f} полутонов, медиана {med:4.0f} Гц, {len(x) / g.SR:4.1f} с")


if __name__ == "__main__":
    main()
