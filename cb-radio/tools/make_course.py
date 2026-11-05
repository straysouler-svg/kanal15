"""2026-11-04: «аудиокурс английского» в кабине Бахтияра (cab extra music style "course") -> music/course_en_*.wav.
gpt-audio через OpenRouter (центы). Диктор + пауза «повторите»."""
import sys
from math import gcd
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_openrouter as gor  # noqa: E402

M = Path(__file__).resolve().parents[1] / "music"
LESSONS = {
    "course_en_lesson7": "Lesson seven. On the road. Listen and repeat. I am a truck driver. ... I drive a big truck. ... "
                         "Where is the parking? ... How much is the diesel? ... Thank you very much. ... Have a nice day.",
    "course_en_lesson8": "Lesson eight. At the border. Listen and repeat. Here are my documents. ... I have twenty tons of "
                         "dried fruit. ... Is this the right lane? ... Excuse me, where is the toilet? ... Goodbye.",
}
STYLE = ("a calm English teacher recording a language course, clear slow pronunciation, neutral friendly tone, "
         "short pauses after each phrase so the student can repeat")
for name, text in LESSONS.items():
    if (M / f"{name}.wav").exists():
        continue
    x, cost = gor.tts(text, "fable", STYLE, "openai/gpt-audio", "en")
    g = gcd(22050, 48000)
    y = resample_poly(x, 22050 // g, 48000 // g).astype(np.float32)
    sf.write(M / f"{name}.wav", y / (np.max(np.abs(y)) + 1e-9) * 0.9, 22050, subtype="PCM_16")
    print(name, f"{len(y) / 22050:.1f} с, ${cost:.4f}")
