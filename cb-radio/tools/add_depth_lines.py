"""2026-11-04: (1) Сорока reworked (ex research scientist, very giggly, precise; no kitten/buns/knitting,
no relationships yet); (2) cab lines - a driver talks about the sound in his cab, that sound is forced
under the line ("cab": [...]); (3) "не знаю / не слышал" (reactions player/dunno).
gpt-audio drivers + Сорока (local XTTS clone) are voiced now; the ElevenLabs five and Сорока's
laughing lines (need the ElevenLabs clone of Tatiana) go to level3_drafts.json.
Appends only; Сорока's off-character lines are dropped via "drop" (numbering kept)."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F = ROOT / "phrases" / "level3_eleven.json"
FD = ROOT / "phrases" / "level3_drafts.json"
d = json.loads(F.read_text(encoding="utf-8"))
dr = json.loads(FD.read_text(encoding="utf-8"))
A = d["actors"]

# ---------------------------------------------------------------- 1. Сорока
s = A["soroka"]
s["about"] = ("Тамара, 38, бывший научный сотрудник (физика атмосферы, облака); работает чётко - чек-лист, график "
              "минута в минуту; всех любит, очень смешливая, смеётся весело; мата нет; отношений пока нет")
s["drop"] = sorted(set(s.get("drop", [])) | {3, 6, 7, 10, 11, 12, 13, 14, 15})   # kitten, buns, knitting, horoscope...
s["cab"]["extras"] = [{"kind": "timer", "db": -16, "chance": 0.3}]
REPL = {  # (group, kind, old text start) -> new text; same slot, so nothing else is re-voiced
    ("intent", "how_are_you", "У меня всё хорошо! Дизель"): "У меня всё отлично! Дорога ровная, график минута в минуту.",
    ("intent", "food", "У меня булочки есть"): "Я по графику обедаю, ровно в час. Через двадцать километров хорошая стоянка, там суп вкусный.",
    ("intent", "truck", "Ивеко у меня, маленький, с вязаными"): "Ивеко у меня. Маленький, аккуратный, всё по чек-листу проверено.",
    ("weather", "rain", "Ой, дождик пошёл. Дизель"): "Ой, дождик пошёл! Слоисто-дождевые облака, это надолго, часа на три.",
}
for (g, k, start), new in REPL.items():
    for ln in d["reactions"][g][k]:
        if ln["actor"] == "soroka" and ln["text"].startswith(start):
            ln["text"] = new
            break
    else:
        if not any(ln["actor"] == "soroka" and ln["text"] == new for ln in d["reactions"][g][k]):
            raise SystemExit(f"не нашёл реплику Сороки {g}/{k}: {start}")
SOROKA_NEW = [  # XTTS now: no laughter needed in these
    "Сорока на связи. Давление в шинах проверила, всё ровно. Можно ехать.",
    "Смотрите, какие облака! Высококучевые. Я их раньше по работе считала.",
    {"text": "Таймер пищит: через сорок минут отдых. Значит, ровно через сорок минут отдых.", "cab": ["timer"]},
    "Туман знаете откуда берётся? Воздух остыл, и влага выпала. Красиво же.",
    "Я двенадцать лет облака изучала. А теперь просто езжу под ними.",
    "До разгрузки сто восемьдесят километров. Приеду ровно к девяти.",
]
have = [p["text"] if isinstance(p, dict) else p for p in s["phrases"]]
for p in SOROKA_NEW:
    if (p["text"] if isinstance(p, dict) else p) not in have:
        s["phrases"].append(p)

# old scenes about the kitten and the buns: out of the air (audio kept in audio/_retired_scenes)
retired = dr.setdefault("retired_scenes", {})
for sid in ("kotenok", "bulochki"):
    if sid in d["scenes"]:
        retired[sid] = d["scenes"].pop(sid)
    src, dst = ROOT / "audio" / "scenes" / sid, ROOT / "audio" / "_retired_scenes" / sid
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))

# ---------------------------------------------------------------- 2. cab lines (voiced now: gpt-audio)
C = lambda t, *fx: {"text": t, "cab": list(fx)}  # noqa: E731
CAB = {
    "student": [C("Навигатор говорит: через двести метров поверните направо. А там поле. (пауза) Я, наверное, не поверну.", "navi"),
                C("Ой, мама звонит. (нервно) Мужики, если что, я покушал. Скажете ей, если спросит?", "ringtone"),
                C("У меня два навигатора, и они спорят. Один налево, другой прямо. А я посередине еду. (смеётся)", "navi")],
    "professor": [C("Коллеги, по «Орфею» Шопен, ноктюрн. (вздыхает) Под такое даже пробка становится философией.", "classic"),
                  C("Стою на светофоре и читаю Чехова. «Краткость — сестра таланта». (смеётся) Это не про мои лекции.", "pages"),
                  C("Знаете, коллеги, концертный рояль весит почти как... нет, вру, фура тяжелее. Намного. (смеётся)", "classic")],
    "petrovna": [C("Чай пью из стакана с подстаканником, как в поезде. Слышите, ложечка звенит? Тридцать лет этот звон слушала.", "clink"),
                 C("Сынки, кто чаю хочет? Ой, через рацию не налью. (смеётся) Ну, представьте, что налила.", "clink"),
                 C("«Маяк» играет, Пьеха поёт. Ой, батюшки, молодость вспомнилась.", "retro")],
    "ten": [C("Дворники. Туда-сюда. (пауза) Всю ночь. Как маятник. Только время не показывают.", "wipers"),
            C("Щёлкаю зажигалкой. Курить бросил. (пауза) А щёлкать — нет.", "lighter"),
            C("Дождь. Фары. Дворники. (пауза) И ни души. Хорошо.", "wipers")],
    "vitek": [C("Опять мама! Пятый раз за час! Мам, я еду, еду я!", "buzz"),
              C("Брат звонит. (тараторит) Да, костюм взял, да, туфли взял. Галстук? (пауза) А, галстук...", "ringtone"),
              C("Обгоняю, обгоняю... Всё, обогнал! Минус тридцать секунд до свадьбы!", "blinker")],
    "sova": [C("По радио гитара, романс. (тихо) «Не жалею, не зову, не плачу...» Это Есенин, милые.", "romance"),
             C("Под гитару и ночь короче. Чай с ромашкой допиваю.", "romance"),
             C("Раньше в библиотеке такая тишина была. А теперь дорога и гитара. Тоже хорошо.", "romance")],
    "ment": [C("Сканер у меня шипит. Привычка. (вздыхает) Двадцать лет слушал, теперь без него не еду.", "scanner"),
             C("Скорая пролетела. Ёлки... Мужики, принимайте вправо, пропускаем.", "siren"),
             C("По сканеру слышу: где-то кого-то остановили. Не нас. Работаем.", "scanner")],
    "kardan": [C("Ща, убавлю... (громко) Всё, убавил! Нет, не убавил. Ладно, так скажу: Кардан на связи!", "rock"),
               C("Это наш альбом, «Кардан», две тысячи четвёртый! Двенадцать слушателей, и один из них я! (смеётся)", "rock"),
               C("Барабаню по рулю, руль терпит. (смеётся) Рок-н-ролл, ночь, трасса!", "rock")],
    "lisa": [C("У меня тут дискотека. Ночь, трасса, танцуем, волки!", "dance"),
             C("Перестраиваюсь. И ещё раз. (смеётся) Поворотник у меня работает больше, чем я.", "blinker"),
             C("Раньше я в клубе ночью работала. Теперь трасса. Тот же клуб, только честнее.", "dance")],
}
for a, items in CAB.items():
    have = [p["text"] if isinstance(p, dict) else p for p in A[a]["phrases"]]
    A[a]["phrases"].extend(p for p in items if p["text"] not in have)

# ---------------------------------------------------------------- 3. "не знаю / не слышал"
DUNNO = {
    "student": ["Э-э, не знаю. Я тут вообще первый раз.", "Ой, не в курсе. Можно я у Михалыча спрошу?",
                "Не знаю, честно. Мне про это ещё не рассказывали."],
    "professor": ["Признаюсь, коллега, не знаю. (смеётся) Историк, который признаётся, — это редкость.",
                  "Не располагаю сведениями. Увы.", "Хм. Об этом источники молчат, коллега."],
    "petrovna": ["Ой, не знаю, сынок. Не слыхала.", "Ёлки-палки, вот не скажу. Не знаю.",
                 "Батюшки, а я и не в курсе. Спроси у Ласточки, она всё знает."],
    "ten": ["Не знаю.", "(пауза) Ночь мне об этом не рассказывала.", "Не слышал. (пауза) И не хочу."],
    "vitek": ["Не знаю, брат! Мне вообще не до этого!", "Без понятия! У меня в голове только свадьба!",
              "Не, не слышал. Я ж никого не слышу, я лечу!"],
    "sova": ["Не знаю, милый. Не слыхала.", "Ой, не скажу, не знаю.", "Не знаю, родной. Я ночью только звёзды знаю."],
    "ment": ["Информацией не располагаю.", "Не знаю, Железяка. Не моя смена.",
             "Ёлки, не в курсе. Раньше бы знал, а теперь нет."],
    "kardan": ["Не знаю, брат! Музыка громко, ничего не слышу!", "Без понятия! Спроси Лису, она хитрая, всё знает.",
               "Не, брат, не в курсе."],
    "lisa": ["Не знаю, волк. И знать не хочу. (смеётся)", "Без понятия. Я бы сказала, если б знала.",
             "Не, не слышала. Редкость, кстати."],
    "soroka": ["Ой, не знаю! Честно, не в курсе.", "Не знаю. Но могу посчитать!", "Не слышала. Надо будет узнать."],
}
lst = d["reactions"]["player"].setdefault("dunno", [])
have = {(x["actor"], x["text"]) for x in lst}
for a, ts in DUNNO.items():
    lst.extend({"actor": a, "text": t} for t in ts if (a, t) not in have)

# ---------------------------------------------------------------- 4. drafts: the ElevenLabs five + Сорока's laughs
dp = dr.setdefault("phrases", {})
DRAFT_CAB = {
    "mihalych": [C("[nostalgic] Пугачёва по радио поёт. [chuckles] Мы с Галей под эту песню на танцах познакомились. Едрит-мадрит, сорок лет прошло.", "retro"),
                 C("[grumbling] Магнитола у Старушки кассетная. [laughs] Стасян спрашивает, что такое кассета. Эх, молодёжь.", "retro")],
    "stas": [C("[excited] О, лайк! [laughs] Ещё лайк! Мужики, ролик пошёл, сорок два просмотра!", "ping"),
             C("[cheerful] Качает, да? Это я под этот бит ролик монтирую. Подписывайтесь, короче.", "hiphop")],
    "yanek": [C("[calm] Гармошка по радио. [pause] Дома сейчас так же играют. Добро.", "folk")],
    "lastochka": [C("[sassy] Попса у меня играет, и не надо мне тут. [laughs] Под неё лучше едется.", "pop")],
    "boroda": [C("[loud] Антирадар пищит! [laughs] Значит, где-то полосатые. А мне пофиг, бродяги.", "radar"),
               C("[laughs] Слышали гудок? Это я! Привет всем!", "airhorn")],
    "soroka": [  # for the ElevenLabs clone of Tatiana (laughs need it: XTTS reads «хи-хи» as words)
        "[laughs] Ой, я опять облака по-научному назвала! Кучево-дождевые. [giggles] Короче, тучка.",
        "[cheerfully] Посчитала: сегодня проехала шестьсот двенадцать километров. [laughs] Зачем посчитала — не знаю!",
        "[giggles] Мне бывший коллега статью прислал про туман. Сорок страниц формул. [laughs] Смешнее анекдота!",
        "[laughing] Чек-лист проверила, всё проверила, а термос дома забыла! [laughs]",
        "[warmly] Всех люблю, всем хорошей дороги! [giggles] Сорока, приём.",
        "[laughs] Барометр падает. Значит, будет дождь. Или барометр сломался. [giggles]",
        "[amused] Радуга! Это же просто преломление света... [laughs] а всё равно красиво!",
        "[cheerful] Приехала минута в минуту. [giggles] Как же я люблю, когда всё по плану.",
    ],
}
for a, items in DRAFT_CAB.items():
    cur = dp.setdefault(a, [])
    have = [p["text"] if isinstance(p, dict) else p for p in cur]
    cur.extend(p for p in items if (p["text"] if isinstance(p, dict) else p) not in have)
DRAFT_DUNNO = {
    "mihalych": ["[thoughtful] Не знаю, сынок. Врать не буду.", "[chuckles] А вот этого не знаю. В восемьдесят седьмом знал бы.",
                 "[calm] Не слыхал, сынок."],
    "stas": ["[confused] Не знаю, бро. Реально без понятия.", "[laughs] Ну ты спросил. Не в курсе вообще.",
             "[sheepish] Блин, не знаю. Загуглю потом."],
    "yanek": ["[calm] Не ведаю, хлопцы.", "[pause] Не знаю. Не скажу.", "[calm] Того не слышал."],
    "lastochka": ["[surprised] Ой, а вот этого даже я не знаю! Запишу.",
                  "[thinking] Не слышала. Странно, обычно мне первой рассказывают.",
                  "[sassy] Не знаю. Но к вечеру буду знать, не сомневайся."],
    "boroda": ["[loud] Не знаю, бродяга! Мне некогда, я гоню!", "[gruff] Без понятия.", "[laughs] Да хрен его знает, бро."],
}
pl = dr.setdefault("reactions", {}).setdefault("player", {}).setdefault("dunno", [])
have = {(x["actor"], x["text"]) for x in pl}
for a, ts in DRAFT_DUNNO.items():
    pl.extend({"actor": a, "text": t} for t in ts if (a, t) not in have)

# ---------------------------------------------------------------- save
src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
FD.write_text(json.dumps(dr, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("Сорока:", len(s["phrases"]), "фраз, drop", s["drop"])
print("cab lines:", sum(len(v) for v in CAB.values()), " dunno:", len(lst), " drafts dunno:", len(pl))
print("scenes:", len(d["scenes"]), " retired:", list(retired))
