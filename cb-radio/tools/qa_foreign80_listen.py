# -*- coding: utf-8 -*-
"""22.11: дожим QA foreign80 — whisper по двум перегенерированным EL-строкам
и Gemini-уши по турецким ответам (whisper small на tr ненадёжен — каша).
  G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/qa_foreign80_listen.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402
import gen_openrouter as gor  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REACT = ROOT / "audio" / "reactions"

if not ge._whisper:
    from faster_whisper import WhisperModel
    import os
    ge._whisper.append(WhisperModel(os.environ.get("QA_MODEL", "small"), device="cpu", compute_type="int8"))

for label, i, text, lang in [("foreign_ans/pl__warn", 1, "Dzięki za info, kurna, zwalniam i się rozglądam!", "pl"),
                             ("foreign_ans/fr__steam", 1, "C'est partout pareil, hélas... Courage, collègue.", "fr")]:
    x, sr = ge.sf.read(REACT / label / f"{i:02d}.wav", dtype="float32")
    y = ge.resample_poly(x, 16000, sr).astype("float32")
    heard = " ".join(s.text for s in ge._whisper[0].transcribe(y, language=lang, beam_size=5)[0])
    print(f"[whisper {lang}] {label}\n   было: {text}\n   слыш: {heard}\n")

Q = ("Это короткая реплика дальнобойщика по рации на турецком. Переведи её ДОСЛОВНО на русский "
     "одной строкой, без комментариев.")
for label, i, text in [("foreign_ans/tr__warn", 1, "Sağ ol kardeşim, dikkat ediyorum!"),
                       ("foreign_ans/tr__warn", 2, "Tamam abi, yavaşlıyorum!"),
                       ("foreign_ans/tr__radio", 1, "Net geliyorsun, beş üstüne beş!"),
                       ("foreign_ans/tr__radio", 2, "Seni duyuyorum abi, temiz geliyor!"),
                       ("foreign_ans/tr__thanks", 1, "Rica ederim kardeşim, yolun açık olsun!"),
                       ("foreign_ans/tr__rant", 1, "Bizde de aynı hikaye, vay be, bu işler hep böyle!"),
                       ("foreign_ans/tr__steam", 1, "Tam anlamadım ama... çay var, idare ederiz!")]:
    f = REACT / label / f"{i:02d}.mp3"       # сухая EL-запись
    ans, cost = gor.listen(f, Q)
    print(f"[gemini-уши ${cost:.4f}] {label}/{i:02d}\n   было: {text}\n   перевод: {ans}\n")
