"""Кандидаты на добавление в stress_dict.json из черновика реплик.

Два движка:
  - по умолчанию: ruaccent (УСТАРЕЛ, оценка 17.11 — на коварных словах («гудни», «йогурты»)
    ошибается так же, как TTS; оставлен как fallback без сети);
  - --giga: GigaChat-2-Pro (Сбер) — основной генератор кандидатов (18.11). Разметка «+» после
    ударной гласной, флаг «!» для коварных слов. Кэш — build/stress_lexicon.json (общий
    с build/stress_scan.py: готовые слова из кэша не дёргают API).

Инструмент НИЧЕГО не правит — он выдаёт список слов на РУЧНУЮ сверку:
  - «tricky»: слово не из stress_dict, которое GigaChat пометил коварным (!) — кандидат в словарь;
  - «no-stress»: слово не из stress_dict и без ударения в разметке (имена, позывные, жаргон);
  - «dict-diff»: слово из stress_dict, а разметка ставит иное ударение — сверить оба варианта головой.

Источник истины по ударениям — phrases/stress_dict.json; GigaChat лишь генератор кандидатов.

Использование:
  stress_suggest.py <файл.md> [файл2.md ...]     — из файлов-черновиков (ruaccent)
  stress_suggest.py --giga <файл.md> [...]       — то же через GigaChat (основной путь)
  stress_suggest.py level3 / --giga level3       — по всему эфиру level3_eleven.json
"""
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stress_check as sc          # noqa: E402  (общий загрузчик ruaccent и словаря)

WS_ROOT = Path(__file__).resolve().parents[2]
LEX_F = WS_ROOT / "build" / "stress_lexicon.json"
FLAG_F = WS_ROOT / "build" / "stress_flagged.json"
GIGA_KEY_F = WS_ROOT / "build" / "gigachat_key.txt"
BATCH = 250

VOWELS = "аеёиоуыэюя"

PROMPT = (
    "Ты — эксперт по русской орфоэпии. Ниже список русских слов из радиопьесы (разговорная речь дальнобойщиков). "
    "Для КАЖДОГО слова верни строку в формате: слово с + сразу ПОСЛЕ ударной гласной. "
    "Пример: на входе «гудок, трасса, позвонишь» — на выходе три строки: «гудо+к», «тра+сса», «позвони+шь». "
    "Каждая твоя строка ОБЯЗАНА содержать знак +. Строк без + быть не должно. "
    "Если ударение зависит от смысла (омоним: за+мок/замо+к) — дай оба варианта через запятую. "
    "Если слово КОВАРНОЕ для синтезаторов речи (частые ошибки TTS: глаголы прошедшего времени женского рода вроде взяла+, "
    "возвратные глаголы, слова с редким ударением, заимствования, жаргон) — добавь в конец строки знак ! "
    "Ответ — ТОЛЬКО строки слов, без нумерации, без пояснений.\n\nСлова:\n"
)


def _stressed_vowel(form):
    for ch in form:
        if ch in VOWELS.upper():
            return ch.lower()
    return None


def _uniq_words(texts):
    words = set()
    for t in texts:
        for w in re.findall(r"[А-Яа-яЁё-]{3,}", t.lower()):
            if w.count("-") <= 1 and sum(c in VOWELS for c in w) >= 2 and "ё" not in w:
                words.add(w)
    return sorted(words)


def _load_json(path):
    return json.load(open(path, encoding="utf-8")) if path.exists() else {}


def _giga_mark(words):
    """words -> {слово: разметка с '+' (и, возможно, '!')}. Дополняет build-лексикон."""
    from gigachat import GigaChat
    lexicon = _load_json(LEX_F)
    todo = [w for w in words if w not in lexicon]
    print(f"giga: в кэше {len(words) - len(todo)}/{len(words)}, к API — {len(todo)} слов", flush=True)
    if not todo:
        return lexicon
    key = GIGA_KEY_F.read_text(encoding="utf-8").strip()
    with GigaChat(credentials=key, verify_ssl_certs=False, scope="GIGACHAT_API_PERS",
                  model="GigaChat-2-Pro") as giga:
        for i in range(0, len(todo), BATCH):
            batch = todo[i:i + BATCH]
            text = None
            for attempt in range(4):
                try:
                    if attempt == 0:
                        r = giga.chat(PROMPT + "\n".join(batch))
                    else:
                        r = giga.chat(
                            "В прошлый раз ты вернул слова БЕЗ знаков +. Повтори задание строго: "
                            "КАЖДАЯ строка = слово с + сразу после ударной гласной (тра+сса, гудо+к). "
                            "Только строки со словами.\n\nСлова:\n" + "\n".join(batch))
                    if "+" in r.choices[0].message.content:
                        text = r.choices[0].message.content
                        break
                    print(f"батч {i // BATCH}: ответ без '+', попытка {attempt + 1}", flush=True)
                except Exception as e:
                    print(f"батч {i // BATCH}: попытка {attempt + 1} ошибка {repr(e)[:120]}", flush=True)
                    time.sleep(20 * (attempt + 1))
            if text is None:
                print(f"батч {i // BATCH}: ПРОПУЩЕН после попыток", flush=True)
                continue
            got = 0
            for line in text.splitlines():
                line = line.strip().strip(".,;")
                if not line or "+" not in line:
                    continue
                trick = line.endswith("!")
                if trick:
                    line = line[:-1].strip()
                # модель иногда обрывает хвост слова: ключ — исходное слово из батча
                plain = line.replace("+", "").split(",")[0].strip()
                for w in batch:
                    if w == plain or (len(plain) >= 3 and w.startswith(plain)):
                        lexicon[w] = line + ("!" if trick else "")
                        got += 1
                        break
            print(f"батч {i // BATCH + 1}: принято {got}/{len(batch)}", flush=True)
            json.dump(lexicon, open(LEX_F, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            time.sleep(2)
    return lexicon


def _giga_stressed_vowel(marked):
    """Формат GigaChat: '+' сразу ПОСЛЕ ударной гласной ('гудо+к'). '+' после согласной
    или в конце слова — мусор разметки (обрывки хвоста), не ударение -> None."""
    i = marked.find("+")
    if i <= 0:
        return None
    ch = marked[i - 1].lower()
    return ch if ch in VOWELS else None


def suggest_giga(texts):
    """GigaChat: {word: (kind, detail)} — tricky | no-stress | dict-diff."""
    d = sc.stress_dict()
    lexicon = _giga_mark(_uniq_words(texts))
    flagged = _load_json(FLAG_F)
    out = []
    for w, marked in sorted(lexicon.items()):
        first = marked.split(",")[0]
        has_stress = "+" in first
        if w in d:
            want = _stressed_vowel(d[w]["stressed"])
            got = _giga_stressed_vowel(first) if has_stress else None
            if got and got != want:
                out.append((w, "dict-diff", f"словарь {d[w]['stressed']} | giga {marked}"))
        elif marked.endswith("!") or w in flagged:
            out.append((w, "tricky", f"giga: коварное — {marked}"))
        elif not has_stress:
            out.append((w, "no-stress", "giga не разметил — имя/жаргон?"))
    return out


def suggest(texts):
    """[(word, kind, detail)] — kind: 'no-stress' (нет в словаре и без ударения) | 'dict-diff'."""
    d = sc.stress_dict()
    out = []
    seen = set()
    for text in texts:
        clean = sc.TAG_RX.sub(" ", text)
        marked = sc._acc().process_all(clean)
        for tok in marked.split():
            low = sc._word_tok(tok)
            if not low:
                continue
            w = low.replace("+", "")
            if not sc.WORD_RX.fullmatch(w) or sum(ch in VOWELS for ch in w) <= 1 or w in seen or "ё" in w:
                continue
            got = None
            for i, ch in enumerate(low):
                if ch == "+" and i + 1 < len(low):
                    got = low[i + 1]
                    break
            if w in d:
                want = _stressed_vowel(d[w]["stressed"])
                if got != want and got is not None:
                    seen.add(w)
                    out.append((w, "dict-diff", f"словарь {d[w]['stressed']} | модель {tok.lower()}"))
            elif got is None:
                # модель не поставила ударение вовсе — ручная проверка обязательна
                single = sc._acc().process_all(w)
                if "+" not in single:
                    seen.add(w)
                    out.append((w, "no-stress", "модель не размечает — имя/жаргон?"))
    return out


def main(argv):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    use_giga = "--giga" in argv
    argv = [a for a in argv if a != "--giga"]
    texts = []
    for arg in argv[1:]:
        if arg == "level3":
            texts += [t for _, t in sc._lines_level3()]
        else:
            texts += sc._lines_from_md(arg)
    if not texts:
        sys.exit("нет входных строк — передай файлы черновиков или level3")
    rows = suggest_giga(texts) if use_giga else suggest(texts)
    print(f"строк: {len(texts)}, кандидатов: {len(rows)}")
    for w, kind, detail in sorted(rows, key=lambda r: (r[1], r[0])):
        print(f"{kind:9s} | {w:20s} | {detail}")
    print("\nНичего не изменено. Отобранное вручную добавляйте в phrases/stress_dict.json "
          "(поля word, stressed с заглавной ударной гласной, ipa, who, date).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
