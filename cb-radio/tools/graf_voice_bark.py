"""graf/voice (игрок сказал «Граф, голос!»): СНАЧАЛА лай Графа, потом Вера. Без трат: берёт озвученные NN.mp3.
Запускать после voice_group.py graf, если реплики graf/voice переозвучивались."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402
import remix  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SR = ge.g.SR


def mono48(path):
    x, sr = sf.read(path, dtype="float32")
    x = x.mean(axis=1) if x.ndim > 1 else x
    return resample_poly(x, SR, sr).astype(np.float32) if sr != SR else x


a = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))["actors"]["vera"]
bark = mono48(ROOT / "audio" / "fx" / "graf_bark_2.wav")
d = ROOT / "audio" / "reactions" / "graf" / "voice"
for f in sorted(d.glob("[0-9][0-9].mp3")):
    voice = mono48(f)
    y = np.concatenate([bark / (np.abs(bark).max() + 1e-9) * 0.55, np.zeros(int(0.25 * SR), np.float32),
                        voice / (np.abs(voice).max() + 1e-9) * 0.9]).astype(np.float32)
    sf.write(f.with_suffix(".wav"), remix.render(y, a, False, np.random.default_rng(100 + int(f.stem))), SR)
    print(f.stem, "лай + Вера")
