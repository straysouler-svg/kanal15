#!/usr/bin/env python3
"""Проверка приватности перед git push: ищет запретные слова (build/privacy_forbidden.txt)
во ВСЕХ коммитах, которые уйдут в origin/main, а не только в последнем.
Код возврата 0 — чисто, 1 — есть находки. Запуск из корня репозитория:
    python tools/check_privacy.py
"""
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LIST = os.path.join(ROOT, "build", "privacy_forbidden.txt")
ALLOW = os.path.join(ROOT, "build", "privacy_allow.txt")


def main():
    if not os.path.exists(LIST):
        print(f"НЕТ СПИСКА: {LIST} — проверка невозможна, push ОТМЕНИТЬ")
        return 1
    words = [w.strip() for w in io.open(LIST, encoding="utf-8") if w.strip() and not w.startswith("#")]
    allow = []
    if os.path.exists(ALLOW):
        allow = [w.strip().lower() for w in io.open(ALLOW, encoding="utf-8") if w.strip() and not w.startswith("#")]
    diff = subprocess.run(
        ["git", "log", "origin/main..main", "-p", "--", "."],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    if not diff:
        print("Нет неопубликованных коммитов — проверять нечего.")
        return 0
    hits = []
    for i, line in enumerate(diff.splitlines(), 1):
        if not line.startswith("+"):
            continue  # смотрим только добавленное
        low = line.lower()
        if any(a in low for a in allow):
            continue  # разобранное ложное срабатывание (build/privacy_allow.txt)
        for w in words:
            if w.lower() in low:
                hits.append((i, w, line.strip()[:120]))
                break
    if hits:
        print(f"НАЙДЕНО {len(hits)} подозрительных строк в отправляемых коммитах:")
        for i, w, line in hits:
            print(f"  строка {i} [{w}]: {line}")
        print("Push ОТМЕНИТЬ до разбора каждой строки.")
        return 1
    print("Чисто: запретных слов в отправляемых коммитах нет.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
    sys.exit(main())
