"""2026-11-05: «свои направления» — ответ на «куда едешь?» (одобрено пользователем: «приступай»).
Источник — «Направления водителей.md» (таблицы «Город | Реплика» под заголовками водителей).
Пишет в level3_eleven.json:
  actors.<key>.lanes = [city ids]                       -> world.py: конечный пункт водителя из его городов
  reactions.lane.<city id> = [{actor, text}, ...]       -> audio/reactions/lane/<city>/NN.wav (gen_eleven.py level3)

    python tools/add_lanes.py           # проверить разбор, ничего не писать
    python tools/add_lanes.py --apply   # записать (копия *.before_lanes.json)
"""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "phrases" / "level3_eleven.json"
MD = ROOT / "Направления водителей.md"
CITIES = ROOT / "map" / "cities_full.json"

ACTOR = {"Михалыч": "mihalych", "Стас": "stas", "Янек": "yanek", "Ласточка": "lastochka", "Борода": "boroda",
         "Самарканд": "rustam", "Ковбой": "bahti", "Кинолог": "vera", "Петровна": "petrovna",
         "Студент": "student", "Профессор": "professor", "Тень": "ten", "Витёк": "vitek", "Сова": "sova",
         "Палыч": "ment", "Кардан": "kardan", "Лиса": "lisa", "Сорока": "soroka"}
CITY = {"Петербург": "petersburg", "Рига": "riga", "Варшава": "warszawa", "Берлин": "berlin", "Милан": "milano",
        "Лион": "lyon", "Мадрид": "madrid", "Альмерия": "almeria", "Валенсия": "valencia", "Севилья": "sevilla",
        "Верона": "verona", "Роттердам": "rotterdam", "Гамбург": "hamburg", "Салоники": "thessaloniki",
        "Каунас": "kaunas", "Белосток": "bialystok", "Гданьск": "gdansk", "Коувола": "kouvola",
        "Стокгольм": "stockholm", "Линц": "linz", "Бордо": "bordeaux", "Париж": "paris", "Амстердам": "amsterdam",
        "Брюссель": "brussel", "Вена": "wien", "Барселона": "barcelona", "Таллин": "tallinn", "Мюнхен": "munchen",
        "Бухарест": "bucuresti", "Лиссабон": "lisboa", "Стамбул": "istanbul", "София": "sofia",
        "Пловдив": "plovdiv", "Констанца": "constanta", "Будапешт": "budapest", "Гавр": "lehavre",
        "Антверпен": "antwerp", "Феликстоу": "felixstowe", "Хельсинки": "helsinki", "Тампере": "tampere",
        "Инсбрук": "innsbruck", "Осло": "oslo", "Зальцбург": "salzburg", "Вильнюс": "vilnius", "Краков": "krakow",
        "Познань": "poznan", "Лодзь": "lodz", "Дрезден": "dresden", "Лейпциг": "leipzig", "Брно": "brno",
        "Вроцлав": "wroclaw", "Рим": "roma", "Афины": "athens", "Прага": "prague", "Кале": "calais",
        "Порту": "porto", "Белград": "beograd", "Загреб": "zagreb", "Тулуза": "toulouse", "Нант": "nantes",
        "Страсбург": "strasbourg", "Берген": "bergen", "Штутгарт": "stuttgart", "Нюрнберг": "nurnberg",
        "Франкфурт": "frankfurt", "Кёльн": "koln", "Лондон": "london", "Люксембург": "luxembourg",
        "Тромсё": "tromso", "Женева": "geneve", "Эдинбург": "edinburgh"}


def parse():
    lanes, actor = {}, None
    for line in MD.read_text(encoding="utf-8").splitlines():
        h = re.match(r"^#{2,3}\s+(.+)$", line)
        if h:
            title = h.group(1)
            actor = next((v for k, v in ACTOR.items() if title.startswith(k)), None)
            continue
        m = re.match(r"^\|\s*([^|]+?)\s*\|\s*(.+?)\s*\|\s*$", line)
        if actor and m and m.group(1) not in ("Город",) and not m.group(1).startswith("---"):
            city, text = m.group(1), re.sub(r"^\(уже озвучено\)\s*", "", m.group(2))
            if city not in CITY:
                raise SystemExit(f"неизвестный город «{city}» у {actor}")
            lanes.setdefault(actor, []).append((CITY[city], text))
    return lanes


def main(apply):
    lanes = parse()
    cities = json.loads(CITIES.read_text(encoding="utf-8"))
    bad = sorted({c for v in lanes.values() for c, _ in v if c not in cities})
    if bad:
        raise SystemExit(f"нет в карте рации: {bad}")
    data = json.loads(MAIN.read_text(encoding="utf-8"))
    for k in lanes:
        if k not in data["actors"]:
            raise SystemExit(f"нет актёра {k}")
    total = sum(len(v) for v in lanes.values())
    for k, v in lanes.items():
        print(f"{data['actors'][k]['name']:12s} {len(v)}: {', '.join(c for c, _ in v)}")
    print("всего реплик:", total)
    if not apply:
        return
    shutil.copy2(MAIN, MAIN.with_name("level3_eleven.before_lanes.json"))
    by_city = {}
    for k, v in lanes.items():
        data["actors"][k]["lanes"] = [c for c, _ in v]
        for c, t in v:
            by_city.setdefault(c, []).append({"actor": k, "text": t})
    data["reactions"]["lane"] = {"_comment": "Ответ на «куда едешь?»: свой город водителя (его конечный пункт, "
                                             "world.py goal). Источник: «Направления водителей.md», tools/add_lanes.py"}
    data["reactions"]["lane"].update(dict(sorted(by_city.items())))
    MAIN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("записано в", MAIN)


if __name__ == "__main__":
    main("--apply" in sys.argv)
