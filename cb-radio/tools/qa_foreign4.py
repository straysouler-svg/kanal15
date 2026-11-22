# -*- coding: utf-8 -*-
"""22.11 QA: обратный перевод строк no/sv/pl/tr через MyMemory (как для финна 20.11).
Сравниваем машинный перевод с нашим ru-субтитром глазами — ищем смысловые лажи.
  G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/qa_foreign4.py
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
d = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))

LINES = []
for group in ("foreign", "foreign_reply", "foreign_warm"):
    for lang in ("no", "sv", "pl", "tr"):
        for ln in d["reactions"][group].get(lang, []):
            LINES.append((group, lang, ln["text"], ln.get("ru", "")))

# pl: старые 3+3 уже были, новые — с 4-й позиции в foreign и warm целиком
SKIP_OK = {("foreign", "pl", i) for i in (1, 2, 3)} | {("foreign_reply", "pl", i) for i in (1, 2, 3)}

def mymemory(text, lang, to="ru"):
    q = urllib.parse.quote(text[:480])
    url = f"https://api.mymemory.translated.net/get?q={q}&langpair={lang}|{to}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return json.loads(r.read())["responseData"]["translatedText"]
        except Exception as e:
            if attempt == 2:
                return f"<ошибка: {e!r}>"
            time.sleep(3)

print(f"{'пул':<16}{'№':<3}{'lang'}  текст -> обратный перевод | наш ru")
bad = 0
for group, lang, text, ru in LINES:
    idx = [x for g, l, x, _ in LINES if g == group and l == lang].index(text) + 1
    if (group, lang, idx) in SKIP_OK:
        continue
    back = mymemory(text, lang)
    print(f"{group:<16}{idx:<3}{lang}  {text}\n{'':22}-> {back}\n{'':22}| ru: {ru}\n")
    time.sleep(1.2)
print(f"всего строк: {len(LINES)}")
