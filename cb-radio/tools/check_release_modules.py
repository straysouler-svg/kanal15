# -*- coding: utf-8 -*-
"""RELEASE-PACK-1 (ревизия v1.41): contract-test «все модули, импортированные в рантайме, есть в поставке».

Проверки:
1. runtime_modules.json валиден; каждый заявленный модуль существует на диске (cb-radio/<m>.py,
   cb-radio/tools/<m>.py).
2. Статический разбор entry-point'ов (cb_radio.py, launcher.py) + транзитивный обход локальных
   импортов: любой импортированный локальный модуль ОБЯЗАН быть в manifest. Ловит протечки
   вида convoy/horn/streampeek/voicedsp/transport/cab — раньше бандлились молча или терялись.
3. Три потребителя (build/radio.spec, tools/build_exe.py, tools/pack_release.py) не содержат
   ручных списков модулей — читают manifest через tools/release_manifest.py (поиск устаревших
   литералов-имён модулей).

Запуск из корня воркспейса:  py -3 cb-radio/tools/check_release_modules.py
Вердикт одной строкой, код возврата 0/1 (урок 6).
"""
import ast
import sys
from pathlib import Path

CB = Path(__file__).resolve().parents[1]
WS = CB.parent

sys.path.insert(0, str(CB / "tools"))
import release_manifest  # noqa: E402


def local_imports(path):
    """Имена локальных модулей, импортируемых файлом (import x / from x import ...), без пакетов."""
    out = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out.add(node.module.split(".")[0])
    return out


def main():
    root_mods, tools_mods = release_manifest.load()
    local_names = set(root_mods) | set(tools_mods)
    problems = []

    # 1) заявленные модули существуют
    for m in root_mods:
        if not (CB / f"{m}.py").exists():
            problems.append(f"manifest: корневой модуль {m}.py отсутствует в cb-radio/")
    for m in tools_mods:
        if not (CB / "tools" / f"{m}.py").exists():
            problems.append(f"manifest: tools-модуль {m}.py отсутствует в cb-radio/tools/")

    # 2) транзитивный обход локальных импортов от entry-point'ов
    seen, stack = set(), ["cb_radio", "launcher"]
    while stack:
        m = stack.pop()
        if m in seen or m not in local_names:
            continue
        seen.add(m)
        p = CB / f"{m}.py" if m in root_mods else CB / "tools" / f"{m}.py"
        for dep in local_imports(p):
            if dep in local_names and dep not in seen:
                stack.append(dep)
            elif dep not in local_names and dep not in sys.stdlib_module_names \
                    and (CB / f"{dep}.py").exists():
                problems.append(f"импорт {dep} в {m}.py — локальный файл есть, а в manifest его нет")
    # tools-модули тоже сканируем (их импортирует cb_radio/company)
    for m in tools_mods:
        for dep in local_imports(CB / "tools" / f"{m}.py"):
            if (CB / f"{dep}.py").exists() and dep not in local_names:
                problems.append(f"tools/{m}.py импортирует {dep} — локальный файл есть, а в manifest нет")

    # 3) потребители без ручных списков
    consumers = {
        "build/radio.spec": WS / "build" / "radio.spec",
        "tools/build_exe.py": CB / "tools" / "build_exe.py",
        "tools/pack_release.py": CB / "tools" / "pack_release.py",
    }
    for name, path in consumers.items():
        text = path.read_text(encoding="utf-8")
        if "release_manifest" not in text:
            problems.append(f"{name} не читает manifest (release_manifest) — ручной список?")

    if problems:
        print("РАСХОЖДЕНИЯ МОДУЛЕЙ ПОСТАВКИ:")
        for p in problems:
            print("  -", p)
        print("ЧИСТО" if False else "СТОП: правь manifest/код и перезапусти")
        return 1
    print(f"Чисто: {len(root_mods)} корневых + {len(tools_mods)} tools-модулей, "
          f"транзитивно проверено {len(seen)}; потребители синхронизированы")
    return 0


if __name__ == "__main__":
    sys.exit(main())
