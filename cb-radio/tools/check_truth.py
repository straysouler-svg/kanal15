"""Сверка «одного источника правды» (2026-11-10): что сейчас не сходится и что ждёт озвучки.

  py tools/check_truth.py            сводка
  py tools/check_truth.py --list     то же + полный список реплик, ждущих озвучки

Ничего не меняет и никуда не ходит по сети: читает phrases/level3_eleven.json, манифесты в audio/,
CHARACTERS.md, ACTORS_RULES.md, intents.py, bonds.py. Работает на системном Python (без numpy).

Разделы:
  1. Очередь озвучки — реплики, у которых текст новый или изменён, а звука нет / звук от старого текста
     (та же проверка, что в tools/gen_eleven.py: подпись voice_id|model|stability|text в manifest.json).
  2. Канон — ключи и имена: таблица личных дел в CHARACTERS.md против актёров в json, возраст против года
     рождения, устаревшие имена (STALE), имена в intents.NAMES.
  3. Настроение — сколько у каждого водителя реплик на каждое настроение (как их видит bonds.py).
  4. Резервные копии в рабочей папке.
"""
import datetime
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import bonds  # noqa: E402
import intents  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

# Имена и слова, которых в каноне быть уже не должно: (что искать, почему). Дополнять при каждом решении.
STALE = [
    ("Тамара", "Сорока — Татьяна Петровна Храмкова (решение 10.11)"),
    ("Рустамов", "Бахтияр — Юлдашев, младший брат Рустама (решение 10.11)"),
    ("Рустамович", "у Бахтияра нет отчества (решение 10.11)"),
    ("Тихонов Алексей", "Стас — Тихонов Станислав Дмитриевич (решение 10.11)"),
    ("восемьдесят седьм", "история Михалыча — 1991 год, «в девяносто первом» (решение 10.11)"),
]
STALE_FILES = ["CHARACTERS.md", "ACTORS_RULES.md", "DESIGN.md", "phrases/level3_eleven.json"]
STALE_STEMS = [("soroka", "тамар", "Сорока — Татьяна: нужна основа «татьян», «таня»")]   # intents.NAMES
# Уменьшительные, которые расхождением не считаются (имя в биографии -> имя в личном деле).
DIMIN = {"Лёша": "Алексей", "Серёга": "Сергей", "Гена": "Геннадий", "Витёк": "Виктор", "Ян": "Ян", "Стасян": "Станислав"}
MOOD_MIN = 5          # меньше стольких реплик на настроение — предупреждение
PRICE_NOTE = {"eleven": "символы ElevenLabs", "gpt-audio": "реплики OpenRouter", "xtts": "локально, бесплатно"}


def _sig(a, text):
    return f"{a.get('voice_id')}|{a.get('model', 'eleven_v3')}|{a.get('stability', 0.5)}|{text}"


def _manifest(d):
    try:
        return json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _man_text(man_val):
    """текст из подписи манифеста voice|model|stability|TEXT[|far=..][|rec=..]"""
    body = "|".join(man_val.split("|")[3:])
    for tail in ("|far=", "|rec="):
        i = body.find(tail)
        if i != -1:
            body = body[:i]
    return body


def _why(prev, path, cur_text):
    """причина попадания в очередь: нет файла / другой текст / тот же текст другим голосом"""
    if not path.exists():
        return "нет звука"
    if prev and _man_text(prev) == cur_text:
        return "текст тот же, другой голос"
    return "текст изменён, звук старый"


def queue(data):
    """[(engine, where, actor, why, text)] — everything gen_eleven.py would voice right now."""
    out = []
    actors = data["actors"]
    for key, a in actors.items():
        wet, man = ROOT / "audio" / "level3" / key, _manifest(ROOT / "audio" / "level3_clean" / key)
        drop = set(a.get("drop", []))
        for i, item in enumerate(a.get("phrases", []), 1):
            if i in drop:
                continue
            n = f"{i:02d}"
            rec = item.get("rec") if isinstance(item, dict) else None
            text = item["text"] if isinstance(item, dict) else item
            sig = _sig(a, f"{text} @{rec}" if rec else text)
            if man.get(n) == sig and (wet / f"{n}.wav").exists():
                continue
            why = _why(man.get(n), wet / f"{n}.wav", f"{text} @{rec}" if rec else text)
            out.append(("rec" if rec else a.get("engine", "eleven"), f"{key}/{n}", key, why, text))

    def lines_of(d, lines, where):
        man = _manifest(d)
        for i, ln in enumerate(lines, 1):
            if not isinstance(ln, dict) or ln.get("actor") not in actors:
                continue
            n, a = f"{i:02d}", actors[ln["actor"]]
            sig = _sig(a, ln["text"]) + f"|far={bool(ln.get('far'))}" + (f"|rec={ln['rec']}" if ln.get("rec") else "")
            if man.get(n) == sig and (d / f"{n}.wav").exists():
                continue
            why = _why(man.get(n), d / f"{n}.wav", ln["text"])
            out.append(("rec" if ln.get("rec") else a.get("engine", "eleven"), f"{where}/{n}", ln["actor"], why,
                        ln["text"]))

    for group, kinds in data.get("reactions", {}).items():
        if group.startswith("_") or not isinstance(kinds, dict):
            continue
        for kind, lines in kinds.items():
            if not kind.startswith("_") and isinstance(lines, list):
                lines_of(ROOT / "audio" / "reactions" / group / kind, lines, f"reactions/{group}/{kind}")
    for sid, lines in data.get("scenes", {}).items():
        if isinstance(lines, list):
            lines_of(ROOT / "audio" / "scenes" / sid, lines, f"scenes/{sid}")
    return out


def canon(data):
    """List of human-readable problems between CHARACTERS.md, the phrases file and intents.NAMES."""
    problems = []
    actors = data["actors"]
    md = (ROOT / "CHARACTERS.md").read_text(encoding="utf-8")
    rows = {}                                           # key -> (позывной, ФИО, год рождения)
    for m in re.finditer(r"^\|\s*([^|]+?)\s*\|\s*([a-z_]+)\s*\|\s*\*\*([^*]+)\*\*[^|]*\|\s*(\d\d)\.(\d\d)\.(\d{4})", md, re.M):
        rows[m.group(2)] = (m.group(1), m.group(3), int(m.group(6)), int(m.group(5)), int(m.group(4)))
    if not rows:
        return ["в CHARACTERS.md не найдена таблица личных дел"]
    for k in rows:
        if k not in actors:
            problems.append(f"таблица личных дел: ключ `{k}` ({rows[k][0]}) — такого актёра нет в json")
    for k in actors:
        if k not in rows and not k.startswith("driver.") and actors[k].get("phrases"):
            problems.append(f"json: актёр `{k}` ({actors[k].get('name', '?')}) — нет строки в таблице личных дел")
    # возраст в заголовке биографии против года рождения в таблице
    today = datetime.date.today()
    by_call = {v[0].lower(): k for k, v in rows.items()}
    for m in re.finditer(r"^#{2,3}\s+([^\n—]+?)\s+—\s+([^\n]*?)(\d\d)\s+(?:год|года|лет)", md, re.M):
        head, rest, age = m.group(1).strip(), m.group(2), int(m.group(3))
        call = re.search(r"позывной «([^»]+)»", rest)
        k = by_call.get((call.group(1) if call else head).lower())
        if not k:
            continue
        _, fio, y, mo, d = rows[k]
        real = today.year - y - ((today.month, today.day) < (mo, d))
        if abs(real - age) > 1:
            problems.append(f"возраст: {head} — в биографии {age}, по дате рождения {real} ({d:02d}.{mo:02d}.{y})")
        first = [w for w in re.split(r"[\s,]+", rest) if w and w[0].isupper()]
        if first and not call and first[0] not in fio and first[0][:4] not in fio                 and DIMIN.get(first[0], "-") not in fio:
            problems.append(f"имя: {head} — в биографии «{first[0]}», в личном деле «{fio}»")
    # устаревшие имена
    for word, why in STALE:
        for f in STALE_FILES:
            p = ROOT / f
            if p.exists():
                n = p.read_text(encoding="utf-8", errors="ignore").count(word)
                if n:
                    problems.append(f"устаревшее «{word}» — {f}: {n} раз ({why})")
    # распознавание имён: у каждого актёра есть запись в intents.NAMES, устаревших основ в ней нет
    for k, (call, *_rest) in rows.items():
        if k in actors and k != "buh" and not intents.NAMES.get(k):     # бухгалтерию по имени не зовут
            problems.append(f"intents.NAMES: нет записи для `{k}` ({call})")
    for k, stem, why in STALE_STEMS:
        if stem in intents.NAMES.get(k, []):
            problems.append(f"intents.NAMES[{k}]: устаревшая основа «{stem}» ({why})")
    return problems


def moods(data):
    """actor -> Counter(mood) over every line he says (phrases + reactions + scenes)."""
    c = defaultdict(Counter)

    def add(actor, ln):
        text = ln.get("text", "") if isinstance(ln, dict) else ln
        m = (ln.get("mood") if isinstance(ln, dict) and ln.get("mood") in bonds.MOODS else None) or bonds.line_mood(text)
        c[actor][m or "none"] += 1

    for k, a in data["actors"].items():
        for ph in a.get("phrases", []):
            add(k, ph)
    for part in ("reactions", "scenes"):
        stack = [data.get(part, {})]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                if isinstance(o.get("text"), str) and o.get("actor"):
                    add(o["actor"], o)
                else:
                    stack.extend(o.values())
            elif isinstance(o, list):
                stack.extend(o)
    return c


def main():
    full = "--list" in sys.argv
    data = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    bad = 0

    q = queue(data)
    print(f"1. ОЧЕРЕДЬ ОЗВУЧКИ: {len(q)} реплик")
    by = defaultdict(list)
    for e in q:
        by[e[0]].append(e)
    for eng, items in sorted(by.items()):
        chars = sum(len(x[4]) for x in items)
        stale_txt = sum(1 for x in items if x[3] == "текст изменён, звук старый")
        stale_voice = sum(1 for x in items if x[3] == "текст тот же, другой голос")
        chars_txt = sum(len(x[4]) for x in items if x[3] == "текст изменён, звук старый")
        chars_voice = sum(len(x[4]) for x in items if x[3] == "текст тот же, другой голос")
        who = ", ".join(f"{a} {n}" for a, n in Counter(x[2] for x in items).most_common())
        print(f"   {eng}: {len(items)} реплик, {chars} символов ({PRICE_NOTE.get(eng, 'запись')})")
        print(f"      А. текст изменён, звук старый: {stale_txt} реплик, {chars_txt} символов"
              f"   |   Б. текст тот же, другой голос: {stale_voice} реплик, {chars_voice} символов")
        print(f"      {who}")
        for x in (items if full else [i for i in items if i[3].startswith("текст")][:10]):
            print(f"      - {x[1]} [{x[3]}] {x[4][:90]}")
    stale_all = sum(1 for x in q if x[3] == "текст изменён, звук старый")
    if stale_all:
        bad += stale_all
        print(f"   ! {stale_all} реплик звучат в эфире старым текстом")
    voice_all = sum(1 for x in q if x[3] == "текст тот же, другой голос")
    if voice_all:
        print(f"   ! {voice_all} реплик записаны не голосом персонажа (текст тот же)")

    pr = canon(data)
    bad += len(pr)
    print(f"\n2. КАНОН: {len(pr)} расхождений")
    for p in pr:
        print(f"   - {p}")

    print("\n3. НАСТРОЕНИЕ РЕПЛИК (в духе / спокоен / устал / хмурый / без настроения)")
    c = moods(data)
    thin, shown = [], 0
    for k in data["actors"]:
        n = sum(c[k].values())
        if n < 20 or bonds.TEMPER.get(k) is None:
            continue
        shown += 1
        lack = [bonds.MOODS[m]["name"] for m, share in zip(bonds.Bonds.ORDER[::-1], bonds.TEMPER[k])
                if share > 0 and c[k][m] < MOOD_MIN]
        print(f"   {k:10s} {c[k]['cheerful']:4d} {c[k]['calm']:4d} {c[k]['tired']:4d} {c[k]['grumpy']:4d}"
              f" {100 * c[k]['none'] // n:4d}%" + (f"   мало: {', '.join(lack)}" if lack else ""))
        if lack:
            thin.append(k)
    print(f"   водителей, у которых на какое-то настроение меньше {MOOD_MIN} реплик: {len(thin)} из {shown}")

    backups = [p for p in ROOT.glob("*.before_*") if p.is_file()] + list((ROOT / "phrases").glob("*.before_*"))
    print(f"\n4. РЕЗЕРВНЫЕ КОПИИ в рабочей папке: {len(backups)} файлов,"
          f" {sum(p.stat().st_size for p in backups) // 1024 // 1024} МБ")

    print(f"\nИТОГО: {'расхождений нет' if not bad else f'требует внимания: {bad}'};"
          f" в очереди озвучки {len(q)}")


if __name__ == "__main__":
    main()
