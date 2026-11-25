# -*- coding: utf-8 -*-
"""RELEASE-PACK-1 (ревизия v1.41): загрузчик единого manifest runtime-модулей (runtime_modules.json).

Импортируют build/radio.spec, tools/build_exe.py, tools/pack_release.py и
tools/check_release_modules.py. Ручные списки модулей в этих файлах запрещены —
только отсюда, иначе contract-test краснеет.
"""
import json
from pathlib import Path

CB = Path(__file__).resolve().parents[1]
MANIFEST = CB / "runtime_modules.json"


def load():
    """-> (root_modules, tools_modules) — списки имён без .py."""
    d = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return list(d["root"]), list(d["tools"])
