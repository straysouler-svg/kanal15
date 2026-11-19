"""Тесты выбора фрагмента журнала для диагностического отчёта (P0-3, промт stabilizaciya_2026-11-19).

Журнал на диске — newest-first (_flush_log в cb_radio.py): свежие записи — первые физические строки.
Было: make_report() брал splitlines()[-4000:] — в отчёт попадали СТАРЫЕ записи, свежие отбрасывались.
Стало: report_log.pick_log_fragment берёт первые REPORT_LINES строк и переворачивает в хронологию.

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


# 1. Журнал короче 4000 строк: ничего не теряется, порядок — хронологический.
short = [f"12:0{i}:00 строка {i}" for i in range(5)]            # newest-first: строка 4 — первая
out = pick_log_fragment(enc(short)).decode("utf-8")
check(out == NL.join(reversed(short)), "короткий журнал целиком, в хронологическом порядке")

# 2. Журнал из 5000 строк с маркерами OLD/NEW: свежие на месте, самые старые отсутствуют.
#    newest-first: первая строка файла — самая свежая (NEW), последние — самые старые (OLD).
big = [f"NEW-{i:04d}" for i in range(5000)]                    # 0000 — самая свежая
big[-1] = "OLD-старт"
out_lines = pick_log_fragment(enc(big)).decode("utf-8").splitlines()
check(len(out_lines) == REPORT_LINES, f"ровно {REPORT_LINES} строк в отчёте")
check(out_lines[0] == f"NEW-{REPORT_LINES - 1:04d}" and out_lines[-1] == "NEW-0000",
      "самые свежие записи на месте, в хронологическом порядке")
check("OLD-старт" not in out_lines and "NEW-4999" not in out_lines, "самые старые записи отсутствуют")

# 3. Пустой журнал.
check(pick_log_fragment(b"") == b"", "пустой журнал -> пустой фрагмент")

# 4. Unicode и очень длинные строки проходят без искажений.
uni = ["свежая запись ☃ é ё", "старая «цитата» \U0001f600"]
check(pick_log_fragment(enc(uni)) == enc(list(reversed(uni))), "unicode без искажений")
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
