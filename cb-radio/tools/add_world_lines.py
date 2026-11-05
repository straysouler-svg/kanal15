"""One-off: lines for the living highway - leaving range, meeting again, police/radar knowledge.
Group reactions.world.<kind>. Appends only (voiced numbering stays). Reuses add_night_cast's dumper."""
import importlib.util
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
spec = importlib.util.spec_from_file_location("anc", Path(__file__).with_name("add_night_cast.py"))
d = json.loads(F.read_text(encoding="utf-8"))
W = d["reactions"].setdefault("world", {"_": "living highway: leave = going out of range (played degraded); "
                                               "meet_again = hello when you met before; warn_* = an oncoming "
                                               "driver who has just passed it; clear = nothing on his way; "
                                               "police_yes/police_no = answer to your question about police."})
L = lambda a, t: {"actor": a, "text": t}  # noqa: E731


def add(kind, lines):
    lst = W.setdefault(kind, [])
    have = {(x["actor"], x["text"]) for x in lst}
    lst.extend(x for x in lines if (x["actor"], x["text"]) not in have)


add("leave", [
    L("student", "Ой... вы пропадаете... я, кажется, уезжаю... всем пока!"),
    L("professor", "Коллеги, связь слабеет... было приятно... до встречи."),
    L("petrovna", "Сынки... не слышу уже... ровной вам дороги!"),
    L("ten", "...Пропадаешь. (пауза) Значит, так надо."),
    L("vitek", "Всё, ухожу из зоны! Если что, я на свадьбе!"),
    L("sova", "Ребята, вы пропадаете... доброй ночи вам."),
    L("ment", "Связь теряю, мужики. Соблюдайте там."),
    L("kardan", "Всё, улетаю из зоны! Рок жив!"),
    L("lisa", "Пропадаете, волки... ладно, до связи."),
    L("soroka", "Ой, вас почти не слышно... пока-пока!"),
])
add("meet_again", [
    L("student", "Ой, Железяка! Опять ты! Я тебя помню! (смеётся)"),
    L("professor", "Коллега, снова пересеклись! Мир тесен, как говорится."),
    L("petrovna", "Железяка, сынок, опять ты! Как доехал-то в прошлый раз?"),
    L("ten", "...Снова ты, Железяка. (пауза) Значит, не случайно."),
    L("vitek", "Железяка! Опять мы! Слушай, я до сих пор не успеваю!"),
    L("sova", "Железяка, милый, снова встретились. Рада тебя слышать."),
    L("ment", "Железяка, опять ты на моём участке? (смеётся) Здорово!"),
    L("kardan", "Железяка, брат! Снова вместе в ночном эфире!"),
    L("lisa", "Опять Железяка? Ты что, за мной ездишь? (смеётся)"),
    L("soroka", "Ой, Железяака! Опять встретились! Как ты?"),
])
add("warn_police", [
    L("petrovna", "Встречные, сынки, за городом полосатые стоят, с радаром. Сбросьте."),
    L("vitek", "Встречные, внимание! На развязке полиция, меряют скорость!"),
    L("ment", "Встречные, бывшие мои коллеги на посту, за мостом. С радаром. Не гоните."),
    L("lisa", "Встречные, там полосатые у заправки засели. Я вам ничего не говорила."),
    L("kardan", "Встречные, на подъезде полиция с фотиком! Тише едем!"),
    L("ten", "Встречные. Впереди полосатые. (пауза) Не спешите туда, куда не надо."),
    L("student", "Э-э, встречные... там полицейская машина стоит. Наверное, с радаром."),
])
add("warn_camera", [
    L("ment", "Встречные, на подъезде к городу камера. Рабочая, проверено на себе."),
    L("petrovna", "Сынки, там камера у въезда стоит, на столбе. Сбросьте, а то штраф."),
    L("lisa", "Встречные, камера за поворотом. Улыбнитесь, вас снимают. (смеётся)"),
    L("vitek", "Встречные, там камера! Я под неё влетел, блин!"),
    L("sova", "Ребята, впереди у вас камера на мосту. Аккуратнее."),
])
add("clear", [
    L("professor", "Встречные, впереди чисто, коллеги. Я только оттуда."),
    L("kardan", "Встречные, дорога чистая, гоните! Ну, в разумных пределах."),
    L("sova", "Встречные, у вас впереди чисто. Тихая ночь."),
    L("petrovna", "Сынки, впереди чисто, я только проехала. Ни души."),
    L("soroka", "Встречные, впереди всё чисто! Хорошей дороги!"),
])
add("police_yes", [
    L("ment", "Стоят, Железяка. Я мимо них проехал, за городом. С радаром."),
    L("petrovna", "Стоят, сынок, стоят. Я только мимо проехала. Сбрось там."),
    L("lisa", "Есть, Железяка. У заправки засели. Я их видела."),
    L("vitek", "Стоят! Я мимо пролетел, чуть не попал!"),
    L("kardan", "Есть полосатые, брат. Сам видел минут десять назад."),
])
add("police_no", [
    L("ment", "Чисто, Железяка. Я только оттуда, никого нет."),
    L("petrovna", "Чисто, сынок, я только что проехала. Никого."),
    L("professor", "Не видел, коллега. По моим наблюдениям, путь свободен."),
    L("sova", "Не было, милый. Я проехала, всё чисто."),
    L("ten", "Никого. (пауза) Только ночь."),
])

spec_mod = importlib.util.module_from_spec(spec)
src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
dump_src = src[src.index("def dump("):src.index("F.write_text(")]
ns = {"json": json}
exec(dump_src, ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("world lines:", {k: len(v) for k, v in W.items() if not k.startswith("_")})
