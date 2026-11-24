# -*- coding: utf-8 -*-
"""Нагрузочный стенд распознавания (24.11, стрим #15: whisper не укладывался в STT_WAIT_S=9 с на ходу).

Гоняет записанный клип через ШТАТНЫЙ код пути распознавания — воркер потока Ears из cb_radio.py
(модель, resample_poly, transcribe с теми же параметрами) — при искусственной нагрузке на процесс,
имитирующей главный цикл рации. Замеряет: время от постановки job до результата, фазы воркера
(пишутся его же log()-строками «стт: ...» в cb_radio.log).

Без микрофона и без игры — только CPU-нагрузка. Платных API нет.

Запуск из корня воркспейса:
  build\\venv\\Scripts\\python.exe -X utf8 cb-radio/tools/whisper_load_stand.py [--rounds 6]
      [--burn 2] [--duty 0.9] [--unload] [--clip cb-radio/last_ptt.wav]

  --burn N    N дополнительных потоков с чисто-питоновской горячей петлёй (GIL-конкуренция,
              как у занятого главного цикла рации). По умолчанию 2.
  --duty D    доля времени потока в горячей петле (остальное — sleep 5 мс), по умолчанию 0.9
  --unload    выгружать модель между раундами (имитация холодного пути нажатия)
  --clip      файл для распознавания (по умолчанию cb-radio/last_ptt.wav)

Вердикт: «СТЕНД ЗЕЛЁНЫЙ» — все раунды уложились в STT_WAIT_S; «СТЕНД КРАСНЫЙ» — воспроизвёлся
таймаут, смотри фазы в cb-radio.log.
"""
import argparse
import collections
import queue
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # cb-radio/
sys.path.insert(0, str(ROOT))

import soundfile as sf  # noqa: E402

import cb_radio as cb  # noqa: E402  env-переменные OpenBLAS/OMP=1 — как в живом процессе

STOP = False


def burn(duty):
    """Горячая петля: душит GIL, как занятый главный цикл рации на ходу."""
    x = 0
    while not STOP:
        t0 = time.monotonic()
        while time.monotonic() - t0 < duty * 0.05:
            x += 1
        time.sleep(0.05 * (1 - duty) + 0.001)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=6)
    ap.add_argument("--burn", type=int, default=2)
    ap.add_argument("--duty", type=float, default=0.9)
    ap.add_argument("--unload", action="store_true")
    ap.add_argument("--clip", default=str(ROOT / "last_ptt.wav"))
    a = ap.parse_args()

    global STOP
    clip = Path(a.clip)
    if not clip.exists():
        print(f"НЕТ КЛИПА: {clip}")
        return 2
    audio, sr = sf.read(clip, dtype="float32")
    if audio.ndim > 1:
        audio = audio[:, 0]

    # Ears без микрофона: тот же воркер, та же очередь jobs/results — штатный путь распознавания
    ears = cb.Ears.__new__(cb.Ears)
    ears.ok, ears.model, ears.recording = True, None, False
    ears.buf, ears.pre = [], collections.deque(maxlen=8)
    ears.jobs, ears.results = queue.Queue(), {}
    ears.stream, ears.dev_name = None, "стенд (без микрофона)"
    ears.sr, ears.last_info, ears.on_silent = int(sr), "", None
    ears.want_model = threading.Event()
    ears.langs = {}
    ears.ready = False

    threading.Thread(target=ears._worker, args=("small",), daemon=True).start()
    t_rdy = time.monotonic()
    while not ears.ready and time.monotonic() - t_rdy < 120:
        time.sleep(0.2)
    if not ears.ready:
        print("воркер не поднялся за 120 с — стенд бессмысленен")
        return 2
    print(f"воркер готов за {time.monotonic() - t_rdy:.1f} с")

    burns = [threading.Thread(target=burn, args=(a.duty,), daemon=True) for _ in range(a.burn)]
    for b in burns:
        b.start()
    time.sleep(0.3)                                   # даём горелкам разогреться

    print(f"клип: {clip.name} ({len(audio) / sr:.1f} с, {sr} Гц), нагрев: {a.burn} потоков, duty {a.duty}")
    wait_s = cb.Operator.STT_WAIT_S
    worst, fails = 0.0, 0
    for i in range(1, a.rounds + 1):
        if a.unload:
            ears.model = None                         # холодный путь: загрузка модели внутри job
        job = time.monotonic()
        ears.jobs.put((job, audio.copy()))
        t0 = time.monotonic()
        while job not in ears.results and time.monotonic() - t0 < wait_s + 20:
            time.sleep(0.05)
        dt = time.monotonic() - t0
        text = ears.results.pop(job, None)
        if text is None:
            print(f"раунд {i}: НЕТ РЕЗУЛЬТАТА за {dt:.1f} с")
            fails += 1
            continue
        worst = max(worst, dt)
        mark = "ТАЙМАУТ" if dt > wait_s else "ок"
        if dt > wait_s:
            fails += 1
        print(f"раунд {i}: {dt:.1f} с [{mark}] -> «{text[:60]}»")
    STOP = True
    print(f"худшее: {worst:.1f} с, таймаутов: {fails}/{a.rounds} (лимит STT_WAIT_S={wait_s} с)")
    print("СТЕНД КРАСНЫЙ — таймаут воспроизвёлся" if fails else "СТЕНД ЗЕЛЁНЫЙ — укладываемся с запасом")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
