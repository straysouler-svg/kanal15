"""CB-Radio.exe entry point (2026-11-05). The exe is a STABLE launcher; the radio's own code lives as plain .py
files in app/ next to it. Updates (updater.py) replace data and .py files only — never an exe — so antivirus
heuristics have nothing to object to («самообновляющийся exe» is a classic false-positive trigger).

Before the radio starts, the launcher applies an update staged by the previous run (update/staged + READY):
  - backs up every file it replaces to update/backup/ (plan.json goes there first: a matching backup on the
    next attempt means «retry after a partial apply» — keep it), writes update/applied.json {"version", "ok": false};
  - the radio sets "ok": true after a minute of healthy work (updater.mark_ok);
  - if a freshly applied version did not reach "ok" twice in a row, the launcher puts the backup back;
  - a failed apply KEEPS update/staged and retries the copy on the next start (3 attempts per file, a pause
    between them): antivirus or the indexer can hold a fresh blob for a moment (2026-11-08, Данилин лог).
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
    line = time.strftime("%Y-%m-%d %H:%M:%S ") + msg
    try:
        with open(UPD / "update.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    try:                                   # mirror into the main log: installs/rollbacks must be visible to the user
        with open(ROOT / "cb_radio.log", "a", encoding="utf-8") as f:
            f.write(time.strftime("%H:%M:%S ") + "лаунчер: " + msg + "\n")
    except OSError:
        pass


def _move(src, dst):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    shutil.move(str(src), str(dst))


def _apply_one(st, bak, rel, tries=3):
    """Backs up the current file and puts the staged one in place; None = ok. Retries with a pause —
    antivirus or the indexer can hold a fresh blob for a moment. A missing staging file means the file
    was already put in place by a previous attempt; a missing backup copy means it is already backed up."""
    cur, stage_f = ROOT / rel, st / "files" / rel
    last = None
    for _ in range(tries):
        try:
            if cur.exists() and not (bak / rel).exists():
                _move(cur, bak / rel)
            if stage_f.exists():
                _move(stage_f, cur)
            return None
        except OSError as e:
            last = e
            time.sleep(0.7)
    return last


def apply_staged():
    st = UPD / "staged"
    if not (st / "READY").exists():
        return
    try:
        plan = json.loads((st / "plan.json").read_text(encoding="utf-8"))
        bak = UPD / "backup"
        fresh = not (bak / "plan.json").exists() \
            or (bak / "plan.json").read_text(encoding="utf-8") != json.dumps(plan, ensure_ascii=False)
        if fresh and bak.exists():
            shutil.rmtree(bak)                 # a new update: the old backup is of no use for rolling it back
        bak.mkdir(parents=True, exist_ok=True)
        (bak / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
        bad = [rel for rel in list(plan.get("files", [])) + list(plan.get("delete", []))
               if _apply_one(st, bak, rel) is not None]
        if bad:
            raise OSError(f"не перенеслось (занято?): {', '.join(bad[:3])}")
        (UPD / "applied.json").write_text(json.dumps({"version": plan.get("version"), "from": plan.get("from"),
                                                     "ok": False, "starts": 0}), encoding="utf-8")
        shutil.rmtree(st)
        _log(f"обновление {plan.get('from')} -> {plan.get('version')} установлено: {len(plan.get('files', []))} файлов, "
             f"удалено {len(plan.get('delete', []))}")
    except Exception as e:  # noqa: BLE001 — never block the radio
        _log(f"обновление не установилось: {e!r} — повторю при следующем запуске")
        # READY stays: the next launch retries the copy, updater.check() won't re-download the same version


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
