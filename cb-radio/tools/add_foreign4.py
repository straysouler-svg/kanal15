# -*- coding: utf-8 -*-
"""2026-11-22: четвёрка проезжих — полные ветки по образцу x_fi (одобрено пользователем).
Новые: x_no (норвежец, onyx), x_sv (швед, shimmer), x_tr (турок, alloy). Расширение: x_pl.
Пулы: foreign.<lang>, foreign_reply.<lang>, foreign_warm.<lang> (warm у pl отсутствовал).
Только дописывание; ремарки TTS английские, как у x_fi."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))

CAB = {"_": "проезжий", "road_db": -18, "window": 0.5, "wind_db": -21, "traffic": 0.1, "traffic_db": -18,
       "horn_chance": 0.1, "engine_db": -25, "rpm": 1450}
RADIO = {"noise_db": -27, "drive": 2.0, "roger_beep": False}

NEW = {
    "x_no": {"lang": "no", "voice": "onyx",
             "style": "норвежский водитель грузовика, неспешный философ, мягкий голос, всё «bra», "
                      "философствует о погоде и фьордах"},
    "x_sv": {"lang": "sv", "voice": "shimmer",
             "style": "шведский водитель фуры, сухой и дотошный, корректный, немного недовольный "
                      "электрофурами, ровная интонация"},
    "x_tr": {"lang": "tr", "voice": "alloy",
             "style": "турецкий дальнобойщик, говорливый душа компании, тёплый, зовёт на чай, "
                      "«kardeşim» на каждом шагу"},
}
for key, v in NEW.items():
    d["actors"].setdefault(key, {
        "name": f"иностранец ({v['lang']})", "extra": True, "lang": v["lang"], "engine": "gpt-audio",
        "voice": v["voice"], "voice_id": f"gpt-audio:{v['voice']}:{v['lang']}", "style": v["style"],
        "radio": dict(RADIO), "cab": dict(CAB), "phrases": []})

def add(group, kind, actor, text, ru=None):
    pool = d["reactions"].setdefault(group, {})
    lst = pool.setdefault(kind, [])
    item = {"actor": actor, "text": text}
    if ru:
        item["ru"] = ru
    if item not in lst:
        lst.append(item)

# foreign: встречный на дороге
for t in ["God kveld, kanalen! Hvordan går det på veien?",
          "Pass deg! Politiet bak broa, de har radar.",
          "Her går alt fint, kjør rolig. Det er elg i skumringa.",
          "For en regn! (sighs) Men det er bare vær, det. Bra kjøring, folkens!",
          "Lange turer, stille radio. (chuckles) Det liker jeg. Ha det bra!"]:
    add("foreign", "no", "x_no", t)
for t in ["God kväll, kanalen! Hur är väglaget där framme?",
          "Varning! Polis efter bron, de har laser.",
          "Allt lugnt här. Kör lagom, då kommer du fram.",
          "(sighs) El-lastbilar överallt. De kör tyst och fort, det är farligt.",
          "Vilken kö! (sighs) Men jag har kaffe, så det går bra. Lycka till, grabbar!"]:
    add("foreign", "sv", "x_sv", t)
for t in ["İyi akşamlar, kanal! Yol nasıl gidiyor, kardeşim?",
          "Dikkat! Köprünün arkasında polis var, radar çalışıyor!",
          "Yol burada açık, gönül ferah. (laughs) Siz de öyle, kardeşler!",
          "Ne yağmur ama! (sighs) Çayım var, ben durmam. Hayırlı yolculuklar!",
          "Uzun yol, sıcak çay, iyi muhabbet. (laughs) Görüşürüz, dostum!"]:
    add("foreign", "tr", "x_tr", t)
for t in ["Siema, kanał! U mnie wszystko git, uważajcie na oblodzenie!",
          "Co za mróz! (laughs) W kabinie minus, a serce gorące. Szerokiej, bracia!",
          "Droga czysta aż po horyzont. Miłej jazdy, panowie!"]:
    add("foreign", "pl", "x_pl", t)

# foreign_reply: не понял, но хорошей дороги
for t, ru in [("(laughs) Jeg skjønner ikke et ord, bror, men god tur!",
               "Ха! Ни слова не понял, брат, но счастливой дороги!"),
              ("Russisk? (laughs) Ingen anelse, men hilsen tilbake, kollega!",
               "По-русски? Понятия не имею, но привет в ответ, коллега!"),
              ("(laughs) Ja, ja… Jeg forsto ingenting. Kjør forsiktig, venn!",
               "Да-да… Ничего не понял. Осторожнее на дороге, друг!")]:
    add("foreign_reply", "no", "x_no", t, ru)
for t, ru in [("(laughs) Jag förstår ingenting, bror, men lycklig resa!",
               "Ничего не понял, брат, но счастливого пути!"),
              ("Ryska? (laughs) Ingen aning vad du säger, men hej då, kollega!",
               "По-русски? Не знаю, что ты сказал, но привет, коллега!"),
              ("(laughs) Ja, precis… jag hörde bara brus. Kör försiktigt!",
               "Да, точно… Я услышал одни помехи. Осторожней за рулём!")]:
    add("foreign_reply", "sv", "x_sv", t, ru)
for t, ru in [("(laughs) Hiç anlamadım kardeşim, ama hayırlı yolculuklar!",
               "Ха! Ничего не понял, братишка, но доброго пути!"),
              ("Rusça mı? (laughs) Ne dediğini bilmiyorum, ama selam sana, kaptan!",
               "По-русски? Не знаю, что ты сказал, но привет тебе, капитан!"),
              ("(laughs) Evet, evet… hiçbir şey anlamadım. Dikkatli sür, dostum!",
               "Да-да… Я вообще ничего не понял. Осторожнее за рулём, друг!")]:
    add("foreign_reply", "tr", "x_tr", t, ru)

# foreign_warm: игрок ответил на его языке
for t, ru in [("(laughs) Å, du snakker norsk! Så bra, bror! God tur, hilsen til dere!",
               "О, ты говоришь по-норвежски! Отлично, брат! Счастливого пути, привет вашим!"),
              ("(warm) Hei hei, nå ble jeg glad! Vi forstår hverandre. Kjør pent, vennen min!",
               "Эй-эй, как я рад! Мы понимаем друг друга. Красиво езжай, мой друг!")]:
    add("foreign_warm", "no", "x_no", t, ru)
for t, ru in [("(laughs) Å, du talar svenska! Så bra, bror! Lycka till på vägarna!",
               "О, ты говоришь по-шведски! Здорово, брат! Удачи на дорогах!"),
              ("(pleased) Men titta! Vi förstår varandra. Varsågod och kör, vän!",
               "Ну надо же! Мы понимаем друг друга. Поехали, друг, дорога твоя!")]:
    add("foreign_warm", "sv", "x_sv", t, ru)
for t, ru in [("(laughs) O, mówisz po polsku! Brawo, bracie! Szerokiej drogi!",
               "О, говоришь по-польски! Браво, брат! Широкой дороги!"),
              ("(pleased) No i śmiga! Rozumiemy się! Pozdrowienia dla całej ekipy, kolego!",
               "Ну и отлично! Понимаем друг друга! Привет всей вашей команде, приятель!")]:
    add("foreign_warm", "pl", "x_pl", t, ru)
for t, ru in [("(laughs) Aa, Türkçe konuşuyorsun! Bravo kardeşim! Hayırlı yolculuklar!",
               "А-а, говоришь по-турецки! Браво, братишка! Доброго пути!"),
              ("(warm) Vay be! Anlaştık işte! Selamlar, çay benden, kaptan!",
               "Вот это да! Мы же поняли друг друга! Привет, чай — за мой счёт, капитан!")]:
    add("foreign_warm", "tr", "x_tr", t, ru)

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("foreign:", {k: len(v) for k, v in d["reactions"]["foreign"].items() if not k.startswith("_")})
print("reply:", {k: len(v) for k, v in d["reactions"]["foreign_reply"].items() if not k.startswith("_")})
print("warm:", {k: len(v) for k, v in d["reactions"]["foreign_warm"].items() if not k.startswith("_")})
print("actors:", [k for k in ("x_no", "x_sv", "x_tr") if k in d["actors"]])
