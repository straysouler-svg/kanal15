"""One-off: reactions + scenes for the night cast (Сова, Палыч, Кардан, Лиса). Appends to the END of lists so
already voiced numbering stays. Rewrites level3_eleven.json in the project's compact style."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))
R = d["reactions"]


def add(group, kind, lines):
    lst = R[group].setdefault(kind, [])
    have = {(x["actor"], x["text"]) for x in lst}
    lst.extend(x for x in lines if (x["actor"], x["text"]) not in have)


L = lambda a, t: {"actor": a, "text": t}  # noqa: E731
# hello to the new ones / from the new ones
add("greet_reply", "sova", [L("ten", "Здравствуй, Сова. (пауза) Ночь будет хорошая.")])
add("greet_reply", "ment", [L("kardan", "Палыч, здорово! Только не штрафуй!")])
add("greet_reply", "kardan", [L("lisa", "Опять ты со своей музыкой, Кардан. Привет.")])
add("greet_reply", "lisa", [L("ment", "Лиса, добрый вечер. Скорость соблюдаем?")])
add("greet_reply", "ten", [L("sova", "Тень, здравствуй. Опять тебя не видно, только слышно.")])
add("greet_reply", "vitek", [L("kardan", "Витёк, гони, брат, успеешь!")])
# your PTT
add("player", "greet", [L("sova", "Железяка, доброй ночи! Сова тебя слышит."),
                        L("ment", "Железяка, Палыч на приёме. Документы при себе? (смеётся)"),
                        L("kardan", "О, Железяка! Ночная смена пополнилась!"),
                        L("lisa", "Железяка, привет! Ночью не спится, да?")])
add("player", "ack", [L("sova", "Поняла тебя, милый."), L("ment", "Принято, Железяка."),
                      L("kardan", "Понял, брат!"), L("lisa", "Поняла, Железяка.")])
# what you ask about
add("intent", "road", [L("kardan", "Дорога пустая, только я и мой бас! Едь спокойно."),
                       L("ment", "Впереди чисто. Но скорость держим, я слежу. (усмехается)")])
add("intent", "police", [L("ment", "Полосатые? Я их за версту чую. Через десять километров пост. Сбрось."),
                         L("lisa", "Камера на выезде, Железяка. Я тебе ничего не говорила.")])
add("intent", "weather", [L("sova", "Туман ложится, Железяка. Ближний включи, дальний только мешает.")])
add("intent", "how_are_you", [L("sova", "Хорошо, милый. Чай есть, книга есть, ночь длинная."),
                              L("kardan", "Как сам? Громко! (смеётся)")])
add("intent", "joke", [L("lisa", "Анекдот? Едет блондинка на фуре... (пауза) Ой, это же я. (смеётся)"),
                       L("ment", "Останавливаю как-то дальнобойщика. Говорю: пьёте за рулём? Он: нет, за рулём я еду. (смеётся)")])
add("intent", "food", [L("sova", "У меня бутерброды с сыром. Догонишь, угощу.")])
add("intent", "radio_check", [L("kardan", "Слышу тебя громко! Даже громче моей музыки!")])
add("intent", "bye", [L("lisa", "Пока, Железяка. Не скучай."), L("sova", "Хорошей дороги, Железяка. Береги себя.")])
add("intent", "thanks", [L("ment", "Служу дороге! (смеётся)")])
# night scenes
S = d["scenes"]
S.setdefault("zvezdy", [L("ten", "Сова, ты видишь звёзды? Приём."),
                        dict(L("sova", "Вижу, Тень. Как будто на дорогу кто-то бисер рассыпал."), pause=1.4),
                        dict(L("ten", "Красиво сказала. (пауза) Запомню."), pause=0.9)])
S.setdefault("pravila", [L("kardan", "Палыч, а ты меня оштрафовал бы? За музыку?"),
                         dict(L("ment", "За музыку нет. За такую музыку да! (смеётся)"), pause=1.1),
                         dict(L("kardan", "Ну Палыч! (смеётся) Это же классика!"), pause=0.6)])
S.setdefault("lisa_kardan", [L("lisa", "Кардан, сделай свою музыку потише, у меня зеркала дрожат."),
                             dict(L("kardan", "Лиса, это не зеркала дрожат, это ты от восторга."), pause=1.0),
                             dict(L("lisa", "Мечтай, Гена. (смеётся)"), pause=0.7)])
S.setdefault("dusha", [L("ment", "Тень, ты всё философствуешь? А документы в порядке? (усмехается)"),
                       dict(L("ten", "Документы в порядке, Палыч. А вот с душой не уверен."), pause=1.6),
                       dict(L("ment", "Ну, это уже не ко мне."), pause=0.8)])


def dump(o, ind=0, key=None):
    sp = "  " * ind
    if isinstance(o, dict):
        if key in ("radio", "cab") or (ind >= 3 and all(not isinstance(v, (dict, list)) for v in o.values())):
            return json.dumps(o, ensure_ascii=False)
        items = [f'{sp}  {json.dumps(k, ensure_ascii=False)}: {dump(v, ind + 1, k)}' for k, v in o.items()]
        return "{\n" + ",\n".join(items) + "\n" + sp + "}"
    if isinstance(o, list):
        if all(isinstance(x, (int, float)) for x in o):
            return json.dumps(o)
        items = [sp + "  " + (json.dumps(x, ensure_ascii=False) if not isinstance(x, list) else dump(x, ind + 1))
                 for x in o]
        return "[\n" + ",\n".join(items) + "\n" + sp + "]"
    return json.dumps(o, ensure_ascii=False)


F.write_text(dump(d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("ok:", len(d["actors"]), "actors,", len(d["scenes"]), "scenes")
