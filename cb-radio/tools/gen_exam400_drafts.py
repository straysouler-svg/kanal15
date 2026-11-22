# -*- coding: utf-8 -*-
"""22.11: черновики общих ответов на 400 вопросов экзамена-2 (план «75%», шаг 1 — ТОЛЬКО драфты).

Gemini через OpenRouter (google/gemini-2.5-flash), батчи по 30 вопросов. Стиль — по 25
одобренным Дмитрием образцам (drafts_exam400_answers_sample_2026-11-22.md). Строки с матом
помечаются флагом «мат» (Дмитрий фильтрует на глаз; правило «эфир чистый» формально в силе),
личные вопросы актёрам — флагом «canon?» (Летописец сверяет с каноном, без выдуманных фактов).

Пакеты: RU (drafts_exam400_*, дефолт) и EU (drafts_exam400eu_*; вопросы про Европу/Исландию/
Турцию — валюты, автобаны, каботаж, BAG/жандармы — как в самих вопросах).

Выход: phrases/drafts_exam400[_eu]_answers_gemini_2026-11-22.md (+ .json рядом).

  G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_exam400_drafts.py [ru|eu]
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PACK = "eu" if (len(sys.argv) > 1 and sys.argv[1].lower() == "eu") else "ru"
KEY = (ROOT / "openrouter_key.txt").read_text(encoding="utf-8").strip()
URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash"

SUF = "eu" if PACK == "eu" else ""
Q_FILE = ROOT / "phrases" / f"drafts_exam400{SUF}_2026-11-22.md"
SAMPLE_FILE = ROOT / "phrases" / "drafts_exam400_answers_sample_2026-11-22.md"
OUT_MD = ROOT / "phrases" / f"drafts_exam400{SUF}_answers_gemini_2026-11-22.md"
OUT_JSON = ROOT / "phrases" / f"drafts_exam400{SUF}_answers_gemini_2026-11-22.json"
BATCH = 30
MIN_LEN = 25          # минимум символов ответа — ловим обрывы
MAT_RX = re.compile(r"(пизд|хуй|хуя|хуё|хуе|бляд|блять|сука|заебал|заебись|ёбан|ебан|ебать|"
                    r"нахуй|нахер|охуел|охрен|проебал|просрал|жоп|задниц|говн|мудил|долбоящер)", re.I)
CANON_RX = re.compile(r"(жена|муж\b|сын|дочь|дети|внук|бабка|семь[ьяеи]|здоровье|боле[её]т|"
                      r"сколько лет|возраст|домой|помните меня|как там.*(жена|сын|дочь|бабка)|"
                      r"где жив[её]шь|кредит|долги|алимент)", re.I)
NAME_RX = re.compile(r"^(Михалыч|Сова|Янек|Ласточка|Тень|Студент|Стас|Петровна|Витёк|Витек|"
                     r"Самарканд|Ковбой|Профессор|Кинолог|Лиса|Борода|Кардан|Сорока)\b")

NUM_RX = re.compile(r"^(\d{1,3})[\.\)]\s+(.+)$")


def parse_questions():
    out = []
    for line in Q_FILE.read_text(encoding="utf-8").splitlines():
        m = NUM_RX.match(line.strip())
        if m and 1 <= int(m.group(1)) <= 400:
            out.append((int(m.group(1)), m.group(2).strip()))
    assert len(out) == 400 and [n for n, _ in out] == list(range(1, 401)), f"вопросов: {len(out)}"
    return out


def sample_block():
    lines = []
    for line in SAMPLE_FILE.read_text(encoding="utf-8").splitlines():
        m = NUM_RX.match(line.strip())
        if m:
            lines.append(f"{m.group(1)}. {m.group(2).strip()}")
    assert len(lines) == 25, len(lines)
    return "\n".join(lines)


SYSTEM = (
    "Ты пишешь ответы водителей в эфире рации «Канал 15» — русский CB-эфир дальнобойщиков в ETS2. "
    "По каждому вопросу игрока напиши ОДИН ответ эфира.\n"
    "Правила стиля (образцы ниже — эталон, пиши РОВНО на этом уровне):\n"
    "- 1–3 предложения, самодостаточно (читателю не нужен контекст вопроса), эфирно, живо.\n"
    "- По теме вопроса: если спросили про рамку/тянучку/душ/солярку — отвечай про это, конкретно.\n"
    "- Обращение/позывной, если вопрос адресный; общие вопросы — «мужики/братишки/парни».\n"
    "- Дальнобойный жаргон: «баранка», «крокодилы», «тангетка», «рамка», «машинка», «плечевые», «шершавенькой».\n"
    "- Персонаж отвечает от себя («Михалыч на связи», «Сова на приёме») или безымянный водитель.\n"
    "- Мат допустим, но умеренно (как в образцах).\n"
    "- НЕ выдумывай биографические факты персонажей (семья/дети/возраст): на личные вопросы отвечай "
    "нейтрально-общим эфирным юмором без конкретных фактов.\n"
    "- Никаких пояснений вне ответов, никаких кавычек вокруг ответа.\n\n"
    "Формат ответа — СТРОГИЙ JSON, один массив объектов:\n"
    '[{"n": <номер>, "a": "<ответ>", "flags": ["мат"|"canon?"]}]\n'
    "flags: «мат» — если в ответе есть брань; «canon?» — если вопрос личный (семья/здоровье/биография "
    "адресованного актёра). Пустой массив flags, если не применимо.\n" +
    ("Специфика вопросов — Европа/Исландия/Турция: валюты (евро, кроны, лиры), автобаны и "
     "ограничения, каботаж, туннельные/паромные переправы, «крокодилы»/BAG/жандармы и прочее — "
     "называй так, как названо в самом вопросе; не русифицирую европейскую реальность, но говори "
     "по-русски, как наши водители за границей.\n" if PACK == "eu" else "") +
    "\nОбразцы (одобрены Дмитрием):\n"
)


def post(body, tries=5):
    req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"),
                                 headers={"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt == tries - 1:
                raise
            wait = 5 * (attempt + 1)
            print(f"   сеть/JSON: {e!r} — пауза {wait} с")
            time.sleep(wait)


def gen_batch(questions, style):
    payload = [{"role": "system", "content": SYSTEM + style},
               {"role": "user", "content": "Вопросы:\n" + "\n".join(f"{n}. {q}" for n, q in questions)}]
    d = post({"model": MODEL, "usage": {"include": True}, "messages": payload})
    cost = (d.get("usage") or {}).get("cost", 0.0)
    text = d["choices"][0]["message"]["content"].strip()
    text = re.sub(r"^```(json)?\s*|\s*```$", "", text, flags=re.S)
    arr = json.loads(text)
    assert isinstance(arr, list) and len(arr) == len(questions), \
        f"батч: ждали {len(questions)} ответов, прислали {len(arr) if isinstance(arr, list) else 'не массив'}"
    by_n = {}
    for it in arr:
        n, a = int(it["n"]), str(it["a"]).strip()
        assert n not in by_n, f"дубль n={n}"
        by_n[n] = a
    assert set(by_n) == {n for n, _ in questions}, "номера батча не совпали"
    return by_n, cost


def flags_for(q, a):
    flags = set()
    if MAT_RX.search(a):
        flags.add("мат")
    if CANON_RX.search(q) and NAME_RX.search(q):
        flags.add("canon?")
    return sorted(flags)


def main():
    questions = parse_questions()
    style = sample_block()
    results, total = {}, 0.0
    for i in range(0, 400, BATCH):
        chunk = questions[i:i + BATCH]
        for attempt in range(4):
            try:
                part, cost = gen_batch(chunk, style)
                break
            except (AssertionError, KeyError, ValueError) as e:
                if attempt == 3:
                    raise
                print(f"   батч {chunk[0][0]}-{chunk[-1][0]}: {e} — повтор")
                time.sleep(5)
        for n, a in part.items():
            results[n] = a
        total += cost
        print(f"батч {chunk[0][0]}-{chunk[-1][0]}: OK, ${cost:.4f} (всего ${total:.3f})")
    # контроль: все 400, без пустых/обрезанных
    bad = []
    for n, q in questions:
        a = results.get(n, "")
        if len(a) < MIN_LEN or not a[-1] in ".!?…»" or a.count('"') % 2:
            bad.append((n, a[:60]))
    assert not bad, f"брак: {bad[:8]}"
    rows = [{"n": n, "q": q, "a": results[n], "flags": flags_for(q, results[n])} for n, q in questions]
    OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md = [f"# Драфты общих ответов на экзамен-2{' (EU)' if PACK == 'eu' else ''} (400) — Gemini через OpenRouter, 22.11",
          "",
          "Шаг 1 плана «75%»: только драфты, НЕ интегрировано, НЕ озвучено. Флаги: «мат» — есть брань "
          "(Дмитрий фильтрует на глаз; «эфир чистый» формально в силе), «canon?» — личный вопрос актёру, "
          "Летописец сверяет с каноном. Машинный вид: "
          f"drafts_exam400{SUF}_answers_gemini_2026-11-22.json.", ""]
    for r in rows:
        fl = ("  [" + ", ".join(r["flags"]) + "]") if r["flags"] else ""
        md.append(f"{r['n']}. **В:** {r['q']}")
        md.append(f"   **А:** {r['a']}{fl}")
        md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    n_mat = sum(1 for r in rows if "мат" in r["flags"])
    n_canon = sum(1 for r in rows if "canon?" in r["flags"])
    print(f"готово: 400/400, мат: {n_mat}, canon?: {n_canon}, итого: ${total:.3f}")


if __name__ == "__main__":
    main()
