"""Точная разметка куска записи по словам (для субтитров шортса).
  python words.py <video> <start_s> <end_s> <out.txt>
Строки: «время_в_записи  текст» — фраза рвётся на паузе > 0.6 с. faster-whisper small, CPU."""
import subprocess
import sys

import numpy as np
from faster_whisper import WhisperModel

src, a, b, out = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-t", str(b - a), "-i", src, "-vn", "-ac", "1",
                      "-ar", "16000", "-f", "f32le", "-"], capture_output=True, check=True).stdout
audio = np.frombuffer(raw, np.float32)
m = WhisperModel("small", device="cpu", compute_type="int8")
segs, _ = m.transcribe(audio, language="ru", word_timestamps=True, vad_filter=True)
lines, cur, last = [], [], None
for s in segs:
    for w in s.words:
        if cur and w.start - last > 0.6:
            lines.append(cur)
            cur = []
        cur.append(w)
        last = w.end
if cur:
    lines.append(cur)
with open(out, "w", encoding="utf-8") as f:
    for ws in lines:
        f.write(f"{a + ws[0].start:8.1f} {a + ws[-1].end:8.1f}  {''.join(w.word for w in ws).strip()}\n")
