"""Фрагмент cb_radio.log для диагностического отчёта (2026-11-19, промт stabilizaciya_2026-11-19, P0-3).

Журнал на диске пишется newest-first (_flush_log в cb_radio.py): свежие записи — первые физические
строки файла. Поэтому для отчёта берём ПЕРВЫЕ REPORT_LINES строк (а не splitlines()[-4000:] — тот
вариант отбрасывал свежие записи и оставлял самые старые) и переворачиваем их в хронологический
порядок, чтобы отчёт было удобно читать. Чистый модуль без зависимостей рации — покрыт тестами
tools/test_report_log.py. Вся система логирования не меняется."""
import re

REPORT_LINES = 4000
_HIDE_RX = re.compile(r"«[^»]*»")


def pick_log_fragment(data, hide_speech=False):
    """-> bytes: до REPORT_LINES самых свежих строк журнала в хронологическом порядке.
    hide_speech: фразы игрока в строках «тангента: «…»» заменены на «(скрыто)» — радио не отправляет
    слова игрока без его явного согласия."""
    lines = data.decode("utf-8", "replace").splitlines()[:REPORT_LINES]
    lines.reverse()                                     # newest-first -> хронологический порядок
    if hide_speech:
        lines = [_HIDE_RX.sub("«(скрыто)»", ln) if "тангента" in ln and "«" in ln else ln
                 for ln in lines]
    return "\n".join(lines).encode("utf-8")
