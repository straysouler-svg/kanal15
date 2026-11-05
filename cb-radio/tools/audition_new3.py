"""Проба голосов для трёх новых водителей (Рустам, Бахтияр, Вера) на ElevenLabs v3, через звук рации,
-> samples/new3/<кто>_<голос>.ogg и голосовыми в личку пользователю от бота канала.
    python tools/audition_new3.py [rustam|bahti|vera]
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402
import gen_level3 as g  # noqa: E402

WHO = {
    "rustam": ("Рустам «Самарканд»",
               "[warmly] Дорогой, ты где стоишь? [chuckles] Я на стоянке казан поставил, плов через час будет. "
               "[pause] Гость в доме — Бог в доме. Приезжай.",
               {"mirzaev": "RaNVfTYq3HYeFPLng6XN", "Abror": "nXdUXfIGcAbTyJ2kC04t", "Mirjalol": "cfWx14ZbaEUT4BjIA5tH"},
               {"noise_db": -31, "drive": 1.6}),
    "bahti": ("Бахтияр «Ковбой»",
              "[excited] Ака, слышишь? Ай эм э трак драйвер! [laughs] Вой-бо, брат не верит, а я в Америку поеду, вот увидишь!",
              {"Sherzod": "FsYDfEbTg0dtQ0Ygfcz9", "Sodiqjon": "CBeZJ4EnTnrJmhtlMCNC", "Asilbek": "fytsqG6MLzC2aCSw7MLa"},
              {"noise_db": -30, "drive": 2.0}),
    "vera": ("Вера «Кинолог»",
             "[dry] Кинолог на связи. [pause] Граф, место. [calm] Это я не вам. Встречные, впереди чисто, я только прошла.",
             {"Serafima": "Vt0E1AMTZdoht6B8DhXP", "Ksenia": "2HbD5Ppo0GFE4ojXPZjr", "Leksa": "7VsVlkgkPKhWAimu09u0"},
             {"noise_db": -31, "drive": 1.5}),
}
DM = 1910976011
OUT = g.ROOT / "samples" / "new3"
TG = g.ROOT.parent / "promo" / "telegram"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(TG))
    import autopost as ap
    only = sys.argv[1:] or list(WHO)
    spent = 0
    for key in only:
        title, line, cands, radio = WHO[key]
        ap.api("sendMessage", {"chat_id": DM, "text": f"🎙 {title}: три голоса на выбор"})
        for name, vid in cands.items():
            mp3, x = ge.tts(vid, line, "eleven_v3", 0.5)
            spent += len(line)
            (OUT / f"{key}_{name}.mp3").write_bytes(mp3)
            y = g.radio(x, dict(radio, far=False), np.random.default_rng(7))
            wav = OUT / f"{key}_{name}.wav"
            sf.write(wav, y, g.SR)
            ogg = OUT / f"{key}_{name}.ogg"
            subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "libopus", "-b:a", "48k", ogg], check=True)
            ap.api("sendVoice", {"chat_id": DM, "caption": f"{title} — голос {name}"}, {"voice": ogg})
            print(f"{key} {name}: {len(y) / g.SR:.1f} с")
    print(f"потрачено символов ElevenLabs: {spent}")


if __name__ == "__main__":
    main()
