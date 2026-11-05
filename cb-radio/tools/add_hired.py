"""2026-11-04: твои наёмные водители (из сохранения, company.py) выходят в эфир, когда оказываются рядом,
а бухгалтерия (Людмила Сергеевна, голос Maria) докладывает о доставках.
Имён в сохранении нет, поэтому у наёмных четыре безымянных голоса: водитель привязан к голосу по своему id.
Актёры hired1..hired4 — extra (не ездят в мире, не говорят в общей колоде). Реакции:
  hired/loaded, hired/empty      — наёмный рядом: с грузом / порожняком;
  buh/delivery, delivery_many, delivery_big — доклады о доставках (крупный рейс: выручка ≥ 100 000).
    python tools/add_hired.py           # предпросмотр
    python tools/add_hired.py --apply   # записать в level3_eleven.json (резервная копия *.before_hired.json)
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "phrases" / "level3_eleven.json"

CAB = {"_": "наёмный, обычная кабина", "road_db": -18, "window": 0.2, "wind_db": -23, "traffic": 0.12,
       "traffic_db": -17, "horn_chance": 0.05, "engine_db": -25, "rpm": 1400,
       "extras": [{"kind": "blinker", "db": -20, "chance": 0.1}]}
HIRED = {
    "hired1": ("Pavel - Warm Conversational", "vGuLaQjzuccOXQyD0H8e", -31, 1.7),
    "hired2": ("Mихаил", "L6qAUOfLV8LhJlH6aFfN", -30, 1.8),
    "hired3": ("Egor - Young & Energetic", "g1G73EpCIdK4HUyDiLYF", -30, 2.0),
    "hired4": ("Anton B - Calm and straight", "AZ8raiNBSkBbrtDIBhFz", -31, 1.5),
}
LINES = {
    "loaded": [
        ("hired1", "[cheerful] Шеф, здравия желаю! Это ваш водитель, из нашего гаража. Иду с грузом, всё по графику."),
        ("hired1", "[calm] Шеф, на связи ваш водитель. Груз целый, машина в порядке. Едем дальше."),
        ("hired2", "[friendly] Начальник, привет! Узнал вашу машину по рации. Везу, не опаздываю, не волнуйтесь."),
        ("hired2", "[laughs] Шеф, вы тоже тут катаетесь? Ну, значит, я на правильной дороге. С грузом иду."),
        ("hired3", "[excited] Шеф, это ваш новенький! Всё нормально, еду, ничего не сломал. [laughs] Пока."),
        ("hired3", "[cheerful] Начальник, здрасьте! Груз везу аккуратно, как вы учили. Ну, как в инструкции."),
        ("hired4", "[calm] Шеф, ваш водитель. Груз на месте, документы в порядке. Связь держу."),
        ("hired4", "[calm] Начальник, проходим мимо. Рейс идёт штатно. Хорошей дороги."),
    ],
    "empty": [
        ("hired1", "[tired] Шеф, это ваш. Разгрузился, возвращаюсь. Дорога нормальная."),
        ("hired2", "[cheerful] Шеф, привет! Порожняком иду, в гараж. Новый рейс возьму — сообщу."),
        ("hired3", "[cheerful] Шеф, порожняком катаюсь. [hopeful] Можно мне потом рейс подлиннее?"),
        ("hired4", "[calm] Возвращаюсь пустой, шеф. Всё спокойно."),
    ],
}
BUH = {
    "delivery": [
        "[pleased] Товарищ начальник, бухгалтерия. Ваш водитель доставил груз, деньги пришли на счёт. [warmly] Вот бы всегда так.",
        "[cheerful] Шеф, приятные новости для разнообразия! Рейс закрыт, оплата поступила. Смета дышит.",
    ],
    "delivery_many": [
        "[excited] Уважаемый шеф, у нас сразу несколько доставок! Деньги идут. [laughs] Я даже кофе себе налила.",
        "[pleased] Товарищ начальник, водители сегодня молодцы: рейсы закрываются один за другим. Так держать!",
    ],
    "delivery_big": [
        "[amazed] Шеф! Пришла оплата за крупный рейс. [pause] Хорошая сумма. Очень хорошая. Я её два раза пересчитала.",
        "[happy] Уважаемый шеф, крупный рейс закрыт! Если так пойдёт, я про штрафы даже вспоминать не буду. [pause] Почти.",
    ],
}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    n = sum(len(v) for v in LINES.values()) + sum(len(v) for v in BUH.values())
    chars = sum(len(t) for v in LINES.values() for _, t in v) + sum(len(t) for v in BUH.values() for t in v)
    for k, v in LINES.items():
        print(f"== hired/{k}")
        for a, t in v:
            print(f"   {a}: {t}")
    for k, v in BUH.items():
        print(f"== buh/{k}")
        for t in v:
            print(f"   {t}")
    print(f"{n} реплик, {chars} символов ElevenLabs")
    if "--apply" not in sys.argv:
        return
    data = json.loads(MAIN.read_text(encoding="utf-8"))
    for key, (vname, vid, noise, drive) in HIRED.items():
        data["actors"].setdefault(key, {
            "name": f"Наёмный водитель {key[-1]}", "extra": True, "fx": "radio",
            "about": "твой наёмный водитель (из сохранения игры), зовёт тебя «шеф», «начальник»",
            "voice": vname, "voice_id": vid, "model": "eleven_v3", "stability": 0.5,
            "radio": {"noise_db": noise, "drive": drive, "roger_beep": False}, "cab": CAB, "phrases": []})
    hired = data["reactions"].setdefault("hired", {
        "_": "your hired drivers (from the save) when one is within radio range: loaded / empty; "
             "the driver is tied to one voice by his id"})
    for k, v in LINES.items():
        lst = hired.setdefault(k, [])
        have = {(x["actor"], x["text"]) for x in lst}
        lst.extend({"actor": a, "text": t} for a, t in v if (a, t) not in have)
    buh = data["reactions"]["buh"]
    for k, v in BUH.items():
        lst = buh.setdefault(k, [])
        have = {x["text"] for x in lst}
        lst.extend({"actor": "buh", "text": t} for t in v if t not in have)
    shutil.copy(MAIN, MAIN.with_name("level3_eleven.before_hired.json"))
    MAIN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("записано")


if __name__ == "__main__":
    main()
