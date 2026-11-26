# -*- coding: utf-8 -*-
"""26.11: драфты общих ответов на провалы экзамена-800 v3 — ЛОКАЛЬНАЯ Ollama, без API-токенов.

Вход: build/exam_v3_fails.json (провалы свежего корпуса; обновляется раннером exam_v3_run).
Бэкенд: http://127.0.0.1:11434/api/chat, модель qwen2.5:14b (после печи, GPU свободен).
Стиль — по 25 одобренным образцам (drafts_exam400_answers_sample_2026-11-22.md).
Отвечающий персонаж: из поля who провала (адресный вопрос) или ротация состава.

Выход: cb-radio/phrases/drafts_exam800v3_answers_ollama_2026-11-26.md (+ .json).
Запуск (из корня репо): build/venv/Scripts/python.exe -X utf8 cb-radio/tools/gen_exam_v3_drafts.py
"""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent          # cb-radio/
WS = ROOT.parent            # gruzovichki/
URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5:14b"
FAILS = WS / "build/exam_v3_fails.json"
SAMPLE_FILE = ROOT / "phrases/drafts_exam400_answers_sample_2026-11-22.md"
OUT_MD = ROOT / "phrases/drafts_exam800v3_answers_ollama_2026-11-26.md"
OUT_JSON = ROOT / "phrases/drafts_exam800v3_answers_ollama_2026-11-26.json"
BATCH = 15
MIN_LEN = 25
MAT_RX = re.compile(r"(пизд|хуй|хуя|хуё|хуе|бляд|блять|сука|заебал|заебись|ёбан|ебан|ебать|"
                    r"нахуй|нахер|охуел|охрен|проебал|просрал|жоп|задниц|говн|мудил|долбоящер)", re.I)
CANON_RX = re.compile(r"(жена|муж\b|сын|дочь|дети|внук|бабка|семь[ьяеи]|здоровье|боле[её]т|"
                      r"сколько лет|возраст|домой|помните меня|как там.*(жена|сын|дочь|бабка)|"
                      r"где жив[её]шь|кредит|долги|алимент)", re.I)
NUM_RX = re.compile(r"^(\d{1,3})[\.\)]\s+(.+)$")

PERSONA = {
    "mihalych": "Михалыч — самый возрастной, миллионный пробег, спокойный авторитет, «бродяга/братишка»",
    "sova": "Сова — ночной житель, ворчливо-добрый, про ночную трассу и семью",
    "yanek": "Янек — поляк, говорит по-русски почти без акцента, дружелюбный, «братуха»",
    "lastochka": "Ласточка — девчонка в мужской профессии, бодрая, хлопотная",
    "ten": "Тень — молчаливый ночной, отвечает коротко и по существу",
    "student": "Студент — молодой, горячий, вечно влетает",
    "stas": "Стас (Стасян) — простой работяга, строит дом, про жену и быт",
    "petrovna": "Петровна — душа канала, готовит, всех кормит и жалеет",
    "vitek": "Витёк — летун, любит скорость, вечно собирает штрафы",
    "samarkand": "Самарканд — восточное спокойствие, чай, лепёшки, мудрость",
    "kovboy": "Ковбой — шляпа, кантри, американские тягачи, понты",
    "professor": "Профессор — всё объясняет по-научному, но по-простому",
    "kinolog": "Кинолог — ездит с псом, пёс решает",
    "lisa": "Лиса — рыжая, острая на язык, обижать её себе дороже",
    "boroda": "Борода — старая школа, механика, ненавидит электронику",
    "kardan": "Кардан — главный механик эфира, чинит всё и у всех",
    "soroka": "Сорока — главная сплетница канала, всё знает раньше диспетчеров",
    "ment": "Мент (Палыч) — бывший гаишник, знает все законы и засады",
    "vera": "Вера — ровная, домашняя, держит фронт",
    "rustam": "Рустам — южанин, про границы, базары и чайхану",
    "bahti": "Бахти — кавказское гостеприимство, «дорогой», кормит",
    "buh": "Бухгалтерия — голос с базы, считает копейки и суточные",
}
ROTATE = ["mihalych", "kardan", "soroka", "sova", "yanek", "professor", "boroda", "stas",
          "petrovna", "vitek", "ment", "lisa", "lastochka", "kinolog", "kovboy", "samarkand"]


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
    "- По теме вопроса: спросили про затык/весы/солярку/душ — отвечай конкретно про это.\n"
    "- Обращение/позывной, если вопрос адресный; общие вопросы — «мужики/братишки/парни».\n"
    "- Дальнобойный жаргон: «баранка», «крокодилы», «тангетка», «рамка», «машинки» (гаишники), "
    "«плечевые», «колейка» (пробка), «шершавенькой», «обнял-приподнял».\n"
    "- Мат допустим, но умеренно (как в образцах).\n"
    "- НЕ выдумывай биографические факты персонажей (семья/дети/возраст/здоровье): на личные "
    "вопросы отвечай нейтрально-общим эфирным юмором без конкретных фактов.\n"
    "- Никаких пояснений вне ответов, никаких кавычек вокруг ответа.\n"
    "Кто отвечает: в каждом вопросе указан отвечающий в формате [ОТВЕЧАЕТ: Имя — характер]. "
    "Ответ пишется от этого персонажа, с его манерой; можно начать «<Имя> на связи/на приёме».\n"
    "Формат — СТРОГИЙ JSON-массив без markdown-ограждений:\n"
    '[{"n": <номер>, "a": "<ответ>"}]\n'
    "\nОбразцы (одобрены Шефом):\n"
)


def post(body, tries=4):
    req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                return json.load(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if attempt == tries - 1:
                raise
            wait = 10 * (attempt + 1)
            print(f"   ollama: {e!r} — пауза {wait} с", flush=True)
            time.sleep(wait)


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(json)?\s*|\s*```$", "", text, flags=re.S).strip()
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


class BatchError(Exception):
    """Батч не удался целиком; partial — что удалось разобрать (по валидным номерам)."""

    def __init__(self, msg, partial=None):
        super().__init__(msg)
        self.partial = partial or {}


def gen_batch(items, style):
    """items: [(n, q, persona_id)] → {n: ответ}. Недобор/битый JSON — BatchError с partial."""
    lines = []
    for n, q, pid in items:
        who = PERSONA.get(pid, "безымянный водитель — нейтральный мужик с трассы")
        lines.append(f"{n}. [ОТВЕЧАЕТ: {who}] {q}")
    payload = [{"role": "system", "content": SYSTEM + style},
               {"role": "user", "content": "Вопросы:\n" + "\n".join(lines)}]
    d = post({"model": MODEL, "messages": payload, "stream": False,
              "options": {"num_predict": 4096, "temperature": 0.85}})
    text = d["message"]["content"]
    try:
        arr = extract_json(text)
    except json.JSONDecodeError as e:
        raise BatchError(f"битый JSON: {e}")
    if not isinstance(arr, list):
        raise BatchError(f"ответ не массив: {type(arr).__name__}")
    want = {n for n, _, _ in items}
    by_n = {}
    for it in arr:
        if not isinstance(it, dict):
            continue
        try:
            n, a = int(it["n"]), str(it["a"]).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if n in want and a:
            by_n[n] = a
    missing = sorted(want - set(by_n))
    if missing:
        raise BatchError(f"не хватает {len(missing)}/{len(want)} "
                         f"(нет ответов на №{missing[:5]}{'…' if len(missing) > 5 else ''})", partial=by_n)
    return by_n


def flags_for(q, a, pid):
    flags = set()
    if MAT_RX.search(a):
        flags.add("мат")
    if CANON_RX.search(q) and pid:
        flags.add("canon?")
    return sorted(flags)


def write_outputs(results, items):
    """Промежуточная/финальная запись md+json — после каждого батча, чтобы прогресс не терялся."""
    bad = []
    for n, q, pid in items:
        a = results.get(n, "")
        if n in results and (len(a) < MIN_LEN or a[-1] not in ".!?…»" or a.count('"') % 2):
            bad.append((n, a[:60]))
    rows = [{"n": n, "q": q, "who": pid, "a": results.get(n, ""), "flags": flags_for(q, results.get(n, ""), pid)}
            for n, q, pid in items]
    OUT_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    md = ["# Драфты общих ответов на провалы экзамена-800 v3 — локальная Ollama qwen2.5:14b, 26.11",
          "",
          "Только драфты, НЕ интегрировано, НЕ озвучено. Флаги: «мат» — есть брань (Шеф фильтрует "
          "на глаз; «эфир чистый» формально в силе), «canon?» — личный вопрос актёру, Летописец "
          "сверяет с каноном. Отвечающий персонаж — в поле who.", ""]
    for r in rows:
        fl = ("  [" + ", ".join(r["flags"]) + "]") if r["flags"] else ""
        md.append(f"{r['n']}. **В:** {r['q']}")
        md.append(f"   **А ({r['who']}):** {r['a']}{fl}")
        md.append("")
    OUT_MD.write_text("\n".join(md), encoding="utf-8")
    return rows, bad


def main():
    data = json.loads(FAILS.read_text(encoding="utf-8"))
    fails = data["fails"]
    print(f"провалов на входе: {len(fails)} (покрытие на момент снимка: {data['pct']:.1f}%)", flush=True)
    style = sample_block()
    items, rot = [], 0
    for f in fails:
        pid = f.get("who")
        if pid not in PERSONA:
            pid = ROTATE[rot % len(ROTATE)]
            rot += 1
        items.append((f["n"], f["q"], pid))
    results = {}
    skipped = []  # номера, которые не вышло получить ни с одной попытки
    MAX_TRIES = 3  # первый запрос + 2 переспроса
    for i in range(0, len(items), BATCH):
        chunk = items[i:i + BATCH]
        part: dict = {}
        last_err: Exception | None = None
        for attempt in range(MAX_TRIES):
            try:
                part = gen_batch(chunk, style)
                last_err = None
                break
            except BatchError as e:
                # забираем частичный разбор и пробуем ещё (модель может дать недобор снова,
                # но с другими номерами — мержим всё валидное)
                part = {**part, **e.partial}
                last_err = e
                if attempt < MAX_TRIES - 1:
                    print(f"   батч {chunk[0][0]}-{chunk[-1][0]}: {e} — повтор {attempt + 1}/{MAX_TRIES - 1}",
                          flush=True)
                    time.sleep(8)
        if last_err is not None:
            miss = [n for n, _, _ in chunk if n not in part]
            skipped.extend(miss)
            print(f"батч {chunk[0][0]}-{chunk[-1][0]}: ПРОПУСК после {MAX_TRIES} попыток "
                  f"({last_err}); пропущено №{miss}", flush=True)
        results.update(part)
        print(f"батч {chunk[0][0]}-{chunk[-1][0]}: OK ({len(results)}/{len(items)})", flush=True)
        rows, bad = write_outputs(results, items)  # инкрементально: файл живёт после каждого батча
        if bad:
            print(f"   брак в батче (не критично, Шеф смотрит глазами): {bad[:5]}", flush=True)
    rows, bad = write_outputs(results, items)
    if bad:
        print(f"ВНИМАНИЕ, брак (не критично, Шеф смотрит глазами): {bad[:10]}", flush=True)
    if skipped:
        print(f"ИТОГО пропущено {len(skipped)} (модель не выдала ответ ни с одной попытки): "
              f"№{skipped}", flush=True)
    n_mat = sum(1 for r in rows if "мат" in r["flags"])
    n_canon = sum(1 for r in rows if "canon?" in r["flags"])
    print(f"готово: {len(rows)}/{len(items)} (пропущено {len(skipped)}), мат: {n_mat}, canon?: {n_canon} "
          f"-> {OUT_MD.name}", flush=True)


if __name__ == "__main__":
    main()
