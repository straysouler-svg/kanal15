"""Озвучка пилота «мигни — бибикну» (11.11): 24 реплики reactions.horn.*.

Сорока — XTTS «Татьяна» (clone_xtts, локально, бесплатно).
Витёк — gpt-audio/verse, Тень — gpt-audio/onyx (gen_openrouter, OpenRouter).

Пишет audio/reactions/horn/<kind>/NN.wav (радио-версия через remix.render) + index.json,
сухие дубли — в samples/horn_pilot_dry/<actor>/, прослушка-склейка — samples/horn_pilot_<actor>.wav.
Перегенерирует только недостающие файлы (удалить файл — перегенерировать строку).

Запуск: venv-python tools/voice_horn_pilot.py            # все
         venv-python tools/voice_horn_pilot.py ten        # один актёр
"""
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_level3 as g  # noqa: E402
import remix  # noqa: E402

ROOT = g.ROOT
PHRASES = ROOT / "phrases" / "level3_eleven.json"

# голоса пилота: XTTS-клон или (gpt-audio voice, характер для system-промпта)
CAST = {
    "soroka": {"engine": "xtts", "voice": "tatiana"},
    "vitek": {"engine": "openrouter", "voice": "verse",
              "style": ("молодой парень лет двадцати, тараторит, восторженный, слегка паникует, "
                        "не в меру эмоциональный, балагур")},
    "ten": {"engine": "openrouter", "voice": "onyx",
            "style": ("тихий низкий мужской голос, говорит медленно, скупо и невозмутимо, "
                      "с мрачноватым юмором, ночной одиночка")},
}


def jobs_for(actor):
    """[(kind, n, text)] из reactions.horn в порядке файлов."""
    data = json.loads(PHRASES.read_text(encoding="utf-8"))
    out = []
    for kind, lines in data["reactions"]["horn"].items():
        if kind.startswith("_"):
            continue
        for i, ln in enumerate(lines, 1):
            if ln["actor"] == actor:
                out.append((kind, i, ln["text"]))
    return out


def main():
    actors = sys.argv[1:] or list(CAST)
    data = json.loads(PHRASES.read_text(encoding="utf-8"))
    dry_root = ROOT / "samples" / "horn_pilot_dry"
    total_chars = 0
    for actor in actors:
        cast = CAST[actor]
        jobs = jobs_for(actor)
        if not jobs:
            print(f"{actor}: нет строк — пропуск")
            continue
        if cast["engine"] == "xtts":
            import clone_xtts
            model = clone_xtts.load_model(ROOT / "voices" / cast["voice"])
            def synth(text):
                x, _clean = clone_xtts.say(model, text)
                return x
        else:
            import gen_openrouter
            def synth(text):
                x, _cost = gen_openrouter.tts(text, cast["voice"], cast["style"])
                return x
        adata = data["actors"][actor]
        dry_parts, spent = [], 0
        for kind, n, text in jobs:
            d = ROOT / "audio" / "reactions" / "horn" / kind
            d.mkdir(parents=True, exist_ok=True)
            out = d / f"{n:02d}.wav"
            dry = dry_root / actor / f"{kind}_{n:02d}.wav"
            if not out.exists():
                x = synth(text)
                spent += len(text)
                rng = remix.seed("horn", kind, n, actor)
                sf.write(out, remix.render(x, adata, False, rng), g.SR)
                dry.parent.mkdir(parents=True, exist_ok=True)
                sf.write(dry, x, g.SR)
                print(f"  {out.relative_to(ROOT)}  {len(x) / g.SR:4.1f}s  {text[:48]}")
            if dry.exists():
                dry_parts.append(sf.read(dry, dtype="float32")[0])
        # index.json — все актёры пилота в порядке строк json
        for kind in ("ask_day", "ask_night", "seen", "missed", "far"):
            lines = [ln for ln in data["reactions"]["horn"][kind]]
            d = ROOT / "audio" / "reactions" / "horn" / kind
            if all((d / f"{i:02d}.wav").exists() for i in range(1, len(lines) + 1)):
                (d / "index.json").write_text(
                    json.dumps({"actors": [ln["actor"] for ln in lines]}), encoding="utf-8")
        # прослушка-склейка сухих дублей
        if dry_parts:
            gap = np.zeros(int(0.6 * g.SR), dtype=np.float32)
            parts = []
            for i, x in enumerate(dry_parts):
                if i:
                    parts.append(gap)
                parts.append(x)
            sf.write(ROOT / "samples" / f"horn_pilot_{actor}.wav", np.concatenate(parts), g.SR)
        total_chars += spent
        print(f"{actor}: строк {len(jobs)}, символов {spent}")
    print(f"итого символов (OpenRouter, платно): "
          f"{sum(len(t) for a in actors if CAST[a]['engine'] == 'openrouter' for _k, _n, t in jobs_for(a))}")


if __name__ == "__main__":
    main()
