"""CB-Radio.exe entry point (2026-11-05). The exe is a STABLE launcher; the radio's own code lives as plain .py
files in app/ next to it. Updates (updater.py) replace data and .py files only — never an exe — so antivirus
heuristics have nothing to object to («самообновляющийся exe» is a classic false-positive trigger).

Before the radio starts, the launcher applies an update staged by the previous run (update/staged + READY):
  - backs up every file it replaces to update/backup/, writes update/applied.json {"version", "ok": false};
  - the radio sets "ok": true after a minute of healthy work (updater.mark_ok);
  - if a freshly applied version did not reach "ok" twice in a row, the launcher puts the backup back.
This file is frozen into the exe and changes only with a full installer: keep it small and boring."""
import json
import os
import runpy
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
APP = ROOT / "app"
UPD = ROOT / "update"


def _log(msg):
    try:
        with open(UPD / "update.log", "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + msg + "\n")
    except OSError:
        pass


def _move(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    shutil.move(str(src), str(dst))


def apply_staged():
    st = UPD / "staged"
    if not (st / "READY").exists():
        return
    try:
        plan = json.loads((st / "plan.json").read_text(encoding="utf-8"))
        bak = UPD / "backup"
        if bak.exists():
            shutil.rmtree(bak)
        bak.mkdir(parents=True)
        for rel in plan.get("files", []) + plan.get("delete", []):
            cur = ROOT / rel
            if cur.exists():
                _move(cur, bak / rel)
        for rel in plan.get("files", []):
            _move(st / "files" / rel, ROOT / rel)
        (bak / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        (UPD / "applied.json").write_text(json.dumps({"version": plan.get("version"), "from": plan.get("from"),
                                                     "ok": False, "starts": 0}), encoding="utf-8")
        shutil.rmtree(st)
        _log(f"обновление {plan.get('from')} -> {plan.get('version')} установлено: {len(plan.get('files', []))} файлов, "
             f"удалено {len(plan.get('delete', []))}")
    except Exception as e:  # noqa: BLE001 — never block the radio
        _log(f"обновление не установилось: {e!r}")
        try:
            (st / "READY").unlink()
        except OSError:
            pass


def rollback_if_broken():
    a = UPD / "applied.json"
    try:
        info = json.loads(a.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if info.get("ok"):
        return
    info["starts"] = int(info.get("starts", 0)) + 1
    if info["starts"] <= 2:
        a.write_text(json.dumps(info), encoding="utf-8")
        return
    bak = UPD / "backup"                       # the new version never reached «ok»: put the old one back
    try:
        plan = json.loads((bak / "plan.json").read_text(encoding="utf-8"))
        for rel in plan.get("files", []):
            cur = ROOT / rel
            if cur.exists():
                cur.unlink()
        for f in bak.rglob("*"):
            if f.is_file() and f.name != "plan.json":
                _move(f, ROOT / f.relative_to(bak))
        a.unlink()
        _log(f"версия {info.get('version')} не запускалась нормально — возвращена {info.get('from')}")
    except Exception as e:  # noqa: BLE001
        _log(f"откат не удался: {e!r}")


if __name__ == "__main__":
    try:
        UPD.mkdir(exist_ok=True)
        rollback_if_broken()
        apply_staged()
    except Exception:  # noqa: BLE001
        pass
    sys.path.insert(0, str(APP))
    os.chdir(ROOT)
    runpy.run_path(str(APP / "cb_radio.py"), run_name="__main__")
