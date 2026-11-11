"""Поджать внутренние паузы у актёра (постобработка, без API).

  tighten_pauses.py vitek [max_pause] [threshold_db]

Работает по audio/level3_clean/<actor>/NN_dry.wav: тишину длиннее max_pause
внутри фразы сжимает до max_pause, края не трогает. Затем пересобирает
wet audio/level3/<actor>/NN.wav через remix.render (тот же rng, что в gen_eleven).
Резервные копии dry — в ../build/tighten_backup/<actor>/ (один раз, не перезатирает).
Манифесты не меняются: текст тот же, сигнатуры валидны.
"""
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402
import remix  # noqa: E402

ROOT = g.ROOT
SR = g.SR


def tighten(x, max_pause=0.45, thr_db=-45, edge_keep=0.25):
    """Сжать внутренние тишины > max_pause до max_pause. Возвращает (y, stats)."""
    frame = int(0.02 * SR)
    hop = frame // 2
    n = (len(x) - frame) // hop + 1
    if n < 2:
        return x, (0, 0.0)
    rms = np.array([np.sqrt(np.mean(x[i * hop:i * hop + frame] ** 2) + 1e-12) for i in range(n)])
    voiced = rms > 10 ** (thr_db / 20)
    if not voiced.any():
        return x, (0, 0.0)
    first, last = int(np.argmax(voiced)), len(voiced) - 1 - int(np.argmax(voiced[::-1]))
    # найти непрерывные участки тишины между first..last
    out = []
    prev_end = 0
    removed = 0.0
    cuts = 0
    i = first
    segs = []
    while i <= last:
        if not voiced[i]:
            j = i
            while j <= last and not voiced[j]:
                j += 1
            segs.append((i * hop / SR, j * hop / SR))
            i = j
        else:
            i += 1
    # собрать: тишину > max_pause заменить на max_pause (с небольшим заходом в тишину с обеих сторон)
    cursor = 0
    pieces = []
    for s, e in segs:
        dur = e - s
        if dur <= max_pause:
            continue
        si, ei = int(s * SR), int(e * SR)
        keep_head = int(min(max_pause * 0.6, dur / 2) * SR)
        keep_tail = int((max_pause - keep_head / SR) * SR)
        pieces.append(x[cursor:si + keep_head])
        pieces.append(x[ei - keep_tail:ei])
        cursor = ei
        removed += dur - (keep_head + keep_tail) / SR
        cuts += 1
    if not cuts:
        return x, (0, 0.0)
    pieces.append(x[cursor:])
    # склейка с короткими кроссфейдами против щелчков
    y = pieces[0]
    f = int(0.01 * SR)
    for p in pieces[1:]:
        if len(y) > f and len(p) > f:
            y = np.concatenate([y[:-f], y[-f:] * np.linspace(1, 0, f) + p[:f] * np.linspace(0, 1, f), p[f:]])
        else:
            y = np.concatenate([y, p])
    return y.astype(np.float32), (cuts, removed)


def main():
    actor = sys.argv[1] if len(sys.argv) > 1 else "vitek"
    max_pause = float(sys.argv[2]) if len(sys.argv) > 2 else 0.45
    thr_db = float(sys.argv[3]) if len(sys.argv) > 3 else -45
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    a = data["actors"][actor]
    dry = ROOT / "audio" / "level3_clean" / actor
    wet = ROOT / "audio" / "level3" / actor
    backup = ROOT.parent / "build" / "tighten_backup" / actor
    backup.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(abs(hash(actor)) % 2**32)
    total_cuts = total_removed = 0
    for i, item in enumerate(a["phrases"], 1):
        n = f"{i:02d}"
        f = dry / f"{n}_dry.wav"
        if not f.exists():
            continue
        x, sr = sf.read(f, dtype="float32")
        y, (cuts, removed) = tighten(x, max_pause, thr_db)
        if not cuts:
            continue
        if not (backup / f.name).exists():
            shutil.copy2(f, backup / f.name)
        sf.write(f, y, SR)
        cab_force = item.get("cab") if isinstance(item, dict) else None
        sf.write(wet / f"{n}.wav", remix.render(y, a, False, rng, force=cab_force), SR)
        total_cuts += cuts
        total_removed += removed
        print(f"{n}: -{removed:.2f} c ({cuts} пауз), {len(x)/SR:.1f} -> {len(y)/SR:.1f} c")
    print(f"готово: {total_cuts} пауз, выиграно {total_removed:.1f} c")


if __name__ == "__main__":
    main()
