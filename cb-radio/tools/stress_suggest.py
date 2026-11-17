"""Кандидаты на добавление в stress_dict.json из черновика реплик.

ruaccent (оценка 17.11) НЕ является источником истины: на коварных словах («гудни», «йогурты»)
он ошибается так же, как TTS. Поэтому инструмент НИЧЕГО не правит — он выдаёт список слов
на РУЧНУЮ сверку:

  - «без ударения»: слово, которое модель не разметила и которого нет в stress_dict
    (имена, позывные, жаргон — типичные коварные слова);
  - «расхождение со словарём»: если черновик содержит слово из stress_dict, а модель ставит
    иное ударение — повод проверить оба варианта головой (модель часто ошибается, но и
    словарь может быть неполным).

Использование:
  stress_suggest.py <файл.md> [файл2.md ...]     — из файлов-черновиков
  stress_suggest.py level3                       — по всему эфиру level3_eleven.json
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stress_check as sc          # noqa: E402  (общий загрузчик ruaccent и словаря)

VOWELS = "аеёиоуыэюя"


def _stressed_vowel(form):
    for ch in form:
        if ch in VOWELS.upper():
            return ch.lower()
    return None


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
    texts = []
    for arg in argv[1:]:
        if arg == "level3":
            texts += [t for _, t in sc._lines_level3()]
        else:
            texts += sc._lines_from_md(arg)
    if not texts:
        sys.exit("нет входных строк — передай файлы черновиков или level3")
    rows = suggest(texts)
    print(f"строк: {len(texts)}, кандидатов: {len(rows)}")
    for w, kind, detail in sorted(rows, key=lambda r: (r[1], r[0])):
        print(f"{kind:9s} | {w:20s} | {detail}")
    print("\nНичего не изменено. Отобранное вручную добавляйте в phrases/stress_dict.json "
          "(поля word, stressed с заглавной ударной гласной, ipa, who, date).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
