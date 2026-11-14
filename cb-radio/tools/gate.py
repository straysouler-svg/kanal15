# -*- coding: utf-8 -*-
"""Заслон фраз: настоящие фразы из журналов стримов -> ожидаемый (intent, addressee).
Урок 10 навыка kanal15-coding: каждый фикс понимания фразы заканчивается строкой здесь.
Запуск: py -3 tools/gate.py  (из cb-radio/). Выход 0 — все совпали, 1 — есть расхождения.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import intents  # noqa: E402

# (фраза из журнала, ожидаемый intent, ожидаемый addressee) — журнал, дата
CASES = [
    # стрим 14.11.2026: гудок молчал — «обибикни» не матчился, horn падал в player/ack
    ("Ну ты бибикня?", "horn", None),    # адресат «ответ ему» достаётся в cb_radio (last_speaker)
    ("Ласточка. Мигни дальним.", "horn", "lastochka"),
    ("Сорока, Бибикни.", "horn", "soroka"),
    ("Стас, обибикни!", "horn", "stas"),
    ("Да го-го, бибикни, профессор, кто-нибудь бибикните вообще?", "horn", "professor"),
    # стрим 14.11.2026: dist уходил в its_me / how_are_you
    ("Ты далеко, Стас?", "dist", "stas"),
    ("Стас, как ты далеко от меня находишься?", "dist", "stas"),
    # стрим 14.11.2026: joke ловил «расскажи про X» и мусор; «весёлое» — joke, не greet
    ("Ласточка, а расскажи про дочку", "family", "lastochka"),
    ("Ребят, ну чё, в эфире тишина, расскажите чё-нибудь весёлое, что ли?", "joke", None),
    ("Сорока, Расскажений, Гдот.", None, "soroka"),          # мусор ASR — не greet
    ("Самарканд, расскажи о анекдот.", "joke", "rustam"),    # «о анекдот» — всё ещё joke
    # 14.11 (стрим): «Вить» (звательная) не резолвился в Витька — адресат улетал к last_speaker
    ("Вить, Вить, как дела?", "how_are_you", "vitek"),
    ("Вить, ты здесь?", "radio_check", "vitek"),
    # 14.11 (стрим): «сколько дочки лет?» уходил в dunno — это family (пул intent/family живёт, тексты не нужны)
    ("Ласточка, сколько дочки лет?", "family", "lastochka"),
    # стрим 14.11.2026: its_me не должен жадно ловить «ты ... <имя>»
    ("Профессор, это ты?", "its_me", "professor"),
    ("Ты Янек?", "its_me", "yanek"),
    # регрессии: близкие фразы, которые должны остаться прежними
    ("Стас, как дела?", "how_are_you", "stas"),
    ("Как ты?", "how_are_you", None),
    ("Тень, расскажи анекдот", "joke", "ten"),
    ("Кто в эфире?", "who", None),
]


def main():
    bad = 0
    for text, want_i, want_a in CASES:
        got_i, got_a = intents.understand(text)
        ok = got_i == want_i and got_a == want_a
        bad += not ok
        mark = "ok " if ok else "FAIL"
        print(f"{mark} «{text}» -> {got_i}/{got_a}"
              + ("" if ok else f"   (ожидалось {want_i}/{want_a})"))
    print("заслон: проблем нет" if not bad else f"заслон: {bad} расхождений")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
