"""Listening test of the cab sounds: per driver one of his lines with every extra forced on
-> samples/cabs/NN_<actor>.wav (and NN_<actor>_bed.wav = only the cab, no voice, to hear what's in it)."""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cab  # noqa: E402
import gen_level3 as g  # noqa: E402
import remix  # noqa: E402

ROOT = g.ROOT
out = ROOT / "samples" / "cabs"
out.mkdir(parents=True, exist_ok=True)
for f in out.glob("*.wav"):
    f.unlink()
data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
only = sys.argv[1:]
i = 0
for key, a in data["actors"].items():
    ex = a.get("cab", {}).get("extras")
    if not ex or (only and key not in only):
        continue
    i += 1
    a = json.loads(json.dumps(a))
    for e in a["cab"]["extras"]:
        e["chance"] = 1.0                      # all on for the test
    base = ROOT / "audio" / "level3_clean" / key
    src = None
    for n in range(2, 13):
        src = remix.src(base / f"{n:02d}", a)
        if src:
            break
    if not src:
        print("нет сухой записи:", key)
        continue
    rng = np.random.default_rng(i)
    x = remix.dry(src)
    sf.write(out / f"{i:02d}_{key}.wav", remix.render(x, a, False, rng), g.SR)
    bed = cab.kerchunk_bed(6.0, a["cab"], np.random.default_rng(i + 100))
    sf.write(out / f"{i:02d}_{key}_bed.wav", g.radio(bed, a.get("radio", {}), rng), g.SR)
    print(f"{i:02d} {a['name']}: {', '.join(e.get('style', e['kind']) for e in a['cab']['extras'])}")
