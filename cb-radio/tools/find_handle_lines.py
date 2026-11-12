"""Реестр именных обращений (12.11): все строки с «Железяка/Железяку/Железяке/Железякой» в эфире.
Нужен для платных ИМЕННЫХ версий: озвучиваем только строки из реестра, не выискивая по коду.

Запуск: venv-python tools/find_handle_lines.py
Пишет: phrases/handle_lines.json (машинный реестр) + печатает сводку.
Поля записи: rel (путь аудио без расширения), actor, text, variants (какие v_* есть в тексте),
voiced (для каких сборок уже есть озвученный вариант в audio/variants/<build>/<rel>.wav).
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "audio"
HANDLE_RE = re.compile("Железяк", re.IGNORECASE)
BUILDS = ("neutral", "kirill", "alive")


def actor_of(idx_file, i):
    try:
        return json.loads(idx_file.read_text(encoding="utf-8"))["actors"][i - 1]
    except Exception:
        return "?"


def main():
    d = json.loads((ROOT / "phrases" / "level3_eleven.json").read_text(encoding="utf-8"))
    rows = []

    def add(rel, actor, ln):
        t = ln if isinstance(ln, str) else ln.get("text", "")
        if not HANDLE_RE.search(t):
            return
        rows.append({
            "rel": rel,
            "actor": actor,
            "text": t,
            "variants": [k for k in ("v_neutral", "v_kirill", "v_alive") if isinstance(ln, dict) and k in ln],
            "voiced": [b for b in BUILDS if (A / "variants" / b / (rel + ".wav")).exists()],
        })

    for name, a in d["actors"].items():
        for i, ln in enumerate(a.get("phrases", []), 1):
            add(f"level3/{name}/{i:02d}", name, ln)
    for sid, ls in d["scenes"].items():
        for i, ln in enumerate(ls, 1):
            add(f"scenes/{sid}/{i:02d}", actor_of(A / "scenes" / sid / "scene.json", i), ln)
    for g, ks in d["reactions"].items():
        if g.startswith("_"):
            continue
        for k, ls in ks.items():
            if k.startswith("_"):
                continue
            for i, ln in enumerate(ls, 1):
                add(f"reactions/{g}/{k}/{i:02d}", actor_of(A / "reactions" / g / k / "index.json", i), ln)

    out = ROOT / "phrases" / "handle_lines.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    no_variant = [r for r in rows if not r["variants"]]
    print(f"всего строк с «Железяка»: {len(rows)} -> {out.name}")
    print(f"  с текстом-вариантом в json: {len(rows) - len(no_variant)}")
    print(f"  озвучено: neutral {sum('neutral' in r['voiced'] for r in rows)},"
          f" kirill {sum('kirill' in r['voiced'] for r in rows)},"
          f" alive {sum('alive' in r['voiced'] for r in rows)}")
    print(f"  без всякого варианта: {len(no_variant)} (см. gaps_neutral_2026-11-12.md)")


if __name__ == "__main__":
    main()
