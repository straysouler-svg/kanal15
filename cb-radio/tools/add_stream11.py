# -*- coding: utf-8 -*-
"""Озвучка по итогам стрима #11 (20.11): финн x_fi, police +32, foreign_warm, пул joke.
Только дописываем в конец списков (номера озвученных не сдвигаются). Озвучка — gen_eleven.py reactions.
"""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))

# --- x_fi (голос fable, OpenAI; альтернатива из брифа — nova) ---
d["actors"].setdefault("x_fi", {
    "name": "иностранец (fi)", "extra": True, "lang": "fi", "engine": "gpt-audio", "voice": "fable",
    "voice_id": "gpt-audio:fable:fi",
    "style": "финский водитель грузовика, спокойный, немного сонная доброта, ровная речь",
    "radio": {"noise_db": -27, "drive": 2.0, "roger_beep": False},
    "cab": {"_": "проезжий", "road_db": -18, "window": 0.5, "wind_db": -21, "traffic": 0.1, "traffic_db": -18,
            "horn_chance": 0.1, "engine_db": -25, "rpm": 1450},
    "phrases": []})

r = d["reactions"]

# --- 1a. foreign.fi (4) ---
fg = r["foreign"]
fi = fg.setdefault("fi", [])
for t in ["Hyvää iltaa, kanava! Miten tie siellä?",
          "Varo! Poliisi sillan takana, tutka!",
          "Täällä kaikki rauhallista. Hyvää matkaa, kaverit!",
          "Onpa pakkasta! Aja rauhallisesti, pitkät matkat."]:
    if {"actor": "x_fi", "text": t} not in fi:
        fi.append({"actor": "x_fi", "text": t})

# --- 1b. foreign_reply.fi (2, с ru-субтитром) ---
fr = r["foreign_reply"]
fir = fr.setdefault("fi", [])
for t, ru in [("(laughs) En ymmärrä sanaakaan, veli, mutta hyvää matkaa!",
               "Ха! Ни слова не понял, брат, но счастливой дороги!"),
              ("(laughs) Suomea? En tiedä, mitä sanoit, mutta terveisiä takaisin, kollega!",
               "По-фински? Не знаю, что ты сказал, но и тебе привет, коллега!")]:
    if {"actor": "x_fi", "text": t} not in fir:
        fir.append({"actor": "x_fi", "text": t, "ru": ru})

# --- 2. police +32 (16 актёров × 2; «пятки»→«пятку» по Корректору) ---
POLICE = {
    "mihalych": ["[warmly] Сынок, спасибо, записал за ухом! А то я газу даю — сам от себя не ожидал.",
                 "[chuckles] Опять они там. Я ж с ними как с тещей: вижу — уже нервничаю."],
    "yanek": ["[calm] Принял. Сбавляю. Не в первый раз.",
              "[short] Вижу пост. Объезжаю. Тихо."],
    "lastochka": ["[sassy] Спасибо, красавчик! Я-то всегда по правилам еду. [laughs] Ну, почти всегда.",
                  "[playful] Записала. Кто тормозить не будет — я первый расскажу."],
    "boroda": ["[loud] Бродяги, сбавляем! Пост за мостом! [grumbling] Опять мой налог на асфальт проверяют!",
               "[grumbling] Я их за версту чую. Нос у меня, как у радара. Дорогой."],
    "professor": ["[thoughtful] Благодарю, коллега. В истории все великие тормозили перед мостом. Некоторые — дважды.",
                  "[amused] Фиксирую: дозор за мостом. Интересно, они тоже ведут журнал наблюдений?"],
    "petrovna": ["Ой, спасибо, милый! Я сразу пятку с газа! (тёпло) Берегите себя, сынок!",
                 "(смеётся) Я ж проводницей была — милицию издалека видеть научилась. Учусь заново!"],
    "ten": ["(тихо) Вижу. Гаснет свет на спидометре. [пауза] Так и я гашу.",
            "(тихо) Они ищут быстрых. Я не быстрый. Я невидимый."],
    "vitek": ["(тараторит) Где?! Кто?! А я ничего! Я по правилам! (паникует) Ты уверен, что за мостом, а не за нами?!",
              "(паникует) Сбросил! Сбросил! Говорят, главное — не бояться. А-а-а!"],
    "ment": ["(ровно) Принято, товарищи. Патруль за мостом. [пауза] Я бы на их месте стоял на солнце. Нет хуже смены, чем моя совесть.",
             "(ворчит) Сбавьте. Они не звери. [пауза] Хотя я из тех, кто в этом не уверен."],
    "kardan": ["(громко) Йо, канал, респект! Сбавляю бас, не спидометр! (смеётся)",
               "(весело) Пост за мостом! Добавлю в текст песни. Рифма: «пост — мост». Уже есть!"],
    "lisa": ["(хитро) Спасибо, милый! Я и так тихо еду. [пауза] Особенно когда кто-то сзади с мигалкой.",
             "(весело) Записала в блокнот. У меня тут все посты, все заправки и все секреты трассы."],
    "rustam": ["[warmly] Спасибо, дорогой! А я как раз чайник ставил. Кок-чой подождёт — закон дороги не ждёт!",
               "[laughs] Полиция — это хорошо. Значит, и за мной никто не угнался!"],
    "vera": ["[dry] Принято. Граф слышит — уши встали. [pause] Ему тоже нельзя нарушать. Дрессировка.",
             "[amused] Сбавляем, как на повороте: плавно, без паники. [pause] Граф так и в машине сидит."],
    "sova": ["[softly] Спасибо, милый. Я и так тихо — мне ночь не нарушать привычнее.",
             "[chuckles] Вижу огоньки. Дальний гашу, сердце не гашу. [pause] Так и едем."],
    "student": ["(волнуется) Спасибо! Я уже сбросил! (радуется) Первый раз сам без штрафа проскочил. Наверное.",
                "(нервно) А если он меня уже видел?! (пауза) Ладно. Торможу. Как учили. Блин."],
    "buh": ["[pleased] Шеф, от всей бухгалтерии — спасибо. Вы только что сэкономили нам статью расходов.",
            "[sighs] Товарищ начальник, они там каждый день. [stern] И всё равно спасибо. С копеечкой, с копеечкой."],
}
pol = r["intent"]["police"]
for actor, lines in POLICE.items():
    for t in lines:
        if {"actor": actor, "text": t} not in pol:
            pol.append({"actor": actor, "text": t})

# --- 3. foreign_warm.<lang> (de/es/it/fi × 2, с ru) ---
fw = r.setdefault("foreign_warm", {
    "_": "warm reply when the PLAYER answers the passer-by in his own language (needs lang detect); "
         "otherwise the standard foreign_reply not-understanding plays"})
WARM = {
    "de": [("x_de", "(lacht) Oh, deutsch! Sehr gut, Bruder! Schöne Grüße nach Russland, gute Fahrt!",
            "О, по-немецки! Очень хорошо, брат! Привет России, счастливого пути!"),
           ("x_de", "(begeistert) Na also, Kollege! Wir verstehen uns doch! Breite Straße, viel Erfolg!",
            "Ну вот, коллега! Мы же понимаем друг друга! Широкой дороги, удачи!")],
    "es": [("x_es", "(ríe) ¡Hablas español! ¡Muy bien, hermano! ¡Buen viaje!",
            "Ха! Говоришь по-испански! Очень хорошо, брат! Счастливого пути!"),
           ("x_es", "(contento) ¡Un español en la radio rusa! ¡Abrazo, compañero, cuidado en la carretera!",
            "Испанец на русской рации! Обнимаю, приятель, берегись на дороге!")],
    "it": [("x_it", "(ride) Oh, parli italiano! Bravissimo, amico! Buon viaggio!",
            "О, говоришь по-итальянски! Молодец, друг! Счастливого пути!"),
           ("x_it", "(felice) Finalmente ci capiamo, fratello! Un saluto grande, attenzione alla polizia!",
            "Наконец-то понимаем друг друга, брат! Большой привет и смотри в оба — полиция!")],
    "fi": [("x_fi", "(nauraa) Oh, suomea! Hyvä, hyvä, kaveri! Tervetuloa, hyvää matkaa!",
            "О, по-фински! Хорошо, хорошо, друг! Добро пожаловать, счастливого пути!"),
           ("x_fi", "(iloinen) Me ymmärrämme toisemme! Sileää tietä, veli!",
            "Мы понимаем друг друга! Гладкой дороги, брат!")],
}
for lang, rows in WARM.items():
    lst = fw.setdefault(lang, [])
    for actor, t, ru in rows:
        if {"actor": actor, "text": t} not in lst:
            lst.append({"actor": actor, "text": t, "ru": ru})

# --- 4. joke (13, разводка по характерам) ---
joke = r.setdefault("joke", {})   # как memes: <actor> -> [lines] -> пулы joke__<actor>
JOKES = [
    ("kardan", "Диспетчер спрашивает: «Где ты?» — «Не знаю. Стою под мостом, на табличке \"высота три восемь\"».» — «Так ты внутри моста, дядя!»"),
    ("petrovna", "Жена спрашивает: «Ты когда дома будешь?» — «Через час!» Говорил он вчера. Дорогу понимает по-своему."),
    ("boroda", "Гаишник: «Превышение». Водитель: «Я же пустой еду!» — «Вот и доказали»."),
    ("professor", "Приехал на выгрузку. «Ты кто?» — «Дальнобой». — «А груз где?» — «А ты кто?» — «Приёмщик». — «А приём где?»"),
    ("mihalych", "Заправился — поехал. Через час опять заправился. Через час — опять. Понял: еду не туда. Разворачиваться стало стыдно."),
    ("lisa", "Стою в пробке. Рядом коллега. Стоим час, второй. Мы вместе постарели. Красиво."),
    ("petrovna", "Жена: «Купи молоко по дороге». Дороги — две тысячи. Молоко едет со мной неделю. Скоро дома."),
    ("boroda", "Спрашивают: «А правда, фуры сами едут?» — «Да. Особенно под горку. И особенно чужие»."),
    ("professor", "Навигатор: «Прибудете в шесть утра». Приехал в шесть вечера. Навигатор молчит. Я тоже. Мы оба устали."),
    ("student", "Документы, права, страховка. Ищу очки. Очки на голове. Документы в бардачке. Страховка в носке. Дальнобой!"),
    ("mihalych", "Диспетчер: «Клиент ругается, груз не тот». Глянул в кузов: груз тот. Клиент, похоже, не тот."),
    ("professor", "Меня спросили, сколько я зарабатываю. Ответил: «Стою столько, сколько проехал». Не поняли. Я и сам нет."),
    ("student", "Вышел из кабины на стоянке — собака лает. «Зря лаешь, свои!» — сказал я. Дверь не открыли. Чужие, видимо."),
]
for actor, t in JOKES:
    lst = joke.setdefault(actor, [])
    if {"actor": actor, "text": t} not in lst:
        lst.append({"actor": actor, "text": t})

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("foreign.fi:", len(fg["fi"]), "| foreign_reply.fi:", len(fir), "| police:", len(pol),
      "| foreign_warm:", {k: len(v) for k, v in fw.items() if not k.startswith("_")},
      "| joke:", len(joke))
