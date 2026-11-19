"""Формирование build/report_upload_key.txt для pack_release (P0-4, промт stabilizaciya_2026-11-19).

pack_release прерывает сборку, если build/report_upload_key.txt отсутствует или в нём
меньше двух строк (access key id + secret сервисного аккаунта kanal15-reporter, upload-only).

Источник ключа — тот же, что читает _report_key() в cb_radio.py:
  1. тайник phrases/x.dat (собранная копия, поле «rk» — туда его кладёт pack_release);
  2. иначе report_key.txt рядом с рацией (дерево разработчика).

Секрет НИГДЕ не печатается: stdout получает только факт записи и размер.
Файл вне git (паттерн *key*.txt в .gitignore) — проверено через git check-ignore.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # cb-radio/
OUT = ROOT.parent / "build" / "report_upload_key.txt"


def _rk_from_tainik():
    x = ROOT / "phrases" / "x.dat"
    if not x.exists():
        return None
    try:
        sys.path.insert(0, str(ROOT))
        import tainik
        rk = (tainik.decode(x.read_bytes()) or {}).get("rk")
        return [str(s).strip() for s in rk if str(s).strip()] if rk else None
    except Exception:
        return None


def _rk_from_file():
    try:
        ls = [s.strip() for s in (ROOT / "report_key.txt").read_text(encoding="utf-8-sig").splitlines()
              if s.strip()]
    except OSError:
        return None
    return ls or None


def main():
    lines = _rk_from_tainik() or _rk_from_file()
    if not lines or len(lines) < 2:
        raise SystemExit("Ключ отправки отчётов не найден: ни в phrases/x.dat (rk), ни в "
                         f"{ROOT / 'report_key.txt'} (нужно две строки: access key id и secret).")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = "\n".join(lines[:2]) + "\n"
    OUT.write_text(data, encoding="utf-8")
    print(f"{OUT}: записано, {len(data.encode('utf-8'))} байт (секрет не печатается)")


if __name__ == "__main__":
    main()
