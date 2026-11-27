#!/usr/bin/env python3
"""Офлайн-линтер черновиков Глашатая (0 токенов): ловит запреты, 3-е лицо и утечки."""

import re
import sys
from pathlib import Path

FORBIDDEN_PATTERNS = [
    (r"\b(?:rutube|рутуб)\b", "Упоминание запрещённой платформы RUTUBE"),
    (r"\bбратишк[аиуео]\w*\b", "Запрещённое обращение «братишки» (используй «Господа и дамы» или «братва»)"),
    (
        r"\bДмитрий\s+(?:сделал|выпустил|поднял|написал|запустил|решил|починил|добавил|настроил)\b",
        "Третье лицо об авторе (писать ТОЛЬКО от первого лица: «я сделал»)",
    ),
    (
        r"\bкоманда\s+(?:сделала|выпустила|подготовила|запустила|починила)\b",
        "Упоминание «команды» от третьего лица (писать от первого лица)",
    ),
    (
        r"\bбыло\s+(?:выпущено|сделано|реализовано|исправлено|запущено)\b",
        "Безличный пресс-релизный оборот (переписать от первого лица автора)",
    ),
    (
        r"\d[\d\s.,]*\s*(?:руб\.?|₽|\$|usd|доллар\w*|донат\w*\s+на\s+сумму)\b",
        "Возможная утечка сумм/доходов/донатов в публичный текст",
    ),
    (
        r"(?:api[_-]?key|secret|token|personal_local|vpn_notes|vault/)",
        "Упоминание внутренних путей/секретов",
    ),
]


def lint_file(path: Path) -> int:
    if not path.exists():
        print(f"ERROR: Файл не найден: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    errors = []

    if "## Сверить перед публикацией" not in text:
        errors.append("Отсутствует обязательный блок «## Сверить перед публикацией» в конце файла.")

    body = text.split("## Сверить перед публикацией")[0]
    for lineno, line in enumerate(body.splitlines(), start=1):
        for pattern, reason in FORBIDDEN_PATTERNS:
            for match in re.finditer(pattern, line, flags=re.IGNORECASE):
                errors.append(f"Строка {lineno}: {reason} -> «{match.group(0)}»")

    if errors:
        print(f"FAIL ({len(errors)} нарушений в {path}):")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(f"OK: Черновик {path} прошёл базовый фильтр.")
    return 0


def main() -> int:
    if len(sys.argv) != 2:
        print("Использование: python cb-radio/tools/lint_promo.py <путь_к_черновику.md>", file=sys.stderr)
        return 2
    return lint_file(Path(sys.argv[1]))


if __name__ == "__main__":
    sys.exit(main())