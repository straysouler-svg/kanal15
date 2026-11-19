"""Тесты выбора фрагмента журнала для диагностического отчёта (P0-3 + P1-9, промт stabilizaciya_2026-11-19).

Контракт порядка строк (P1-9): журнал на диске — append-only ХРОНОЛОГИЯ (новые записи — в конец
файла). pick_log_fragment берёт ПОСЛЕДНИЕ REPORT_LINES строк (самые свежие), переворот не нужен.
История: до P0-3 make_report() брал splitlines()[-4000:] на newest-first файле — в отчёт попадали
СТАРЫЕ записи; P0-3 брал первые 4000 newest-first и переворачивал; P1-9 перевёл журнал на
append-only — свежие стали последними.

Запуск: G:\\Claude\\gruzovichki\\build\\venv\\Scripts\\python.exe -X utf8 cb-radio/tools/test_report_log.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # cb-radio/ на пути — импорт report_log без рации

from report_log import REPORT_LINES, pick_log_fragment          # noqa: E402

NL = "\n"


def enc(lines):
    return NL.join(lines).encode("utf-8")


def check(cond, what):
    if not cond:
        raise SystemExit(f"FAIL: {what}")
    print(f"ok: {what}")


# 1. Журнал короче 4000 строк: ничего не теряется, порядок — хронологический (как в файле).
short = [f"12:0{i}:00 строка {i}" for i in range(5)]            # append-only: строка 4 — последняя и самая свежая
out = pick_log_fragment(enc(short)).decode("utf-8")
check(out == NL.join(short), "короткий журнал целиком, в хронологическом порядке")

# 2. Журнал из 5000 строк с маркерами OLD/NEW: свежие на месте, самые старые отсутствуют.
#    append-only: последние строки файла — самые свежие (NEW), первые — самые старые (OLD).
big = [f"NEW-{i:04d}" for i in range(5000)]                    # 4999 — самая свежая (последняя строка)
big[0] = "OLD-старт"
out_lines = pick_log_fragment(enc(big)).decode("utf-8").splitlines()
check(len(out_lines) == REPORT_LINES, f"ровно {REPORT_LINES} строк в отчёте")
check(out_lines[0] == f"NEW-{5000 - REPORT_LINES:04d}" and out_lines[-1] == "NEW-4999",
      "самые свежие записи на месте, в хронологическом порядке")
check("OLD-старт" not in out_lines and "NEW-0000" not in out_lines, "самые старые записи отсутствуют")

# 3. Пустой журнал.
check(pick_log_fragment(b"") == b"", "пустой журнал -> пустой фрагмент")

# 4. Unicode и очень длинные строки проходят без искажений.
uni = ["старая запись ☃ é ё", "свежая «цитата» \U0001f600"]
check(pick_log_fragment(enc(uni)) == enc(uni), "unicode без искажений, порядок хронологический")
long_line = "X" * 200000
out = pick_log_fragment(enc([long_line, "old"])).decode("utf-8")
check(long_line in out, "очень длинная строка проходит целиком")

# 5. Режимы с фильтрацией речи и без: реплики игрока скрываются только по флагу.
log_lines = ["тангента: «привет, это я» → принял: Палыч", "12:00 обычная запись «цитата не игрока»",
             "13:00 тангента без кавычек"]
full = pick_log_fragment(enc(log_lines)).decode("utf-8")
check("«привет, это я»" in full and "«цитата не игрока»" in full, "без флага фразы на месте")
hidden = pick_log_fragment(enc(log_lines), hide_speech=True).decode("utf-8")
check("«привет, это я»" not in hidden and "«(скрыто)»" in hidden, "с флагом фраза игрока скрыта")
check("«цитата не игрока»" in hidden, "чужие цитаты не тронуты")
check("тангента без кавычек" in hidden, "строка тангенты без кавычек не ломается")

print("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
