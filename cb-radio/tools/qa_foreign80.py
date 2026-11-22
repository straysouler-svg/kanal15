# -*- coding: utf-8 -*-
"""22.11 QA foreign80: faster-whisper на языке каждой строки (small, CPU) по сухим дорожкам.
Сверка распознанного с исходником: ratio >= 0.75 + печать для глаз. Мат whisper цензурит —
пропуски в мат-строках не брак сами по себе, смотрим глазами.
  G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/qa_foreign80.py
"""
import difflib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REACT = ROOT / "audio" / "reactions"

data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))


def norm(s):
    return re.sub(r"[^a-zàâäçéèêëîïôöùûüœæåøæðþñěščřžýáíóúůťďľĺŕąćęłńśźżžăâîșțğışçöüâ ]", "",
                  s.lower().replace("ё", "е")).split()


def heard_ratio(x, ref, lang):
    y = ge.resample_poly(x, 16000, ge.g.SR).astype("float32")
    txt = " ".join(s.text for s in ge._whisper[0].transcribe(y, language=lang, beam_size=5)[0])
    return difflib.SequenceMatcher(None, norm(ref), norm(txt)).ratio(), txt


JOBS = []
fg = data["reactions"]["foreign"]
for lang, lines in fg.items():
    if lang.startswith("_") or not isinstance(lines, list):
        continue
    for i, e in enumerate(lines, 1):
        if isinstance(e, dict) and e.get("t"):            # только новые филлеры с типом
            JOBS.append((f"foreign/{lang}", i, e["text"], lang))
fa = data["reactions"].get("foreign_ans", {})
for lang, types in fa.items():
    if lang.startswith("_"):
        continue
    for t, lines in types.items():
        for i, e in enumerate(lines, 1):
            JOBS.append((f"foreign_ans/{lang}__{t}", i, e["text"], lang))

low = 0
if not ge._whisper:
    from faster_whisper import WhisperModel
    import os
    ge._whisper.append(WhisperModel(os.environ.get("QA_MODEL", "small"), device="cpu", compute_type="int8"))
for label, i, text, lang in JOBS:
    dry = REACT / label / f"{i:02d}_dry.wav"
    if not dry.exists():
        dry = REACT / label / f"{i:02d}.wav"      # ElevenLabs: сухая запись — NN.mp3, берём wet
    if not dry.exists():
        print(f"!! нет сухой дорожки: {label}/{i:02d}")
        low += 1
        continue
    x, sr = ge.sf.read(dry, dtype="float32")
    r, heard = heard_ratio(x, re.sub(r"\([^)]*\)", "", text), lang)
    flag = "" if r >= 0.75 else "  <<< СМОТРЕТЬ"
    if r < 0.75:
        low += 1
    print(f"[{label}] {i:02d} ({lang}) r={r:.2f}{flag}\n   было: {text}\n   слыш: {heard}")
print(f"\nвсего {len(JOBS)} строк, ниже порога: {low}")
