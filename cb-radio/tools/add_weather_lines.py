"""One-off: weather lines - reactions.weather.{rain,dry_day,dry_night}. Rain = your wipers are on (the
drivers in radio range are in the same area); day/night from the game clock. Appends only."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))
W = d["reactions"].setdefault("weather", {"_": "rain = your wipers on (same area as you); dry_day / dry_night by "
                                                 "the game clock. Said after a hello sometimes, and as the answer "
                                                 "to your question about the weather."})
L = lambda a, t: {"actor": a, "text": t}  # noqa: E731


def add(kind, lines):
    lst = W.setdefault(kind, [])
    have = {(x["actor"], x["text"]) for x in lst}
    lst.extend(x for x in lines if (x["actor"], x["text"]) not in have)


add("rain", [
    L("student", "Ой, тут ливень такой, дворники не успевают. Страшновато."),
    L("professor", "У нас дождь, коллеги. Мокрый асфальт, как писал классик... впрочем, не помню кто."),
    L("petrovna", "Льёт, сынки, как из ведра. Держите дистанцию, тормозной путь длиннее."),
    L("ten", "Дождь. (пауза) Он смывает всё лишнее. И разметку тоже."),
    L("vitek", "Ливень! А у меня костюм в кабине, лишь бы не промок!"),
    L("sova", "Дождик стучит по крыше кабины. Под него так хорошо думается."),
    L("ment", "Мокро, мужики. На мокром тормозной путь в полтора раза длиннее, это я вам как бывший говорю."),
    L("kardan", "Дождь барабанит, как ударник! Бесплатный концерт."),
    L("lisa", "Опять льёт, блин. Дворники скрипят, как старая телега."),
    L("soroka", "Ой, дождик пошёл. Дизель под сиденье спрятался."),
])
add("dry_day", [
    L("student", "Солнце светит, дорога сухая. Даже не так страшно ехать."),
    L("professor", "Погода, коллеги, превосходная. Видимость, как говорят авиаторы, миллион на миллион."),
    L("petrovna", "Солнышко, сухо. Только к вечеру, говорят, похолодает."),
    L("vitek", "Солнце! Хоть бы такая погода на свадьбе была!"),
    L("lisa", "Солнце в глаза бьёт, хоть очки надевай. А так красота."),
    L("ment", "Сухо, видимость хорошая. Самое время соблюдать скоростной режим. (усмехается)"),
    L("soroka", "Ой, какое солнышко сегодня! Прямо настроение хорошее."),
])
add("dry_night", [
    L("ten", "Ночь ясная. Звёзд столько, что не сосчитать. (пауза) Я и не пытаюсь."),
    L("sova", "Ночь тихая, сухо. Луна над трассой, как фонарь."),
    L("ment", "Ночь сухая, дорога чистая. Только фары встречные слепят."),
    L("kardan", "Ночь ясная, звёзды, музыка. Что ещё надо?"),
    L("lisa", "Ночь сухая, прохладно. Окно приоткрыла, свежо."),
    L("vitek", "Ночь, сухо, лечу! Звёзды мелькают!"),
    L("professor", "Ясная ночь, коллеги. Видна Большая Медведица. Ну, или мне кажется."),
    L("soroka", "Вечер ясный, тихо. Звёздочки зажигаются."),
])

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("weather lines:", {k: len(v) for k, v in W.items() if not k.startswith("_")})
