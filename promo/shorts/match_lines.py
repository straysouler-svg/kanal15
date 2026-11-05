"""Сверка распознанного текста записи с базой реплик рации (точные тексты для субтитров).
  python match_lines.py [от_сек] [до_сек]
Печатает: время, что услышал Whisper, лучшая реплика из базы (актёр, похожесть)."""
import difflib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DB = Path(r"G:\Claude\gruzovichki\cb-radio\phrases\level3_eleven.json")


def clean(t):
    t = re.sub(r"\[[^\]]*\]", "", t)          # acted tags [warmly]
    t = re.sub(r"\([^)]*\)", "", t)           # stage directions (смеётся)
    return re.sub(r"\s+", " ", t).strip(" .,")


def norm(t):
    return re.sub(r"[^а-яёa-z ]", "", clean(t).lower().replace("ё", "е"))


def corpus():
    d = json.loads(DB.read_text(encoding="utf-8"))
    out = []
    for k, a in d["actors"].items():
        for p in a.get("phrases", []):
            txt = p if isinstance(p, str) else p.get("text", "")
            out.append((k, txt))

    def walk(node):
        if isinstance(node, list):
            for x in node:
                if isinstance(x, dict) and "text" in x:
                    out.append((x.get("actor", ""), x["text"]))
                else:
                    walk(x)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
    walk(d.get("reactions", {}))
    walk(d.get("scenes", {}))
    return out


def best(heard, lines, actor=None):
    h = norm(heard)
    if len(h) < 6:
        return None
    pool = [x for x in lines if not actor or x[0] == actor] or lines
    scored = []
    for a, t in pool:
        n = norm(t)
        if not n:
            continue
        r = difflib.SequenceMatcher(None, h, n).ratio()
        # a short heard piece inside a long line: compare with the best window
        if len(n) > len(h) * 1.5:
            m = difflib.SequenceMatcher(None, n, h).find_longest_match(0, len(n), 0, len(h))
            r = max(r, m.size / len(h) * 0.9)
        scored.append((r, a, clean(t)))
    return max(scored) if scored else None


if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "transcript"     # work/<name>.json (video stem)
    t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 0
    t1 = float(sys.argv[3]) if len(sys.argv) > 3 else 1e9
    lines = corpus()
    tr = json.loads((HERE / "work" / f"{name}.json").read_text(encoding="utf-8"))
    for s in tr:
        if not (t0 <= s["start"] <= t1):
            continue
        b = best(s["text"], lines)
        tag = f"  => {b[1]} {b[0]:.2f}: {b[2]}" if b and b[0] >= 0.45 else ""
        print(f"{s['start']:7.1f}-{s['end']:6.1f} {s['text']}{tag}")
