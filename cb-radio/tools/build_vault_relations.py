"""Граф знакомств → Obsidian vault (2026-11-11, по слову пользователя «выставить все связи, чтобы не перепутать»).

Источники правды:
  map/actor_relations.json            — матрица Л/Э (Л — лично, Э — заочно по эфиру)
  phrases/canon_relations_2026-11-08.md — описания пар («что связывает»)

Делает:
  1) vault/Канон/Граф знакомств.md  — легенда, матрица, все пары с описаниями и вики-ссылками;
  2) в каждую заметку vault/Персонажи/<Имя>.md дописывает/заменяет секцию «## Связи».

Запуск: ../build/venv/Scripts/python.exe -X utf8 tools/build_vault_relations.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VAULT = ROOT.parent / "vault"
PERS = VAULT / "Персонажи"

ORDER = ["mihalych", "stas", "yanek", "lastochka", "boroda", "soroka", "student", "professor", "petrovna",
         "ten", "vitek", "sova", "ment", "kardan", "lisa", "rustam", "bahti", "vera"]
RU = {"mihalych": "Михалыч", "stas": "Стас", "yanek": "Янек", "lastochka": "Ласточка", "boroda": "Борода",
      "soroka": "Сорока", "student": "Студент", "professor": "Профессор", "petrovna": "Петровна", "ten": "Тень",
      "vitek": "Витёк", "sova": "Сова", "ment": "Палыч", "kardan": "Кардан", "lisa": "Лиса", "rustam": "Рустам",
      "bahti": "Бахтияр", "vera": "Вера"}
SHORT = {"mihalych": "Мих", "stas": "Стас", "yanek": "Янек", "lastochka": "Ласт", "boroda": "Бор", "soroka": "Сор",
         "student": "Студ", "professor": "Проф", "petrovna": "Петр", "ten": "Тень", "vitek": "Витёк", "sova": "Сова",
         "ment": "Палыч", "kardan": "Кард", "lisa": "Лиса", "rustam": "Руст", "bahti": "Бахт", "vera": "Вера"}


def load_descriptions():
    """«**А–Б:** текст» из канон-md -> {(А, Б): текст}. Собирает и много-парные строки («А–Б, А–В:** ...»)."""
    desc = {}
    for line in (ROOT / "phrases" / "canon_relations_2026-11-08.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"- \*\*(.+?):\*\*\s*(.+)", line)
        if not m:
            continue
        pairs, text = m.group(1), m.group(2).strip()
        for pair in pairs.split(","):
            pair = pair.strip()
            if "–" not in pair:
                continue
            a, b = (p.strip() for p in pair.split("–", 1))
            if a in RU.values() and b in RU.values():
                desc[frozenset((a, b))] = text
    return desc


def main():
    rel = json.loads((ROOT / "map" / "actor_relations.json").read_text(encoding="utf-8"))
    desc = load_descriptions()

    def pair_line(a, b, mark):
        d = desc.get(frozenset((RU[a], RU[b])))
        return f"- **[[{RU[a]}]]–[[{RU[b]}]]** ({mark})" + (f": {d}" if d else "")

    # --- 1) сводная заметка
    head = "| | " + " | ".join(SHORT[k] for k in ORDER) + " |"
    sep = "|" + "---|" * (len(ORDER) + 1)
    rows = []
    for a in ORDER:
        row = [f"**{RU[a]}**"]
        for b in ORDER:
            row.append("—" if a == b else rel.get(a, {}).get(b, "—"))
        rows.append("| " + " | ".join(row) + " |")
    matrix = "\n".join([head, sep] + rows)

    l_pairs, e_pairs, none_pairs = [], [], []
    for i, a in enumerate(ORDER):
        for b in ORDER[i + 1:]:
            mark = rel.get(a, {}).get(b)
            if mark == "Л":
                l_pairs.append(pair_line(a, b, "Л"))
            elif mark == "Э":
                e_pairs.append(pair_line(a, b, "Э"))
            else:
                none_pairs.append(f"[[{RU[a]}]]–[[{RU[b]}]]")

    note = f"""---
tags: [канон]
обновлено: 2026-11-11
---

# Граф знакомств

Источник правды: `cb-radio/map/actor_relations.json` + `cb-radio/phrases/canon_relations_2026-11-08.md`.
Эта заметка генерируется скриптом `cb-radio/tools/build_vault_relations.py` — править источники, потом перегенерировать.

- **Л** — знакомы лично (стоянки, заправки, рыбалка). Сценки строим только по этим рёбрам.
- **Э** — знакомы заочно по эфиру (слышали голоса на 15-м, лично не встречались).
- **—** — чужие.

Правило мира: все слышат один канал, но «знать» — это голос + встреча. «Да и то не все».

## Матрица

{matrix}

## Личные знакомства (Л) — {len(l_pairs)} пар

{chr(10).join(l_pairs)}

## Заочные (Э) — {len(e_pairs)} пар

{chr(10).join(e_pairs)}

## Чужие (—) — {len(none_pairs)} пар

{", ".join(none_pairs)}

## Вехи и правила

- Инцидент «Ласточка не знает Бороду» закрыт: пара **Л**, сценок пять, реплика знакомства обязательна.
- [[Сорока]] — изолированный узел (решение 2026-11-04 «отношения не выстраиваем»); её «чужие»-ответы добрые, не обиженные.
- Ночная смена ([[Тень]], [[Сова]], [[Палыч]], [[Кардан]], [[Лиса]]) и дневная почти не знают друг друга лично.
- Связанные механики: интент «ты знаешь X?» (knows, 1.33), [[Взаимные арки]].
"""
    (VAULT / "Канон" / "Граф знакомств.md").write_text(note, encoding="utf-8")

    # --- 2) секция «## Связи» в каждую заметку персонажа
    for a in ORDER:
        mine = rel.get(a, {})
        l_list = [(b, desc.get(frozenset((RU[a], RU[b])))) for b in ORDER if mine.get(b) == "Л"]
        e_list = [b for b in ORDER if mine.get(b) == "Э"]
        lines = ["## Связи", "",
                 f"Граф знакомств: [[Граф знакомств]]. Л — лично, Э — заочно по эфиру.", ""]
        if l_list:
            lines.append("**Лично (Л):**")
            for b, d in l_list:
                lines.append(f"- [[{RU[b]}]]" + (f" — {d}" if d else ""))
            lines.append("")
        if e_list:
            lines.append("**Заочно по эфиру (Э):** " + ", ".join(f"[[{RU[b]}]]" for b in e_list))
            lines.append("")
        alone = [b for b in ORDER if b != a and b not in mine]
        if alone:
            lines.append("**Чужие (—):** " + ", ".join(f"[[{RU[b]}]]" for b in alone))
            lines.append("")
        section = "\n".join(lines).rstrip() + "\n"

        path = PERS / f"{RU[a]}.md"
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"\n?## Связи\n.*?(?=\n## |\Z)", "\n", text, flags=re.S)   # старую секцию убрать
        text = text.rstrip() + "\n\n" + section
        path.write_text(text, encoding="utf-8")

    print(f"готово: граф ({len(l_pairs)} Л, {len(e_pairs)} Э, {len(none_pairs)} чужих), секции в {len(ORDER)} заметках")


if __name__ == "__main__":
    main()
