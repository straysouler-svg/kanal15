"""2026-11-04 (game test): «Как дела?» - 7 drivers had no answer, the rest one each. Appends only.
gpt-audio + Сорока (XTTS) voiced now; the ElevenLabs five -> level3_drafts.json."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F, FD = ROOT / "phrases" / "level3_eleven.json", ROOT / "phrases" / "level3_drafts.json"
d = json.loads(F.read_text(encoding="utf-8"))
dr = json.loads(FD.read_text(encoding="utf-8"))

NOW = {
    "student": ["Нормально! Ну, то есть страшно немножко, но нормально.",
                "Хорошо! Сегодня задом с первого раза встал. (пауза) Ну, со второго."],
    "professor": ["Благодарю, коллега, недурно. Еду, читаю дорожные знаки, как летопись.",
                  "Как у Чехова, коллега: всё хорошо, только немного скучно. (смеётся)"],
    "petrovna": ["Ой, сынок, потихоньку. Чай попила, пирожок съела — жить можно.",
                 "Хорошо, родной! Ноги гудят, а душа поёт."],
    "ten": ["(пауза) Ночь длинная. Дела короткие.", "Живой. (пауза) Это уже неплохо."],
    "vitek": ["Плохо! Опаздываю! Ну, то есть хорошо, но опаздываю!",
              "Дела? Свадьба послезавтра, а я ещё во Франции! Вот такие дела!"],
    "sova": ["Хорошо, милый. Тихо, чай горячий, звёзды на месте.",
             "Спасибо, родной, хорошо. Стихи вспоминаю, чтоб не задремать."],
    "kardan": ["Дела отлично, брат! Громкость на десяти!", "Рок-н-ролл жив, и я жив! Значит, всё хорошо!"],
    "lisa": ["Лучше всех, волк. Бак полный, дорога пустая.", "Как у лисы: хитро и весело. (смеётся)",
             "Нормально. Не спрашивай, а то сглазишь."],
    "ment": ["Нормально, Железяка. Без происшествий. Как у нас говорили: обстановка спокойная.",
             "Не спится, но едется. Значит, нормально.", "Жив-здоров, штрафов сегодня ноль. Рекорд!"],
    "soroka": ["Всё отлично! Еду точно по графику.", "Хорошо! Облака сегодня красивые, перистые."],
}
LATER = {
    "mihalych": ["[warmly] Да потихоньку, сынок. Старушка тянет, я тяну. [chuckles] Вместе тянем.",
                 "[playful] Дела как сажа бела. [laughs] Шучу, нормально всё.",
                 "[tired] Спина ноет, а так хорошо. Галя звонила, значит, день удался."],
    "stas": ["[excited] Норм, бро! Ролик заходит, сорок лайков!", "[whiny] Да так себе, зарядку опять потерял.",
             "[cheerful] Всё огонь, короче!"],
    "yanek": ["[calm] Добро.", "[calm] Помаленьку, хлопцы. Как пчёлы: тихо, но в деле.",
              "[pause] Нормально. Дома всё хорошо, и мне хорошо."],
    "lastochka": ["[sassy] У меня всегда всё хорошо, Железяка, запомни. [laughs]",
                  "[warmly] Нормально, солнышко. Дочка звонила, настроение есть.",
                  "[gossipy] Лучше, чем у некоторых. Потом расскажу."],
    "boroda": ["[loud] Отлично, бродяга! Лечу!", "[laughs] Дела? Двадцать третий штраф получил, юбилейный почти!",
               "[gruff] Нормально. Жрать охота."],
}
lst = d["reactions"]["intent"]["how_are_you"]
have = {(x["actor"], x["text"]) for x in lst}
for a, ts in NOW.items():
    lst.extend({"actor": a, "text": t} for t in ts if (a, t) not in have)
dl = dr.setdefault("reactions", {}).setdefault("intent", {}).setdefault("how_are_you", [])
have = {(x["actor"], x["text"]) for x in dl}
for a, ts in LATER.items():
    dl.extend({"actor": a, "text": t} for t in ts if (a, t) not in have)

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
FD.write_text(json.dumps(dr, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("how_are_you:", len(lst), " drafts:", len(dl))
