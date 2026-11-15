"""Проба голосов для Совы (15.11, пользователь: «более женственный и молодой», Бахтияр в неё влюблён)
на ElevenLabs v3, через звук рации, -> samples/sova_<голос>.ogg и голосовыми в личку пользователю.
    python tools/audition_sova.py
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402
import gen_level3 as g  # noqa: E402

TITLE = "Сова (новый голос)"
LINE = ("[warmly] [sultry] Ковбой ваш — мальчик-то какой добрый. Плова банку, и чая, мне привез. "
        "[pause] [playful] [cheerful] А чего вы так замолчали, а? [giggles]")
CANDS = {
    # раунд 4 (15.11): Marishnou + радость (была «слишком уставшая»)
    "Marishnou": "3EkZsEff6fKDaatADyt6",
}
SUFFIX = "r4"                                # раунд 4 — не затирать файлы прошлых раундов
RADIO = {"noise_db": -30, "drive": 1.6}      # как у Совы в level3_eleven.json
DM = 1910976011
OUT = g.ROOT / "samples"
TG = g.ROOT.parent / "promo" / "telegram"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(TG))
    import autopost as ap
    ap.api("sendMessage", {"chat_id": DM, "text": f"🎙 {TITLE}, раунд 4 — Marishnou с радостью (была «слишком уставшая»)"})
    spent = 0
    for name, vid in CANDS.items():
        mp3, x = ge.tts(vid, LINE, "eleven_v3", 0.5)
        spent += len(LINE)
        (OUT / f"sova_{SUFFIX}_{name}.mp3").write_bytes(mp3)
        y = g.radio(x, dict(RADIO, far=False), np.random.default_rng(7))
        wav = OUT / f"sova_{SUFFIX}_{name}.wav"
        sf.write(wav, y, g.SR)
        ogg = OUT / f"sova_{SUFFIX}_{name}.ogg"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", wav, "-c:a", "libopus", "-b:a", "48k", ogg], check=True)
        ap.api("sendVoice", {"chat_id": DM, "caption": f"Сова r2 — голос {name}"}, {"voice": ogg})
        print(f"sova {name}: {len(y) / g.SR:.1f} с")
    print(f"потрачено символов ElevenLabs: {spent}")


if __name__ == "__main__":
    main()
