"""Интеграция пакетов 1.33: first_air/who_asks, knows (+матрица), vityok-муд, iceland/memes. Удалить после."""
import json, re
from pathlib import Path

ROOT = Path(r"G:\Claude\gruzovichki\cb-radio")
PJ = ROOT / "phrases" / "level3_eleven.json"
PH = ROOT / "phrases"

FIX = {
    "[пауза]": "[pause]", "[смеётся]": "[laughs]", "[хихикает]": "[giggles]",
    "[тихо смеётся]": "[giggles]", "[сухо]": "[dry]", "[хитро]": "[playful]",
    "[тараторит]": "[fast]", "[тише]": "[quietly]", "[листает]": "[pause]",
    "[щелчок чёток]": "[pause]", "[щелчок зажигалки]": "[quietly]", "[гудок]": "[laughs]",
    "[кашляет]": "[clears throat]", "[медленно]": "[slowly]", "[щелчок]": "[pause]",
}
DROP_MARK = re.compile(r"\s*\[(мем — заменяемо|кино — вечное)\]\s*$")

def fix(t):
    for a, b in FIX.items():
        t = t.replace(a, b)
    return DROP_MARK.sub("", t).strip()

def quote_lines(txt, actor=None):
    """Строки-«цитаты» из секции (опционально только под одним актёром)."""
    out = []
    cur = actor
    for line in txt.splitlines():
        m = re.match(r"^(\w+) \(", line) or re.match(r"^### (\w+)", line) or re.match(r"^## (\w+)", line)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r"^- (?:\w+: )?«(.+)»$", line.strip()) or re.match(r"^  - «(.+)»$", line)
        if m and (actor is None or cur == actor):
            out.append(fix(m.group(1)))
    return out

d = json.loads(PJ.read_text(encoding="utf-8"))
R = d["reactions"]

# ---------- 1. first_air / who_asks ----------
t = (PH / "drafts_first_air_2026-11-08.md").read_text(encoding="utf-8")
fa, wa = {}, {}
cur = None
section = None
for line in t.splitlines():
    m = re.match(r"^## (\w+) \(", line)
    if m:
        cur = m.group(1); section = None; continue
    m = re.match(r"^\*\*(\w+):\*\*", line.strip())
    if m and cur:
        section = m.group(1); continue
    m = re.match(r"^- «(.+)»$", line.strip())
    if m and cur and section:
        (fa if section == "first_air" else wa).setdefault(cur, []).append({"actor": cur, "text": fix(m.group(1))})
R["first_air"] = {k: v for k, v in fa.items()}
R["who_asks"] = {k: v for k, v in wa.items()}
print("first_air:", sum(len(v) for v in fa.values()), "who_asks:", sum(len(v) for v in wa.values()))

# ---------- 2. knows + матрица ----------
t = (PH / "drafts_knows_actor_2026-11-08.md").read_text(encoding="utf-8")
kn = {}
cur = None
for line in t.splitlines():
    m = re.match(r"^## (\w+) \(", line)
    if m:
        cur = m.group(1); continue
    if line.startswith("## "):
        cur = None; continue                      # «Заметки», «Что проверить» — не актёры
    m = re.match(r"^- (\w+): «(.+)»\s*$", line.strip())
    if m and cur:
        tgt = m.group(1)
        kn.setdefault(cur, {})[tgt] = [{"actor": cur, "text": fix(m.group(2))}]
R["knows"] = kn
print("knows:", sum(len(v) for g in kn.values() for v in g.values()))

# матрица canon_relations -> map/actor_relations.json
t = (PH / "canon_relations_2026-11-08.md").read_text(encoding="utf-8")
KEY = {"Мих": "mihalych", "Стас": "stas", "Янек": "yanek", "Ласт": "lastochka", "Бор": "boroda",
       "Сор": "soroka", "Студ": "student", "Проф": "professor", "Петр": "petrovna", "Тень": "ten",
       "Витёк": "vitek", "Сова": "sova", "Палыч": "ment", "Кард": "kardan", "Лиса": "lisa",
       "Руст": "rustam", "Бахт": "bahti", "Вера": "vera"}
rels = {}
in_tab = False
for line in t.splitlines():
    if line.startswith("## Матрица"):
        in_tab = True; continue
    if in_tab:
        if not line.startswith("|"):
            if rels: break
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] in ("", "---") or cells[0].startswith("-"):
            continue
        row = KEY.get(cells[0])
        if not row: continue
        rels[row] = {}
        for i, c in enumerate(cells[1:], 1):
            col = list(KEY)[i - 1] if i - 1 < len(KEY) else None
            col_key = KEY.get(col)
            if col_key and c in ("Л", "Э"):
                rels[row][col_key] = c
(ROOT / "map" / "actor_relations.json").write_text(
    json.dumps(rels, ensure_ascii=False, indent=1), encoding="utf-8")
print("relations: рёбер", sum(len(v) for v in rels.values()))

# ---------- 3. Витёк-муд ----------
t = (PH / "drafts_vityok_mood_2026-11-08.md").read_text(encoding="utf-8")
# арка: секция «## 1.» до «## 2.», ступени 2-7
arc = []
sec1 = t.split("## 1.")[1].split("## 2.")[0]
for line in sec1.splitlines():
    m = re.match(r"^- (?:«)?(.+?)»?$", line.strip())
    if m and "«" in line:
        txt = re.search(r"«(.+)»", line).group(1)
        if "Ступень 1" in line or line.strip().startswith("- «Мальчики, я опаздываю"):
            continue                      # ступень 1 уже живёт в эфире
        arc.append({"actor": "vitek", "text": fix(txt)})
R.setdefault("quest", {})["vityok_wedding"] = arc
# спокойный Витёк
sec2 = t.split("## 2.")[1].split("## 3.")[0]
R["calm_vityok"] = [{"actor": "vitek", "text": x} for x in quote_lines(sec2, "vitek")]
# маркеры настроения
sec3 = t.split("## 3.")[1].split("## 4.")[0] if "## 4." in t else t.split("## 3.")[1].split("---")[0]
marks = {}
cur = None
for line in sec3.splitlines():
    m = re.match(r"^### (\w+)", line)
    if m:
        cur = m.group(1); continue
    m = re.match(r"^- (\w+): «(.+)»$", line.strip())
    if m and cur:
        marks.setdefault(m.group(1), []).append({"actor": cur, "text": fix(m.group(2))})
R["mood_mark"] = marks
# «успокойся»
sec4 = t.split("## 4.")[1] if "## 4." in t else ""
cd = {"yes": [], "no": []}
cur = None
for line in sec4.splitlines():
    m = re.match(r"^### (\w+)", line)
    if m:
        cur = m.group(1); continue
    m = re.match(r"^- (да|нет): «(.+)»$", line.strip())
    if m and cur:
        cd["yes" if m.group(1) == "да" else "no"].append({"actor": cur, "text": fix(m.group(2))})
R["calm_down"] = cd
print("арка:", len(arc), "calm_vityok:", len(R["calm_vityok"]),
      "mood_mark:", sum(len(v) for v in marks.values()), "calm_down:", sum(len(v) for v in cd.values()))

# ---------- 4. Исландия + мемы ----------
t = (PH / "drafts_iceland_memes_2026-11-09.md").read_text(encoding="utf-8")
route, dlc, mem = {}, [], []
sec = None
cur = None
sub = None
for line in t.splitlines():
    m = re.match(r"^# (.+)$", line.strip())
    if m:
        sec = m.group(1); cur = None; sub = None; continue
    m = re.match(r"^## (\S+)", line)
    if m:
        sub = m.group(1); cur = None; continue
    m = re.match(r"^(\w+):$", line.strip())
    if m:
        cur = m.group(1); continue
    q = re.search(r"«(.+?)»\s*$", line.strip())
    if not q:
        continue
    txt = DROP_MARK.sub("", q.group(1)).strip()
    if "ЗАДАНИЕ 1" in (sec or "") and (sub or "").startswith("1а") and cur:
        route.setdefault(cur, []).append({"actor": cur, "text": fix(txt)})
    elif "ЗАДАНИЕ 1" in (sec or "") and (sub or "").startswith("1б") and cur:
        dlc.append({"actor": cur, "text": fix(txt)})
    elif "ЗАДАНИЕ 2" in (sec or "") and cur:
        mem.append({"actor": cur, "text": fix(txt)})
# dlc не дублируем из отдельного сплита — уже собран выше
R["intent"].setdefault("route", [])
# route дополняет существующий intent/route, если пуст — создаёт
R["intent"]["route"] = [x for g in route.values() for x in g]
R["world"]["dlc_iceland"] = dlc
R["memes"] = {}
for ln in mem:
    R["memes"].setdefault(ln["actor"], []).append(ln)
print("route:", len(R["intent"]["route"]), "dlc:", len(dlc), "memes:", len(mem))

PJ.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
bad = [g for g, ks in R.items() if g in ("first_air", "who_asks", "knows", "quest", "calm_vityok", "mood_mark", "calm_down", "memes")]
print("группы готовы:", bad)
