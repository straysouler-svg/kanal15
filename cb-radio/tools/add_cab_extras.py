"""2026-11-04: every driver's own cab sounds (cab.extras, synthesised by cab_extras.py).
Re-run safe: overwrites cab.extras only. Then: remix.py (no credits) re-renders all audio."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))

M = lambda style, db, ch=1.0: {"kind": "music", "style": style, "db": db, "chance": ch}  # noqa: E731
E = lambda kind, db, ch: {"kind": kind, "db": db, "chance": ch}                         # noqa: E731

EXTRAS = {
    # Старушка Volvo: старый приёмник, эстрада «Ретро FM», иногда сирена мимо
    "mihalych": [M("chanson_mih", -15, 0.65), E("blinker", -20, 0.12)],
    # Стас: бит из телефона, лайки сыплются, иногда звонок
    "stas": [M("rock_light", -15, 0.55), E("ping", -15, 0.45)],
    # Янек: тихая польская/белорусская станция с гармошкой
    "yanek": [M("folk_yanek", -17, 0.45)],
    # Ласточка: чистая кабина, лёгкая попса негромко, поворотник аккуратно
    "lastochka": [M("pop", -16, 0.5), E("blinker", -20, 0.2)],
    # Борода: окно настежь, антирадар пищит, свой воздушный сигнал
    "boroda": [E("radar", -14, 0.3), E("airhorn", -10, 0.15), M("rock", -15, 0.45)],
    # Сорока: котёнок Дизель и спицы
    "soroka": [E("timer", -16, 0.3), M("classic", -19, 0.25)],
    # Студент: навигатор подсказывает, мама звонит
    "student": [E("navi", -14, 0.4), E("ringtone", -18, 0.12), M("rock_light", -18, 0.25)],
    # Профессор: Шопен на «Орфее», страница книги
    "professor": [M("classic", -15, 0.6), E("pages", -18, 0.15)],
    # Петровна: стакан в подстаканнике, «Маяк»
    "petrovna": [E("clink", -12, 0.5), M("estrada", -16, 0.5)],
    # Тень: ночь, дворники, зажигалка, больше ничего
    "ten": [E("wipers", -20, 0.3), E("lighter", -16, 0.2), M("ten", -18, 0.35)],
    # Витёк: телефон вибрирует (мама, брат), поворотник — обгоняет
    "vitek": [E("buzz", -16, 0.35), E("ringtone", -19, 0.15), E("blinker", -18, 0.3), M("vitek", -16, 0.4)],
    # Сова: тихая гитара, романс
    "sova": [M("romance_sova", -16, 0.55)],
    # Палыч: полицейский сканер (старая привычка), сирены
    "ment": [E("scanner", -19, 0.45), E("siren", -15, 0.15), M("chanson_palych", -17, 0.35)],
    # Кардан: рок на всю
    "kardan": [M("rock_kardan", -8, 0.9)],
    # Лиса: танцевальное, поворотник — перестраивается
    "lisa": [M("dance", -14, 0.6), E("blinker", -19, 0.3)],
}

for k, ex in EXTRAS.items():
    d["actors"][k].setdefault("cab", {})["extras"] = ex

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("extras:", {k: [e.get("style", e["kind"]) for e in v] for k, v in EXTRAS.items()})
