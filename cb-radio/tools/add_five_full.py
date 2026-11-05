"""2026-11-04: доводим первую пятёрку (Михалыч, Стас, Янек, Ласточка, Борода) до полного набора реплик.
1) переносим их черновики из level3_drafts.json (реплики, «как дела», «на чём едешь», «не знаю», сценки);
2) дописываем недостающее: приветствия, «принял», «не расслышал», ответы на вопросы, «кто в эфире»,
   полиция/камеры (только что видел сам), повторная встреча, погода, ответы других на их приветствие.
Всё только ДОПИСЫВАЕТСЯ в конец списков, номера озвученных реплик не сдвигаются.

    python tools/add_five_full.py           # только предпросмотр -> «Пятёрка — новые реплики.md»
    python tools/add_five_full.py --apply   # записать в level3_eleven.json (с резервной копией), убрать из черновиков
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "phrases" / "level3_eleven.json"
DRAFTS = ROOT / "phrases" / "level3_drafts.json"
PREVIEW = ROOT / "Пятёрка — новые реплики.md"
FIVE = ["mihalych", "stas", "yanek", "lastochka", "boroda"]
NAMES = {"mihalych": "Михалыч", "stas": "Стас", "yanek": "Янек", "lastochka": "Ласточка", "boroda": "Борода"}
# черновая реплика Янека дублирует первую реплику сценки «Рыбалка» — в колоду не переносим
# правки старых черновиков: реальных артистов в эфире не называем; Старушке 2003 года не 38 лет
FIX = {
    "[nostalgic] Пугачёва по радио поёт. [chuckles] Мы с Галей под эту песню на танцах познакомились. Едрит-мадрит, сорок лет прошло.":
        "[nostalgic] По радио старую песню крутят. [chuckles] Мы с Галей под неё на танцах познакомились. Едрит-мадрит, сорок лет прошло.",
    "[chuckles] Старушка моя сегодня два миллиона сто тысяч разменяла. [proudly] Тридцать восьмой год вместе, считай, вторая жена.":
        "[chuckles] Старушка моя сегодня два миллиона сто тысяч разменяла. [proudly] Двадцать третий год вместе, считай, вторая жена.",
}
SKIP_DRAFT = {("yanek", "[calm] Михалыч, на выходных озеро будет по пути. Удочки взял? Приём.")}

NEW_PHRASES = {
    "lastochka": [
        "[warmly] Голосовое дочке записала, на три минуты. [laughs] А она мне: «ок». Одним словом, мальчики. Молодёжь.",
        "[gossipy] Записала в блокнот, для истории: Стасян опять зарядку потерял. [laughs] Это уже шестая страница про него.",
        "[sly] Слышу тут одного под новым позывным... Голос знакомый. [pause] [sassy] Делаю вид, что не узнала. Пусть мучается.",
        "[playful] Ногти сегодня накрасила, вишнёвые. А что? Руль не против.",
        {"text": "[calm] Поворотник включила, перестраиваюсь. [playful] Мальчики, пропустите даму.", "cab": ["blinker"]},
    ],
    "boroda": [
        "[loud] Окно у меня настежь, бродяги! Не люблю духоту. [laughs] Ветер в бороде, как у викинга.",
        "[sheepish] Мама звонила. «Игорёчек, ты покушал?» [clears throat] [loud] Это не в эфир! Бродяги, забыли!",
        "[laughs] Папку для штрафов новую купил, старая кончилась. Коллекционер, бродяги.",
        "[annoyed] Рефрижератор пищит, температура скачет. Если мясо поплывёт, меня самого на фарш пустят, бля.",
    ],
}

# группа -> вид -> [(актёр, текст)]
NEW_REACTIONS = {
    "player": {
        "greet": [
            ("mihalych", "[cheerful] О, кто прорезался! Здорово, Железяка. Михалыч слышит."),
            ("mihalych", "[warmly] Здорово, сынок. Давно тебя не слышно было, я уж думал, на пенсию ушёл. [chuckles]"),
            ("mihalych", "[calm] Привет, привет. Михалыч на связи, Старушка тоже."),
            ("stas", "[excited] О, Железяка в эфире! Респект, бро. Стасян на связи."),
            ("stas", "[cheerful] Здорово, братан! Короче, рад слышать, реально."),
            ("stas", "[playful] Йо, Железяка! Ты прям вовремя, я тут уже сам с собой болтал."),
            ("yanek", "[calm] Здорово, Железяка. Слышу."),
            ("yanek", "[warmly] О, Железяка. Добро, что в эфире."),
            ("yanek", "[calm] Здорово. Янек на приёме."),
            ("lastochka", "[playful] О, Железяка! Привет, солнышко. Как раз про тебя вспоминала."),
            ("lastochka", "[cheerful] Привет-привет! Ласточка на связи, все новости при мне."),
            ("lastochka", "[sassy] Явился, Железяка. [laughs] Я уж думала, ты меня избегаешь."),
            ("boroda", "[loud] О, Железяка! Здорово, бродяга! Меня слышно? Меня всех слышно!"),
            ("boroda", "[loud] Железяка на канале! Ну всё, теперь веселее."),
            ("boroda", "[laughs] Здорово, бро! Борода на связи, громко и чётко."),
        ],
        "ack": [
            ("mihalych", "[calm] Понял, сынок. Учту."),
            ("mihalych", "[chuckles] Добро. Записал бы, да ручка в бардачке."),
            ("stas", "[cheerful] Понял, принял, лайк поставил."),
            ("stas", "[casual] Ага, норм. Понял тебя, бро."),
            ("yanek", "[calm] Понял. Так и сделаем."),
            ("yanek", "[calm] Ага. Принял."),
            ("lastochka", "[calm] Ага, поняла."),
            ("lastochka", "[sassy] Поняла, не глухая. [laughs]"),
            ("lastochka", "[warmly] Хорошо, солнышко, запомнила."),
            ("boroda", "[loud] Понял, бродяга! Гоню дальше!"),
            ("boroda", "[gruff] Ага, принято."),
        ],
        "not_heard": [
            ("mihalych", "[grumbling] Чего? Сынок, ты в ведро говоришь, что ли? Повтори."),
            ("stas", "[confused] Бро, ты пропадаешь, будто в туннеле. Ещё раз скажи."),
            ("yanek", "[calm] Не слышу, хлопец. Ещё раз."),
            ("lastochka", "[annoyed] Железяка, ты мне шипишь, а не говоришь. Ещё раз."),
            ("lastochka", "[sassy] Чего-чего? Повтори, я записываю."),
            ("boroda", "[loud] Чего? У тебя рация на батарейках, что ли? Громче!"),
            ("boroda", "[annoyed] Бродяга, ни хрена не слышно. Повтори."),
        ],
    },
    "intent": {
        "bye": [
            ("mihalych", "[warmly] Бывай, сынок. Ровной дороги, и не гони там."),
            ("stas", "[cheerful] Давай, бро! На канал мой подпишись, короче. Ну, когда-нибудь."),
            ("yanek", "[calm] Бывай, хлопец. Дорога длинная, не спеши."),
            ("lastochka", "[warmly] Пока, солнышко. Поешь нормально, слышишь?"),
            ("boroda", "[loud] Давай, бродяга! Увидимся на трассе, если догонишь! [laughs]"),
        ],
        "thanks": [
            ("mihalych", "[chuckles] Да не за что, сынок. Сочтёмся салом."),
            ("stas", "[cheerful] Да без базара, братан!"),
            ("yanek", "[calm] Не за что. Добро."),
            ("lastochka", "[sassy] На здоровье. Обращайся, Ласточка всё знает."),
            ("boroda", "[loud] Да брось, бродяга! Свои люди."),
        ],
        "road": [
            ("mihalych", "[calm] Я по ней только что прошёл, сынок. Ям хватает, но ехать можно. Не гони только."),
            ("stas", "[confused] Дорога? Да норм вроде. Я, если честно, больше в телефон смотрел. [laughs] Шучу. Почти."),
            ("lastochka", "[gossipy] Дорога нормальная, я только оттуда. А вот на заправке у развязки такое было... [pause] Потом расскажу."),
            ("boroda", "[loud] Дорога? Летишь, бродяга! Я тут на девяноста прошёл. [laughs] Ну ладно, на ста."),
        ],
        "police": [
            ("boroda", "[warning] Полосатые? Увижу — первым скажу, бродяга. У меня антирадар, я их чую."),
        ],
        "food": [
            ("mihalych", "[chuckles] Есть хочешь? Хлеб да сало, сынок, вот и вся столовая. Встанешь рядом, поделюсь."),
            ("stas", "[whiny] Пожрать? Бро, у меня доширак и полбанки энергетика. Кредит, сам понимаешь."),
            ("yanek", "[warmly] Мёд есть. Хлеба кусок найду. Подъезжай."),
            ("lastochka", "[caring] Голодный? Я так и знала. На следующей заправке суп нормальный, сама брала. Иди поешь."),
            ("boroda", "[gruff] Жрать? Я мясо везу, бродяга, а сам на сухарях. [laughs] Ирония, бля."),
        ],
        "joke": [
            ("mihalych", "[chuckles] Анекдот? Едет дальнобой, видит знак: «До Москвы две тысячи». Вздыхает: «Ну, к ужину не успею». [laughs] Это про меня, сынок."),
            ("stas", "[laughing] Анекдот, короче: заходит блогер в кабину фуры... [pause] [sheepish] Не, забыл, чем кончается. Но смешно было."),
            ("yanek", "[calm] Анекдот... Пчела пчеле: «Что делаешь?» — «Работаю». [pause] Всё. [chuckles softly] У пчёл анекдоты короткие."),
            ("lastochka", "[gossipy] Анекдот? Да у меня каждая новость с трассы смешнее анекдота. [laughs] Вчера один на стоянке... [pause] Нет, это не для эфира."),
            ("boroda", "[laughs] Анекдот! Полосатый мне: «Знаете, с какой скоростью ехали?» А я: «Знаю, я ж её и ехал!» [laughs] Двадцать четвёртый штраф, бродяги."),
        ],
        "radio_check": [
            ("mihalych", "[calm] Слышу тебя, сынок, чисто. Как в восемьдесят седьмом по проводу."),
            ("stas", "[excited] Слышу тебя, бро, как в наушниках! Чётко!"),
            ("yanek", "[calm] Слышу хорошо. Чисто."),
            ("lastochka", "[cheerful] Слышу тебя, солнышко, отлично!"),
            ("boroda", "[loud] Слышу! Меня-то все слышат, а вот тебя еле-еле!"),
        ],
        "help": [
            ("mihalych", "[concerned] Что стряслось, сынок? Говори толком, где стоишь. Изолента у меня всегда с собой."),
            ("stas", "[nervous] Чё случилось, бро? Я, короче, не механик, но могу Михалыча позвать!"),
            ("yanek", "[concerned] Где стоишь? Говори. Помогу, чем смогу."),
            ("lastochka", "[stern] Так, спокойно. Где стоишь? Мальчики, кто рядом с Железякой, отзовитесь!"),
        ],
    },
    "world": {
        "rollcall": [
            ("mihalych", "[clears throat] Михалыч тут. Куда ж я денусь."),
            ("stas", "[excited] Стасян тут! Всегда тут!"),
            ("yanek", "[calm] Янек. Тут."),
            ("lastochka", "[cheerful] Ласточка здесь, мальчики!"),
            ("boroda", "[loud] Борода тут! Кто сомневался?"),
        ],
        "leave": [
            ("mihalych", "[fading] Пропадаешь, сынок... Ровной дороги..."),
            ("stas", "[fading] Бро, ты пропадаешь... короче, на связи..."),
            ("yanek", "[fading] Пропадаешь... Бывай..."),
            ("lastochka", "[fading] Мальчики, пропадаю... не скучайте..."),
            ("boroda", "[fading] Бродяги... пропадаю... даже кикер не тянет..."),
        ],
        "meet_again": [
            ("mihalych", "[cheerful] Опять ты, Железяка! [chuckles] Земля круглая, а трасса ещё круглее."),
            ("stas", "[excited] Железяка, опять ты! Это судьба, бро, реально."),
            ("yanek", "[warmly] Опять встретились. [pause] Добро."),
            ("lastochka", "[playful] Железяка, опять ты! Это уже в блокнот, для истории."),
            ("boroda", "[loud] Опять ты, Железяка! Ты что, за мной гонишься? [laughs]"),
        ],
        "clear": [
            ("mihalych", "[calm] Встречные, впереди чисто, я только прошёл. Едьте спокойно."),
            ("stas", "[cheerful] Встречные, чисто впереди, я только оттуда. Валите спокойно."),
            ("yanek", "[calm] Встречные, чисто. Я только проехал."),
            ("lastochka", "[cheerful] Встречные, чисто впереди, я только проехала. Даже скучно."),
            ("boroda", "[loud] Встречные, чисто! Ни полосатых, ни камер, я только прошёл. Летите!"),
        ],
        "police_yes": [
            ("mihalych", "[stern] Стоят, сынок. Проезжал только что, полосатые с радаром. Сбрось."),
            ("stas", "[nervous] Стоят, бро, стоят! Я мимо проезжал, чуть не обделался. Сбрасывай."),
            ("yanek", "[calm] Стоят. Видел, когда проезжал. Не спеши там."),
            ("lastochka", "[gossipy] Стоят, солнышко, стоят! Своими глазами видела, с радаром. Сбрось."),
            ("boroda", "[warning] Стоят, бродяга! Я мимо них только что, с радаром. Антирадар чуть не сгорел."),
        ],
        "police_no": [
            ("mihalych", "[calm] Не видел, сынок. Я оттуда, никого не было."),
            ("stas", "[casual] Не, бро, чисто. Я только оттуда, никого."),
            ("yanek", "[calm] Не видел. Чисто."),
            ("lastochka", "[calm] Я только оттуда, никого. А я бы заметила, поверь."),
            ("boroda", "[loud] Чисто, бродяга! Я оттуда, никого. Антирадар молчит."),
        ],
        "warn_police": [
            ("boroda", "[warning] Встречные, внимание! Полосатые стоят, я только мимо проехал. С радаром. Сбрасывайте!"),
        ],
        "warn_camera": [
            ("boroda", "[warning] Встречные, камера впереди! Я проскочил, вспышку видел. [grumbling] Двадцать четвёртый, наверное."),
        ],
    },
    "weather": {
        "rain": [
            ("mihalych", "[grumbling] Льёт, едрит-мадрит. Колени ещё утром сказали. Дистанцию держите, ребята."),
            ("stas", "[sarcastic] Ливень, бро. Дворники не справляются. Я тоже."),
            ("yanek", "[calm] Дождь. Для огорода хорошо, для дороги плохо. Не спешите, хлопцы."),
            ("lastochka", "[annoyed] Льёт, мальчики. А я машину вчера помыла, между прочим."),
            ("boroda", "[loud] Льёт, бродяги! А мне пофиг, окно всё равно открыто. [laughs] Мокрый, но свободный."),
        ],
        "dry_day": [
            ("mihalych", "[content] Сухо, солнышко. Старушка такую погоду любит, и я тоже."),
            ("stas", "[happy] Солнце, сухо, кайф! Вот бы ещё кондей нормально дул."),
            ("yanek", "[content] Сухо, тепло. Дома бы сейчас у ульев посидеть."),
            ("lastochka", "[happy] Солнышко, сухо. Окошко приоткрыла, бризом пахнет. [laughs] Морским, из ароматизатора."),
            ("boroda", "[loud] Сухо, солнце! Идеальная погода, чтоб гнать!"),
        ],
        "dry_night": [
            ("stas", "[dreamy] Ночь сухая, звёзды. Сфоткать бы, да руль держать надо."),
            ("boroda", "[quietly] Ночь сухая... [loud] Самое время прибавить, пока полосатые спят!"),
        ],
    },
    "greet_reply": {
        "mihalych": [
            ("lastochka", "[warmly] Здравствуйте, Михалыч. Гале привет."),
            ("boroda", "[loud] Здорово, Михалыч! Опять шестьдесят едешь? [laughs]"),
        ],
        "yanek": [
            ("boroda", "[respectful] О, Янек. Здорово."),
            ("stas", "[cheerful] Янек, здорово! Мёд ещё остался?"),
        ],
    },
}


def tx(item):
    return item["text"] if isinstance(item, dict) else item


def fixed(item):
    t = tx(item)
    if t not in FIX:
        return item
    return dict(item, text=FIX[t]) if isinstance(item, dict) else FIX[t]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    apply = "--apply" in sys.argv
    data = json.loads(MAIN.read_text(encoding="utf-8"))
    drafts = json.loads(DRAFTS.read_text(encoding="utf-8"))
    md = ["# Пятёрка — новые реплики (на проверку перед озвучкой)", "",
          "Пометки в [скобках] — игра голосом, вслух не произносятся. «из черновика» — написано раньше, ждало кредитов.", ""]
    per = {a: [] for a in FIVE}          # актёр -> [(раздел, текст, источник)]
    chars = 0

    # 1. черновые реплики
    for a in FIVE:
        moved = [fixed(p) for p in drafts["phrases"].get(a, []) if (a, tx(p)) not in SKIP_DRAFT]
        for p in moved:
            per[a].append(("своя реплика", tx(p), "из черновика"))
        for p in NEW_PHRASES.get(a, []):
            per[a].append(("своя реплика", tx(p), "новое"))
        if apply:
            data["actors"][a]["phrases"] += moved + NEW_PHRASES.get(a, [])
            drafts["phrases"].pop(a, None)

    # 2. черновые реакции
    for group, kinds in drafts.get("reactions", {}).items():
        if group.startswith("_"):
            continue
        for kind, lines in kinds.items():
            if kind.startswith("_"):
                continue
            keep, move = [], []
            for ln in lines:
                (move if ln["actor"] in FIVE else keep).append(ln)
            for ln in move:
                per[ln["actor"]].append((f"{group}/{kind}", ln["text"], "из черновика"))
            if apply:
                data["reactions"].setdefault(group, {}).setdefault(kind, []).extend(move)
                kinds[kind] = keep

    # 3. новые реакции
    for group, kinds in NEW_REACTIONS.items():
        for kind, lines in kinds.items():
            for actor, text in lines:
                who = actor if group != "greet_reply" else actor
                per.setdefault(who, [])
                label = f"{group}/{kind}" if group != "greet_reply" else f"отвечает на приветствие: {NAMES.get(kind, kind)}"
                per[who].append((label, text, "новое"))
                if apply:
                    data["reactions"].setdefault(group, {}).setdefault(kind, []).append({"actor": actor, "text": text})

    # 4. черновые сценки
    scenes = {k: v for k, v in drafts.get("scenes", {}).items() if all(ln["actor"] in FIVE for ln in v)}
    if apply:
        for k, v in scenes.items():
            assert k not in data["scenes"], k
            data["scenes"][k] = v
            drafts["scenes"].pop(k)

    labels = {"своя реплика": "Свои реплики в эфир", "intent/how_are_you": "«Как дела?»", "intent/truck": "«На чём едешь?»",
              "player/greet": "Ответ на твоё приветствие", "player/ack": "«Принял»", "player/not_heard": "«Не расслышал»",
              "player/dunno": "«Не знаю»", "world/rollcall": "«Кто в эфире?»", "world/leave": "Уходит из зоны связи",
              "world/meet_again": "Повторная встреча", "world/clear": "Встречным: впереди чисто",
              "world/police_yes": "«Полиция есть?» — да (видел сам)", "world/police_no": "«Полиция есть?» — нет",
              "world/warn_police": "Встречным: полиция", "world/warn_camera": "Встречным: камера",
              "weather/rain": "Дождь", "weather/dry_day": "Сухо, день", "weather/dry_night": "Сухо, ночь",
              "intent/bye": "«Пока»", "intent/thanks": "«Спасибо»", "intent/road": "«Как дорога?»",
              "intent/police": "«Полиция есть?»", "intent/food": "«Где поесть?»", "intent/joke": "«Расскажи анекдот»",
              "intent/radio_check": "«Как слышно?»", "intent/help": "«Помогите»"}
    for a in FIVE:
        items = per[a]
        c = sum(len(t) for _, t, _ in items)
        chars += c
        md += [f"## {NAMES[a]} — {len(items)} реплик", ""]
        groups = {}
        for sec, t, src in items:
            groups.setdefault(labels.get(sec, sec), []).append((t, src))
        for g, ts in groups.items():
            md.append(f"**{g}**")
            for t, src in ts:
                md.append(f"- {t}" + (" *(из черновика)*" if src == "из черновика" else ""))
            md.append("")
    md += ["## Сценки (из черновика)", ""]
    for k, v in scenes.items():
        md.append(f"**{k}**")
        for ln in v:
            md.append(f"- {NAMES.get(ln['actor'], ln['actor'])}: {ln['text']}")
            chars += len(ln["text"])
        md.append("")
    total = sum(len(v) for v in per.values()) + sum(len(v) for v in scenes.values())
    md.insert(3, f"Всего {total} реплик, около {chars} символов ElevenLabs (с переделками ~{int(chars * 1.3)}).\n")
    PREVIEW.write_text("\n".join(md), encoding="utf-8")
    print(f"реплик: {total}, символов: {chars} -> {PREVIEW.name}")

    if apply:
        shutil.copy(MAIN, MAIN.with_name("level3_eleven.before_five_full.json"))
        shutil.copy(DRAFTS, DRAFTS.with_name("level3_drafts.before_five_full.json"))
        MAIN.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        DRAFTS.write_text(json.dumps(drafts, ensure_ascii=False, indent=2), encoding="utf-8")
        print("записано в level3_eleven.json, черновики пятёрки убраны (резервные копии *.before_five_full.json)")


if __name__ == "__main__":
    main()
