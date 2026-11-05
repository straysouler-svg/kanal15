"""One-off: answers to "на чём едешь?" (reactions.intent.truck) and to "кто в эфире?" (reactions.world.rollcall)
for the gpt-audio drivers + Сорока. Appends only."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))
L = lambda a, t: {"actor": a, "text": t}  # noqa: E731
truck = [
    L("student", "Я на MAN TGX еду. Новенький, с завода. Ну, почти."),
    L("professor", "Я на DAF XF, коллега. Надёжная машина, как немецкая грамматика."),
    L("petrovna", "На Вольво я, сынок. В кабине цветы, а в прицепе тоже цветы. (смеётся)"),
    L("ten", "Чёрная Скания. (пауза) Её ночью не видно. Как и меня."),
    L("vitek", "Ивеко S-Way! Летит, как я на свадьбу!"),
    L("sova", "Рено у меня, старенький, но тёплый, как дом."),
    L("ment", "Мерседес Актрос. Ой, чуть не сказал: служебный."),
    L("kardan", "Скания V8! Только она звучит как рок-н-ролл!"),
    L("lisa", "Рыжий MAN, под цвет позывного. (смеётся)"),
    L("soroka", "Ивеко у меня, маленький, с вязаными подушками."),
]
roll = [
    L("student", "Студент на связи! Ну, я тут."), L("professor", "Профессор на связи, коллеги."),
    L("petrovna", "Петровна здесь, сынки!"), L("ten", "...Тень. Я здесь."), L("vitek", "Витёк на связи, лечу!"),
    L("sova", "Сова на связи."), L("ment", "Палыч на приёме."), L("kardan", "Кардан в эфире!"),
    L("lisa", "Лиса тут, волки."), L("soroka", "Сорока на связи!"),
]
for group, kind, lines in (("intent", "truck", truck), ("world", "rollcall", roll)):
    lst = d["reactions"][group].setdefault(kind, [])
    for x in lines:
        if x not in lst:
            lst.append(x)

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("truck", len(d["reactions"]["intent"]["truck"]), "rollcall", len(d["reactions"]["world"]["rollcall"]))
