"""Radio ambience without words: empty push-to-talk clicks ("kerchunks") -> audio/fx/kerchunk_NN.wav."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402

out = g.ROOT / "audio" / "fx"
out.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(2026)
for i in range(1, 9):
    silence = np.zeros(int(rng.uniform(0.05, 0.7) * g.SR), dtype=np.float32)
    cfg = {"noise_db": rng.uniform(-30, -20), "far": bool(rng.integers(0, 2)), "roger_beep": i == 8}
    x = g.radio(silence, cfg, rng) * rng.uniform(0.35, 0.7)  # quieter than speech
    sf.write(out / f"kerchunk_{i:02d}.wav", x.astype(np.float32), g.SR)
    print(f"kerchunk_{i:02d}  {len(x) / g.SR:.2f}s")
