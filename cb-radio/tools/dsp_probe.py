# -*- coding: utf-8 -*-
"""Песочница voicedsp: 5 архетипов x 3 файла проезжих -> build/dsp_probe/*.wav (на прослушку Дмитрию).
Офлайн, без рации: берёт wet-файлы пулов foreign/ru 05, streambot/ru 05, night_mystic/ru 13
и прогоняет каждый через КАЖДЫЙ архетип принудительно (profile=...)."""
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import voicedsp  # noqa: E402

OUT = ROOT.parent / "build" / "dsp_probe"
FILES = [("foreign", ROOT / "audio" / "reactions" / "foreign" / "ru" / "05.wav"),
         ("streambot", ROOT / "audio" / "reactions" / "streambot" / "ru" / "05.wav"),
         ("night_mystic", ROOT / "audio" / "reactions" / "night_mystic" / "ru" / "13.wav")]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    arch = voicedsp.profiles()["archetypes"]
    for pool, f in FILES:
        assert f.exists(), f"нет файла {f}"
        x, sr = sf.read(f, dtype="float32")
        for i, prof in enumerate(arch):
            p = dict(prof)
            p["_seed"] = 1000 + i                      # фиксированный сид — воспроизводимо
            y = voicedsp.process(x, sr, f"{pool}/05", profile=p)
            name = f"{prof['name']}_{pool}.wav"
            sf.write(OUT / name, y, voicedsp.SR)
            print(f"{name}: {len(y) / voicedsp.SR:.1f} с")
    print(f"готово: {len(arch) * len(FILES)} файлов в {OUT}")


if __name__ == "__main__":
    main()
