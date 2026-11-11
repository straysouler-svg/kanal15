"""One-off (пилот «мигни — бибикну», 11.11): reactions.horn.{ask_day,ask_night,seen,missed,far}
для soroka / vitek / ten. Тексты утверждены пользователем: phrases/drafts_horn_2026-11-11.md.

Точечная вставка в phrases/level3_eleven.json: блок вставляется сразу после "reactions": {,
остальной файл не перечитывается и не переписывается (EOL сохраняются). Идемпотентен.
"""
import json
import shutil
import sys
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
BACKUP = F.with_name("level3_eleven.before_horn.json")

L = lambda a, t: {"actor": a, "text": t}  # noqa: E731

HORN = {
    "_": ("«Мигни — бибикну» (пилот 11.11): ответы на «ты далеко?» от водителя в пороге 150-1500 м. "
          "ask_day — просьба днём (гудок), ask_night — ночью и в дождь днём (свет), seen — увидел/услышал "
          "сигнал, missed — не разглядел (без упрёка), far — дальше порога, «не услышишь»."),
    "ask_day": [
        L("soroka", "Железяка, я навстречу, в двухстах метрах буду. Бибикни — сверюсь с расписанием, хи-хи."),
        L("soroka", "Я у тебя за спиной, догоняю по графику. Гудни — отмечу в блокноте встречу."),
        L("vitek", "Железяка! Бибикни, бибикни! Я навстречу лечу, как я на свадьбу опаздываю!"),
        L("vitek", "Я за тобой! Сзади! Гудни — я тебя по звуку вычислю, как радар!"),
        L("ten", "Днём меня не видно. Я тот, кого нет. Бибикни — отвечу, если солнце не против."),
        L("ten", "Иду за тобой. Тихо иду. Гудни — отмечусь."),
    ],
    "ask_night": [
        L("soroka", "Встречная. Мигни дальним — я по вспышке азимут возьму, как в лаборатории."),
        L("soroka", "Иду за тобой. Мигни, пожалуйста, — ночью я всех путаю, кроме облаков."),
        L("vitek", "Встречный! Мигни дальним, ага? Я тут всех обгоняю, заметишь — я единственный, кто летит!"),
        L("vitek", "Сзади еду! Мигни — я по фарам пойму, что ты. Мама, не звони сейчас, не звони…"),
        L("ten", "Мигни дальним. Я встречный. Чёрный. Ночью это… не отличается."),
        L("ten", "Сзади еду, как твоя тень. Ну, я и есть. Мигни — пойму, что не приснился."),
    ],
    "seen": [
        L("soroka", "Засекла! Сейчас бибикну — два коротких, как положено по моему чек-листу."),
        L("soroka", "Есть контакт! Отвечаю сигналом, готовься."),
        L("vitek", "Вижу-вижу-вижу! Ща бибикну, держись — у меня он весёлый!"),
        L("vitek", "Есть! Принял! Сейчас затараторю гудком, как мама по телефону!"),
        L("ten", "Вижу. Отвечаю. Один гудок — больше ночь не разрешает."),
        L("ten", "Есть вспышка. Ща бибикну. Коротко. Не пугайся."),
    ],
    "missed": [
        L("soroka", "Не зафиксировала… ничего, трасса длинная, ещё сверимся. Приём."),
        L("vitek", "Не увидел, блин… ладно, на свадьбе расскажешь, где прятался. Приём!"),
        L("ten", "Не разглядел. Или разглядел, но это был заяц. Езжай, приём."),
    ],
    "far": [
        L("soroka", "Далековато, километра три. Не услышишь меня, честно скажу. Приём."),
        L("vitek", "Далеко я, Железяка, не докричишься. Но я лечу! Может, ещё догоню!"),
        L("ten", "Три километра ночи между нами. Не услышишь. Оно и правильно."),
    ],
}


def block_text():
    """Блок "horn": {...} в формате файла (отступ 1 пробел на уровень), строки CRLF."""
    lines = [' "horn": {', '  "_": ' + json.dumps(HORN["_"], ensure_ascii=False) + ","]
    kinds = [k for k in HORN if not k.startswith("_")]
    for ki, kind in enumerate(kinds):
        items = HORN[kind]
        lines.append(f'  "{kind}": [')
        for i, it in enumerate(items):
            comma = "," if i < len(items) - 1 else ""
            lines.append('   {')
            lines.append('    "actor": ' + json.dumps(it["actor"], ensure_ascii=False) + ",")
            lines.append('    "text": ' + json.dumps(it["text"], ensure_ascii=False))
            lines.append('   }' + comma)
        lines.append('  ]' + ("," if ki < len(kinds) - 1 else ""))
    lines.append(' },')
    return "\r\n".join(lines) + "\r\n"


def main():
    with open(F, "r", encoding="utf-8", newline="") as fh:
        text = fh.read()                     # без трансляции EOL: CRLF остаются CRLF
    if '\n "horn": {' in text:
        print("horn: уже вставлено — пропуск")
        return
    if not BACKUP.exists():
        shutil.copyfile(F, BACKUP)
        print("бэкап:", BACKUP.name)
    anchor = ' "reactions": {\r\n'
    if anchor not in text:
        anchor = ' "reactions": {\n'      # на всякий случай, если EOL вдруг LF
        joiner = "\n"
    else:
        joiner = "\r\n"
    head, tail = text.split(anchor, 1)
    block = block_text().replace("\r\n", joiner)
    with open(F, "w", encoding="utf-8", newline="") as fh:
        fh.write(head + anchor + block + tail)
    d = json.loads(open(F, encoding="utf-8").read())
    horn = d["reactions"]["horn"]
    print("horn вставлен:", {k: len(v) for k, v in horn.items() if not k.startswith("_")})


if __name__ == "__main__":
    sys.exit(main())
