"""Распознать звук записи поездки (Whisper small, CPU) -> work/transcript.json: [{start, end, text}].
Звук записи: игра + рация + голос игрока в тангенту. Тексты водителей потом сверяются с базой фраз."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from faster_whisper import WhisperModel

video = Path(sys.argv[1])
work = Path(__file__).with_name("work")
wav = work / f"{video.stem}_16k.wav"
if not wav.exists():
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)], check=True)
a, sr = sf.read(wav, dtype="float32")
m = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=8)
segs, _ = m.transcribe(a, language="ru", vad_filter=True, beam_size=5, word_timestamps=False,
                       initial_prompt="Рация, канал дальнобойщиков. Кто в эфире? Петровна, Михалыч, Ласточка, Витёк, "
                                      "Тень, Стас, Янек, Борода, Кардан, Лиса, Сова, Палыч, Самарканд, Ковбой.")
out = []
for s in segs:
    out.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()})
    print(f"{s.start:7.1f} {s.text.strip()}", flush=True)
(work / f"{video.stem}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("ГОТОВО", len(out))
