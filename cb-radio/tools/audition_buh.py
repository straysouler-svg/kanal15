"""Проба голосов бухгалтерии на ElevenLabs: одна реплика несколькими голосами, с телефонным звуком,
-> samples/buh/<имя>.ogg и голосовыми в личку пользователю от бота канала.
    python tools/audition_buh.py            # все кандидаты (тратит ~150 символов на голос)
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402
import gen_level3 as g  # noqa: E402
import remix  # noqa: E402

CANDIDATES = {
    "Волошина": "nkvv6waLzFah2jTNUZGT",   # Tatyana Voloshina - Dramatic, Rich (библиотека)
    "Марина": "CsT9glYAgw8L02hu9od2",     # Marina - Warm Expressive
    "Мария": "EluqMkib8uTv2OpkCbcD",      # Maria - confidence and charisma (ru-moscow)
}
LINE = ("[exasperated] Товарищ начальник! Это уже третий штраф за день! [frustrated] Я вам отчёт на стол положу. "
        "И заявление. [sighs] [pause] Шучу. [quietly] Пока шучу.")
DM = 1910976011
OUT = g.ROOT / "samples" / "buh"
TG = g.ROOT.parent / "promo" / "telegram"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    ping, sr = sf.read(g.ROOT / "audio" / "fx" / "phone_ping.wav", dtype="float32")
    sys.path.insert(0, str(TG))
    import autopost as ap
    spent = 0
    for name, vid in CANDIDATES.items():
        mp3, x = ge.tts(vid, LINE, "eleven_v3", 0.5)
        spent += len(LINE)
        (OUT / f"{name}.mp3").write_bytes(mp3)
        y = np.concatenate([ping if ping.ndim == 1 else ping.mean(axis=1), np.zeros(int(0.3 * g.SR), np.float32),
                            remix.phone(x)])
        wav = OUT / f"{name}.wav"
        sf.write(wav, y, g.SR)
        ogg = OUT / f"{name}.ogg"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "libopus", "-b:a", "48k", ogg], check=True)
        ap.api("sendVoice", {"chat_id": DM, "caption": f"Бухгалтерия, голос: {name}"}, {"voice": ogg})
        print(f"{name}: {len(y) / g.SR:.1f} с, отправлено")
    print(f"потрачено символов ElevenLabs: {spent}")


if __name__ == "__main__":
    main()
