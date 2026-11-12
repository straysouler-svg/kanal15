"""2026-11-04: lines that call the player «Железяка» get two more versions (fields on the line):
  v_kirill  - for friend Кирилл (handle «СидиПосиди»): Кирилл / Кириллушка / Кирюха / Сиди-Посиди by character
  v_alive   - for blogger TheAlive55 (Алексей): Алёша / Лёха / Алексей / «Пятьдесят пятый» by character
  v_neutral - no name at all (public release)
Audio goes to audio/variants/<variant>/<same path> (tools/gen_variants.py); the radio picks it by config "variant".
Сорока is personal (Tatiana's voice) and is never part of a shared build -> skipped here."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "phrases" / "level3_eleven.json"
HANDLE = "Сиди-Посиди"          # written with a hyphen so TTS stresses both halves: сиди́-посиди́

# how each character calls Кирилл: (form, weight)
FORMS = {
    "mihalych": [("Кирюха", 3), (HANDLE, 1)], "stas": [("Кирюха", 3), (HANDLE, 1)], "yanek": [("Кирилл", 3), (HANDLE, 1)],
    "lastochka": [("Кирилл", 2), (HANDLE, 1)], "boroda": [("Кирюха", 2), (HANDLE, 1)], "student": [("Кирилл", 3), (HANDLE, 1)],
    "professor": [("Кирилл", 3), (HANDLE, 1)], "petrovna": [("Кириллушка", 1)], "sova": [("Кириллушка", 1)],
    "ten": [(HANDLE, 2), ("Кирилл", 1)], "vitek": [("Кирюха", 3), (HANDLE, 1)], "ment": [(HANDLE, 2), ("Кирилл", 1)],
    "kardan": [("Кирюха", 2), (HANDLE, 1)], "lisa": [(HANDLE, 2), ("Кирюха", 1)],
    "rustam": [("Кирилл", 3), (HANDLE, 1)], "bahti": [("Кирюха", 2), (HANDLE, 1)], "vera": [("Кирилл", 2), (HANDLE, 1)],
}
# lines where the handle (not the name) is the only right choice: radio calls and "знакомый позывной"
FORCE_HANDLE = {"scenes/zhelezyaka/01", "reactions/player/greet/19", "reactions/player/greet/35"}

# personal builds for bloggers (2026-11-06): same scheme as Кирилл. key -> handle, forms per actor, other cases
ALIVE = "Пятьдесят пятый"             # TheAlive55 (Алексей): radio-style call sign from his «55»
PERSONAL = {
    "kirill": {"handle": HANDLE, "forms": FORMS,
               "cases": {"Железякой": "Кириллом", "Железяке": "Кириллу"}},
    "alive": {"handle": ALIVE,
              "forms": {"mihalych": [("Алёша", 3), (ALIVE, 1)], "petrovna": [("Алёшенька", 1)],
                        "sova": [("Алёшенька", 2), ("Алёша", 1)],
                        "boroda": [("Лёха", 3), (ALIVE, 1)], "stas": [("Лёха", 3), (ALIVE, 1)],
                        "kardan": [("Лёха", 2), (ALIVE, 1)], "bahti": [("Лёха", 2), (ALIVE, 1)],
                        "vitek": [("Лёха", 2), (ALIVE, 1)],
                        "ment": [(ALIVE, 2), ("Алексей", 1)], "ten": [(ALIVE, 2), ("Алексей", 1)],
                        "vera": [(ALIVE, 2), ("Алексей", 1)],
                        "yanek": [("Алексей", 3), (ALIVE, 1)], "lastochka": [("Алёша", 2), (ALIVE, 1)],
                        "student": [("Алексей", 3), (ALIVE, 1)], "professor": [("Алексей", 3), (ALIVE, 1)],
                        "lisa": [(ALIVE, 2), ("Лёха", 1)], "rustam": [("Алексей", 3), (ALIVE, 1)]},
              "cases": {"Железякой": "Лёхой", "Железяке": "Лёхе"}},
}

# neutral: the name is the subject of the sentence -> rewrite by hand
NEUTRAL = {
    "scenes/zhelezyaka/01": "[calling out] На канале, есть кто живой? Ответьте Михалычу. Приём.",
    "reactions/player/greet/18": "О, кто-то в эфире! Э-э... как дела?",
    "reactions/player/greet/20": "Добрый день, коллега. Как ваш рейс?",
    "reactions/player/greet/39": "Новый голос в эфире! Ночь становится лучше!",
    "reactions/world/meet_again/09": "Опять ты? Ты что, за мной ездишь? (смеётся)",
    "reactions/player/greet/25": "...Здравствуй.",
    "reactions/player/greet/27": "(пауза) Я так и думал, что ты появишься.",
    "reactions/player/greet/07": "Ой! Привет! (смущённо) А ты... давно ездишь? Я вот первый раз.",
    "reactions/player/greet/10": "(тихо) ...Слышу тебя. Тоже не спишь, значит.",
    "reactions/player/greet/41": "Ну здравствуй, здравствуй.",
    "reactions/player/greet/53": "А я думаю, кто это так громко дышит в эфир. (смеётся)",
    "reactions/player/greet/46": "А, вот и вы! Как раз о вас вспоминал, коллега.",
    "reactions/player/greet/58": "[excited] О, новый голос в эфире! Респект, бро. Стасян на связи.",
    "reactions/player/greet/68": "[loud] Новенький на канале! Ну всё, теперь веселее.",
    "reactions/player/greet/70": "[warmly] О, дорогой! Ассалому алейкум. Самарканд слышит.",
}


def pick_form(actor, path, who="kirill"):
    spec = PERSONAL[who]
    if path in FORCE_HANDLE:
        return spec["handle"]
    forms = spec["forms"][actor]
    total = sum(w for _, w in forms)
    h = int(hashlib.md5(path.encode()).hexdigest(), 16) % total
    for f, w in forms:
        if h < w:
            return f
        h -= w
    return forms[0][0]


def neutral(text):
    t = text
    t = re.sub(r",\s*Железяка(?=[.!?,])", "", t)                 # "Привет, Железяка!" -> "Привет!"
    t = re.sub(r"Железяка,\s*", "", t)                           # "Железяка, здорово!" -> "здорово!"
    t = re.sub(r"Железяка[.!]\s*", "", t)                        # "О, Железяка! ..." -> "О, ..."
    t = re.sub(r"\s+Железяка(?=[.!?])", "", t)
    t = t.replace("рядом с Железякой", "рядом").replace("Железяке помочь", "человеку помочь")   # other cases
    t = re.sub(r"(^|[.!?]\s+|\]\s+|\)\s+)([а-яё])", lambda m: m.group(1) + m.group(2).upper(), t)
    t = re.sub(r"О,\s+([А-ЯЁ])", lambda m: "О! " + m.group(1), t)
    return re.sub(r"\s{2,}", " ", t).strip()


def main():
    d = json.loads(F.read_text(encoding="utf-8"))
    rows = []

    def handle_line(path, ln):
        if "Железяк" not in ln["text"] or ln["actor"] == "soroka":
            return
        for who, spec in PERSONAL.items():
            t = ln["text"]
            for case, form in spec["cases"].items():
                t = t.replace(case, form)
            ln[f"v_{who}"] = t.replace("Железяка", pick_form(ln["actor"], path, who))
        # 12.11: ручной вариант из gaps_neutral (уже в json) важнее авто-генерации — не затираем
        ln["v_neutral"] = ln.get("v_neutral") or NEUTRAL.get(path) or neutral(ln["text"])
        rows.append((path, ln["actor"], ln["v_alive"], ln["v_neutral"]))

    for sid, ls in d["scenes"].items():
        for i, ln in enumerate(ls, 1):
            handle_line(f"scenes/{sid}/{i:02d}", ln)
    for g, ks in d["reactions"].items():
        if g.startswith("_"):
            continue
        for k, ls in ks.items():
            if k.startswith("_"):
                continue
            for i, ln in enumerate(ls, 1):
                handle_line(f"reactions/{g}/{k}/{i:02d}", ln)
    src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
    ns = {"json": json}
    exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
    F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
    for p, a, k, n in rows:
        print(f"{p:34} {a:9}\n    К: {k}\n    Н: {n}")
    print(len(rows), "реплик")


if __name__ == "__main__":
    main()
