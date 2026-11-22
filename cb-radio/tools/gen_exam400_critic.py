# -*- coding: utf-8 -*-
"""22.11: критик-проход по драфтам ответов экзамена-2 + регенерация провальных.

Классы дефектов: mirror (зеркаленное обращение из вопроса в устах отвечающего),
wrong_speaker (отвечает не тот/путаница лиц), off_topic (не по существу),
person_mix (я/ты перепутаны), canon (противоречит канону: Сова — вдова, сын взрослый).
Итераций: максимум 2 (критик -> реген -> критик по заменённым). Трогаем только свои
два файла драфтов и этот скрипт.

Пакеты: RU (дефолт), EU — аргументом: gen_exam400_critic.py eu

  G:/Claude/coop-buddy/.venv/Scripts/python.exe -X utf8 tools/gen_exam400_critic.py [ru|eu]
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
SUF = "eu" if PACK == "eu" else ""
KEY = (ROOT / "openrouter_key.txt").read_text(encoding="utf-8").strip()
URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "google/gemini-2.5-flash"
OUT_JSON = ROOT / "phrases" / f"drafts_exam400{SUF}_answers_gemini_2026-11-22.json"
OUT_MD = ROOT / "phrases" / f"drafts_exam400{SUF}_answers_gemini_2026-11-22.md"

BATCH = 30
REGEN_BATCH = 20
MIN_LEN = 25
MAT_RX = re.compile(r"(пизд|хуй|хуя|хуё|хуе|бляд|блять|сука|заебал|заебись|ёбан|ебан|ебать|"
                    r"нахуй|нахер|охуел|охрен|проебал|просрал|жоп|задниц|говн|мудил|долбоящер)", re.I)
CANON_Q_RX = re.compile(r"(жена|муж\b|сын|дочь|дети|внук|бабка|семь[ьяеи]|здоровье|боле[её]т|"
                        r"сколько лет|возраст|домой|помните меня|как там.*(жена|сын|дочь|бабка)|"
                        r"где жив[её]шь|кредит|долги|алимент)", re.I)
NAME_RX = re.compile(r"^(Михалыч|Сова|Янек|Ласточка|Тень|Студент|Стас|Петровна|Витёк|Витек|"
                     r"Самарканд|Ковбой|Профессор|Кинолог|Лиса|Борода|Кардан|Сорока)\b")

CRITIC_SYSTEM = (
    "Ты редактор эфира рации «Канал 15» (русский CB-эфир дальнобойщиков в ETS2). Тебе дают пары "
    "«вопрос игрока — драфт ответа эфира». Отметь драфты с дефектами.\n"
    "Классы дефектов:\n"
    "- mirror: отвечающий повторяет обращение/эпитет ИЗ ВОПРОСА в свой адрес, как будто это про "
    "него сказал кто-то другой (вопрос «Ласточка, привет, красавица…» -> Ласточка отвечает "
    "«привет-привет, красавица» — дефект: красавицей назвали ЕЁ, о себе так не говорят).\n"
    "- wrong_speaker: вопрос адресован конкретному персонажу, а отвечает ДРУГОЙ названный персонаж "
    "(или отвечает сам спрашивающий).\n"
    "- off_topic: ответ не по существу вопроса (спросили про рамку — ответ про погоду).\n"
    "- person_mix: путаница я/ты, самообращение, ответ от лица спрашивающего.\n"
    "- canon: противоречие канону. Известное: Сова — вдова, сын взрослый (29 лет). Драфт, где Сова "
    "рассуждает про живого мужа или маленького ребёнка — дефект. Прочие биографии не выдумываем: "
    "выдуманный конкретный факт биографии НАЗВАННОГО персонажа (болезни, дети, имущество) — тоже canon.\n"
    "Ответ безымянного водителя на общий вопрос — НЕ дефект. Мат — НЕ дефект. Краткость — не дефект.\n"
    "Формат — СТРОГИЙ JSON-массив по ВСЕМ парам батча:\n"
    '[{"n": <номер>, "defect": null|<класс>, "note": "<одна строка, если дефект>"}]\n'
    "defect=null, если драфт в порядке."
)

REGEN_SYSTEM = (
    "Ты пишешь ответы водителей в эфире рации «Канал 15» — русский CB-эфир дальнобойщиков в ETS2. "
    "Тебе дают вопрос игрока и ПРОВАЛЬНЫЙ драфт с пояснением дефекта. Напиши ИСПРАВЛЕННЫЙ ответ.\n"
    "Стиль: 1–3 предложения, самодостаточно, эфирно, по теме вопроса, дальнобойный жаргон "
    "(«баранка», «крокодилы», «тангетка», «рамка», «шершавенькой»). Обращение/позывной, если вопрос "
    "адресный. Отвечающий — тот, кому адресован вопрос (или безымянный водитель на общий вопрос): "
    "эпитеты из вопроса («красавица», «старый») — это то, что сказали ОТВЕЧАЮЩЕМУ, не зеркалить их. "
    "Мат допустим умеренно. НЕ выдумывай биографию персонажей (Сова — вдова, сын взрослый, 29 лет).\n"
    "Формат — СТРОГИЙ JSON-массив: [{\"n\": <номер>, \"a\": \"<исправленный ответ>\"}]"
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


def ask(system, user, expect_n, tag):
    d = post({"model": MODEL, "usage": {"include": True},
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
    cost = (d.get("usage") or {}).get("cost", 0.0)
    text = d["choices"][0]["message"]["content"].strip()
    text = re.sub(r"^```(json)?\s*|\s*```$", "", text, flags=re.S)
    arr = json.loads(text)
    by_n = {}
    for it in arr:
        n = int(it["n"])
        assert n not in by_n, f"дубль n={n} ({tag})"
        by_n[n] = it
    assert set(by_n) == set(expect_n), f"{tag}: номера не сошлись ({len(by_n)} vs {len(expect_n)})"
    return by_n, cost


def critic(rows, tag="критик"):
    defects, total = {}, 0.0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        user = "\n".join(f'{r["n"]}. В: {r["q"]}\n   А: {r["a"]}' for r in chunk)
        for attempt in range(4):
            try:
                by_n, cost = ask(CRITIC_SYSTEM, user, [r["n"] for r in chunk], tag)
                break
            except (AssertionError, KeyError, ValueError, json.JSONDecodeError) as e:
                if attempt == 3:
                    raise
                print(f"   {tag} {chunk[0]['n']}-{chunk[-1]['n']}: {e} — повтор")
                time.sleep(5)
        total += cost
        for n, it in by_n.items():
            if it.get("defect"):
                defects[n] = (str(it["defect"]), str(it.get("note", ""))[:160])
        print(f"{tag} {chunk[0]['n']}-{chunk[-1]['n']}: дефектов {sum(1 for n in by_n if n in defects)} "
              f"(${cost:.4f}, всего ${total:.3f})")
    return defects, total


def regen(rows_by_n, defects, tag="реген"):
    items = sorted(defects)
    out, total = {}, 0.0
    for i in range(0, len(items), REGEN_BATCH):
        chunk = items[i:i + REGEN_BATCH]
        user = "\n".join(f'{n}. В: {rows_by_n[n]["q"]}\n   Старый драфт: {rows_by_n[n]["a"]}\n'
                         f'   Дефект ({defects[n][0]}): {defects[n][1]}\n   Напиши исправленный ответ.'
                         for n in chunk)
        for attempt in range(4):
            try:
                by_n, cost = ask(REGEN_SYSTEM, user, chunk, tag)
                break
            except (AssertionError, KeyError, ValueError, json.JSONDecodeError) as e:
                if attempt == 3:
                    raise
                print(f"   {tag} {chunk[0]}-{chunk[-1]}: {e} — повтор")
                time.sleep(5)
        total += cost
        for n, it in by_n.items():
            a = str(it["a"]).strip()
            assert len(a) >= MIN_LEN and a[-1] in ".!?…»", f"брак в регене n={n}: {a[:50]!r}"
            out[n] = a
        print(f"{tag} {chunk[0]}-{chunk[-1]}: OK (${cost:.4f}, всего ${total:.3f})")
    return out, total


def flags_for(q, a):
    flags = set()
    if MAT_RX.search(a):
        flags.add("мат")
    if CANON_Q_RX.search(q) and NAME_RX.search(q):
        flags.add("canon?")
    return sorted(flags)


def write(rows):
    OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md = [f"# Драфты общих ответов на экзамен-2{' (EU)' if PACK == 'eu' else ''} (400) — Gemini через OpenRouter, 22.11",
          "",
          "Шаг 1 плана «75%»: только драфты, НЕ интегрировано, НЕ озвучено. Прошли критик-проход "
          "(2 итерации максимум): зеркаленные обращения, чужие говорящие, off-topic, путаница лиц, "
          "канон. Флаги: «мат» — есть брань (Дмитрий фильтрует на глаз), «canon?» — личный вопрос "
          "актёру, Летописец сверяет. Машинный вид: drafts_exam400_answers_gemini_2026-11-22.json.", ""]
    for r in rows:
        fl = ("  [" + ", ".join(r["flags"]) + "]") if r["flags"] else ""
        md.append(f"{r['n']}. **В:** {r['q']}")
        md.append(f"   **А:** {r['a']}{fl}")
        md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")


def main():
    rows = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    assert len(rows) == 400
    by_n = {r["n"]: r for r in rows}
    spent = 0.0
    for it in (1, 2):
        defects, cost = critic(rows)
        spent += cost
        print(f"=== итерация {it}: дефектов {len(defects)} ===")
        if not defects:
            break
        fixed, cost = regen(by_n, defects)
        spent += cost
        for n, a in fixed.items():
            by_n[n]["a"] = a
        rows = [by_n[n] for n in sorted(by_n)]
        # повторный критик ТОЛЬКО по заменённым — на следующей итерации цикла
        if it == 2:
            left, cost = critic([by_n[n] for n in sorted(fixed)], tag="контроль")
            spent += cost
            print(f"не исправилось после 2 итераций: {sorted(left) or 'нет'}")
            for n, (cls, note) in sorted(left.items()):
                print(f"  {n}. [{cls}] {note}")
    for r in rows:
        r["flags"] = flags_for(r["q"], r["a"])
        assert len(r["a"]) >= MIN_LEN and r["a"][-1] in ".!?…»", f"брак n={r['n']}"
    write(rows)
    n_mat = sum(1 for r in rows if "мат" in r["flags"])
    n_canon = sum(1 for r in rows if "canon?" in r["flags"])
    print(f"готово: 400/400, мат: {n_mat}, canon?: {n_canon}, критик+реген всего: ${spent:.3f}")


if __name__ == "__main__":
    main()
