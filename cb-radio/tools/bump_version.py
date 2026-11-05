"""Новая версия «Канала 15»: +0.01 к номеру, сегодняшняя дата, запись в CHANGELOG.md.
    python tools/bump_version.py "что изменилось" ["ещё пункт" ...]
Потом пересобрать установщики (pack_release + build_exe): номер попадёт в имя файла, значок в трее,
«Программы и компоненты» и окно установщика."""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VF, CL = ROOT / "version.json", ROOT / "CHANGELOG.md"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    notes = sys.argv[1:]
    if not notes:
        raise SystemExit('укажи, что изменилось: bump_version.py "пункт" ["пункт" ...]')
    v = json.loads(VF.read_text(encoding="utf-8"))
    new = f"{float(v['version']) + 0.01:.2f}"
    today = date.today()
    VF.write_text(json.dumps({"version": new, "date": today.isoformat()}, ensure_ascii=False, indent=2) + "\n",
                  encoding="utf-8")
    text = CL.read_text(encoding="utf-8")
    entry = f"## {new} — {today:%d.%m.%Y}\n" + "".join(f"- {n}\n" for n in notes) + "\n"
    i = text.index("\n## ") + 1
    CL.write_text(text[:i] + entry + text[i:], encoding="utf-8")
    print(f"версия {v['version']} -> {new} ({today:%d.%m.%Y})")


if __name__ == "__main__":
    main()
