# -*- coding: utf-8 -*-
"""Ступень 0: демо гудков «с дороги». Без рации, игры и сети.

Собирает build/horn_demo.wav: 3 тембра x 3 расстояния (200/600/1500 м)
+ проезд встречного с Доплером. Между фрагментами 1 с тишины.
Печатает таблицу замеров: длительность, пик (дБ), спектральный центроид.
"""

import os
import sys

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import soundfile as sf

from horn import horn_buffer, TIMBRES

SR = 48000
GAP = 1.0
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "..", "build", "horn_demo.wav")

FRAGMENTS = []
for timbre in ("old_low", "bass", "high"):
    for dist in (200, 600, 1500):
        FRAGMENTS.append(dict(timbre=timbre, distance_m=dist, rel_speed_ms=0.0,
                              side="center", tag=f"{timbre} {dist}м центр"))
# проезд встречного: 80+80 км/ч, гудок 2.5 с, максимальное сближение посередине
FRAGMENTS.append(dict(timbre="bass", distance_m=56.0, rel_speed_ms=160 / 3.6,
                      side="left", tag="bass встречный 160км/ч Доплер (слева)"))


def peak_db(buf):
    p = np.abs(buf).max()
    return -120.0 if p <= 0 else 20 * np.log10(p)


def centroid(buf, sr=SR):
    mono = buf.mean(axis=1)
    if np.abs(mono).max() < 1e-6:
        return 0.0
    sp = np.abs(np.fft.rfft(mono * np.hanning(len(mono))))
    fr = np.fft.rfftfreq(len(mono), 1 / sr)
    return float((sp * fr).sum() / sp.sum())


def main():
    gap = np.zeros((int(GAP * SR), 2), dtype=np.float32)
    parts, rows = [], []
    for i, f in enumerate(FRAGMENTS):
        buf = horn_buffer(f["timbre"], f["distance_m"], f["rel_speed_ms"],
                          side=f["side"], sr=SR, duration=2.5)
        if i:
            parts.append(gap)
        parts.append(buf)
        row = dict(tag=f["tag"], dur=len(buf) / SR, db=peak_db(buf),
                   cen=centroid(buf))
        if f["rel_speed_ms"] > 0:  # доплер: центроид первой и последней трети
            k = len(buf) // 3
            row["cen"] = centroid(buf[:k])
            row["cen_end"] = centroid(buf[-k:])
        rows.append(row)

    wav = np.vstack(parts)
    sf.write(OUT, wav, SR, subtype="FLOAT")
    size_mb = os.path.getsize(OUT) / 1e6

    print(f"wav: {os.path.abspath(OUT)}  ({size_mb:.1f} МБ, {len(wav)/SR:.1f} с)\n")
    print(f"{'фрагмент':<38}{'длит,с':>7}{'пик,дБ':>9}{'центроид,Гц':>14}"
          + (f"{'центр.конец,Гц':>16}" if any('cen_end' in r for r in rows) else ""))
    for r in rows:
        line = f"{r['tag']:<38}{r['dur']:>7.2f}{r['db']:>9.1f}{r['cen']:>14.0f}"
        if "cen_end" in r:
            line += f"{r['cen_end']:>16.0f}"
        print(line)


if __name__ == "__main__":
    main()
