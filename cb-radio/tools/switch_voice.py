"""Put an alternative voice set (audio/alt_<name>/...) on air, or take it back off.

  switch_voice.py tatiana on    copy alt files over the live ones (live originals saved to audio/_live_saved_<name>/)
  switch_voice.py tatiana off   restore the saved originals
Only *.wav files that exist in the alt set are touched (never the *_dry.wav helpers).
"""
import shutil
import sys
from pathlib import Path

A = Path(__file__).resolve().parents[1] / "audio"


def main(name, mode):
    alt, saved = A / f"alt_{name}", A / f"_live_saved_{name}"
    files = [f for f in alt.rglob("*.wav") if not f.stem.endswith("_dry")]
    n = 0
    for f in files:
        rel = f.relative_to(alt)
        live = A / rel
        if mode == "on":
            if live.exists() and not (saved / rel).exists():
                (saved / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(live, saved / rel)
            live.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, live)
            n += 1
        elif (saved / rel).exists():
            shutil.copy2(saved / rel, live)
            n += 1
    print(f"{'в эфире' if mode == 'on' else 'возвращено как было'}: {n} файлов")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
