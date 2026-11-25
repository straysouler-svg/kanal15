"""Атомарное хранение JSON-состояния рации (P1-8, промт stabilizaciya_2026-11-19).

Проблема: world_state.json / bonds.json / hazards.json писались напрямую
write_text(). Аварийное завершение посреди записи оставляло обрезанный
JSON, и прогресс тихо обнулялся (load ловил ValueError и начинал с нуля).

Контракт:
- save_json: временный файл в ТОМ ЖЕ каталоге -> flush + os.fsync ->
  os.replace. Старая валидная копия сохраняется как <имя>.bak.
- load_json: читает основной файл; при повреждении (OSError/ValueError) ИЛИ
  отсутствии основного файла (при живом .bak) пробует .bak и пишет ПОНЯТНУЮ
  диагностику — не молчаливое обнуление. Нет ни файла, ни backup — тихий None
  (первый запуск). Возвращает None, если валидных данных нет нигде.
"""
import json
import os
import sys
import tempfile
from pathlib import Path


def _default_log(msg):
    print(msg, file=sys.stderr)


def save_json(path, obj, *, log=_default_log, indent=None):
    """Атомарно записать obj в path (json, utf-8). Старое содержимое уходит в path.bak."""
    path = Path(path)
    data = json.dumps(obj, ensure_ascii=False, indent=indent).encode("utf-8")
    bak = path.with_name(path.name + ".bak")
    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        if path.exists():
            os.replace(path, bak)          # прежняя валидная копия
        os.replace(tmp_name, path)
    except OSError as e:
        try:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)
        except OSError:
            pass
        log(f"json_store: не смог сохранить {path.name}: {e!r} (прежнее состояние в {bak.name})")
        raise


def load_json(path, *, log=_default_log):
    """Прочитать JSON из path. При повреждении основного файла восстановить из .bak.
    -> объект или None (нет валидных данных ни в основном, ни в backup)."""
    path = Path(path)
    bak = path.with_name(path.name + ".bak")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        # 25.11 (STATE-1, ревизия v1.41): основного файла нет (удалён/переименован) — backup
        # читался ТОЛЬКО при повреждении, при отсутствии — тихое обнуление. Если backup есть —
        # читаем его с диагностикой; если нет ни того ни другого (первый запуск) — тишина.
        if not bak.exists():
            return None
        log(f"json_store: {path.name} не найден — восстанавливаю из {bak.name}")
    except (OSError, ValueError) as e:
        log(f"json_store: {path.name} повреждён ({e!r}) — пробую {bak.name}")
    try:
        obj = json.loads(bak.read_text(encoding="utf-8"))
    except FileNotFoundError:
        log(f"json_store: {path.name} повреждён и backup отсутствует — состояние начнётся с нуля")
        return None
    except (OSError, ValueError) as e:
        log(f"json_store: и backup {bak.name} недоступен ({e!r}) — состояние начнётся с нуля")
        return None
    log(f"json_store: {path.name} восстановлен из {bak.name}")
    return obj
