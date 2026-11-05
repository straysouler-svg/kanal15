"""Play every WAV in a folder in name order, printing each name first."""
import sys
import time
from pathlib import Path

import sounddevice as sd
import soundfile as sf

for f in sorted(Path(sys.argv[1]).glob("*.wav")):
    print(f.stem, flush=True)
    data, sr = sf.read(f, dtype="float32")
    sd.play(data * 0.8, sr)
    sd.wait()
    time.sleep(0.8)
