# -*- coding: utf-8 -*-
"""Стенд пилота GigaAM (24.11): гоняет A/B-клипы через ИНТЕГРИРОВАННЫЙ путь cb_radio.Ears._recognize
(не через ab_run.py) с флагом gigaam_pilot=True и проверяет: движок, время, фолбэки, интенты, имена.

Проверяемые ожидания (основание — build/gigaam_ab/report.md):
- русские клипы — движок «гигаам», фолбэка нет;
- 2 английских (c01, c02) — фолбэк в whisper (причина «латиница»/«пусто»);
- c00 «Стас, как твои дела?» — интент how_are_you, адресат stas;
- c908L «Янок как семья…» — адресат yanek (маппинг артефакта GigaAM в intents.NAMES);
- режим флага ВЫКЛ — движок «whisper» (старое поведение).

Запуск из корня воркспейса:
  build\\venv\\Scripts\\python.exe -X utf8 cb-radio/tools/gigaam_pilot_stand.py [--off]
  --off — прогон с gigaam_pilot=False (контроль старого поведения)
Вердикт: «СТЕНД ЗЕЛЁНЫЙ» / «СТЕНД КРАСНЫЙ» + таблица.
"""
import argparse
import collections
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]          # cb-radio/
WS = ROOT.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import cb_radio as cb  # noqa: E402  env OpenBLAS/OMP=1 — как в живом процессе

CLIPS = WS / "build" / "gigaam_ab" / "clips"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--off", action="store_true", help="контроль: флаг выключен, старый путь whisper")
    a = ap.parse_args()

    import asr_gigaam
    from faster_whisper import WhisperModel

    ears = cb.Ears.__new__(cb.Ears)
    ears.ok, ears.recording = True, False
    ears.buf, ears.pre = [], collections.deque(maxlen=8)
    ears.jobs, ears.results = __import__("queue").Queue(), {}
    ears.dev_name, ears.sr = "стенд", 16000
    ears.last_info, ears.on_silent = "", None
    ears.gigaam_pilot = not a.off
    ears.gigaam_dir = ""
    ears.model = None
    ears._whisper_name = "small"
    ears.langs = {}

    # бенч как в живом старте (под пилотом): гигаам + whisper-эталон
    if ears.gigaam_pilot:
        wm_probe = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=4)
        ears._bench(wm_probe)
        assert ears.gigaam_pilot, "бенч выключил пилот — модель не найдена?"

    fails = []
    print(f"{'клип':22} {'движок':16} {'время':>7}  интент/адресат   текст")
    for c in sorted(CLIPS.glob("*.wav")):
        y, sr = sf.read(c, dtype="float32")
        if y.ndim > 1:
            y = y[:, 0]
        if sr != 16000:
            from scipy.signal import resample_poly
            y = resample_poly(y, 16000, sr).astype(np.float32)
        peak = float(np.max(np.abs(y))) if len(y) else 0.0
        if peak > 0.002:
            y = (y / peak * 0.9).astype(np.float32)
        t0 = time.monotonic()
        text, lang, meta = ears._recognize(y)
        dt = time.monotonic() - t0
        import intents
        intent, who = intents.understand(text)
        engine = meta["engine"] if ears.gigaam_pilot else "whisper"
        why = meta.get("why")
        print(f"{c.name:22} {engine:16} {dt:6.2f}с  {str(intent) + '/' + str(who):16} «{text[:52]}»"
              + (f"  (фолбэк: {why})" if why else ""))
        # --- ожидания ---
        if ears.gigaam_pilot:
            # фолбэк разрешён: 2 английских (латиница/пусто) + c9560 (2 слова без интента — обрывок по спеке)
            if c.name.startswith(("c01", "c02", "c9560")) and engine == "gigaam":
                fails.append(f"{c.name}: ожидался фолбэк, а сработал gigaam")
            if not c.name.startswith(("c01", "c02", "c9560")) and engine != "gigaam":
                fails.append(f"{c.name}: русский ушёл в фолбэк зря")
            want_why = {"c01_en_thankyou1.wav": "латиница", "c02_en_thankyou2.wav": "пусто",
                        "c9560.wav": "обрывок без интента"}.get(c.name)
            if want_why and why != want_why:
                fails.append(f"{c.name}: причина фолбэка {why!r}, ожидалось {want_why!r}")
            if c.name == "c00_last_ptt.wav" and (intent != "how_are_you" or who != "stas"):
                fails.append(f"c00: ожидали how_are_you/stas, получили {intent}/{who}")
            if c.name == "c908L.wav" and who != "yanek":
                fails.append(f"c908L: «Янок» не смаппился в yanek (who={who})")
        else:
            if "стас" not in text.lower() and c.name == "c00_last_ptt.wav":
                fails.append("c00 (флаг выкл): whisper не распознал как прежде")

    # порог латиницы (задача Испытателя): вкрапления по-русски НЕ фолбэк, чистая латиница — фолбэк
    for s, want in (("про DLC в ETS2 расскажи что там", False),
                    ("Thank you stranger", True),
                    ("Sankie Stranger", True)):
        got = cb.Ears._latin_dominant(s)
        if got != want:
            fails.append(f"порог латиницы: {s!r} -> {got}, ожидалось {want}")
    print(f"порог латиницы: «про DLC в ETS2…» -> {cb.Ears._latin_dominant('про DLC в ETS2 расскажи')} "
          f"(ложно нет), «Thank you stranger» -> {cb.Ears._latin_dominant('Thank you stranger')} (да)")

    print("СТЕНД КРАСНЫЙ:" if fails else "СТЕНД ЗЕЛЁНЫЙ")
    for f in fails:
        print("  -", f)
    asr_gigaam.unload()
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
