"""Load local Silero models, list speakers, synth one test line per male voice."""
import sys
from pathlib import Path

import soundfile as sf
import torch

ROOT = Path(__file__).resolve().parents[1]
TEXT = "Всем привет на канале! Кто там едет в сторону Берлина? Тут дождь такой, что дворники не справляются."


def load(name):
    imp = torch.package.PackageImporter(str(ROOT / "models" / f"{name}.pt"))
    model = imp.load_pickle("tts_models", "model")
    model.to(torch.device("cpu"))
    return model


def main():
    out = ROOT / "samples" / "probe"
    out.mkdir(parents=True, exist_ok=True)
    for name in sys.argv[1:] or ["v5_1_ru", "v4_ru"]:
        m = load(name)
        speakers = list(getattr(m, "speakers", []))
        print(name, "speakers:", speakers)
        for sp in speakers:
            if sp == "random":
                continue
            try:
                audio = m.apply_tts(text=TEXT, speaker=sp, sample_rate=48000,
                                    put_accent=True, put_yo=True)
            except TypeError:
                audio = m.apply_tts(text=TEXT, speaker=sp, sample_rate=48000)
            f = out / f"{name}_{sp}.wav"
            sf.write(f, audio.numpy(), 48000)
            print("  wrote", f.name, f"{len(audio) / 48000:.1f}s")


if __name__ == "__main__":
    main()
