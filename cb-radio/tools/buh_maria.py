"""2026-11-04: бухгалтерия переезжает с gpt-audio (shimmer) на ElevenLabs v3, голос Maria (выбор пользователя).
Меняет актёра buh и тексты reactions.buh (ремарки -> теги v3), потом озвучивает ТОЛЬКО reactions.buh."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_eleven as ge  # noqa: E402

F = ge.ROOT / "phrases" / "level3_eleven.json"
TEXTS = {
    "speeding": [
        "[worried] Товарищ начальник, это Людмила Сергеевна, бухгалтерия. Пришёл штраф за превышение скорости. [frustrated] Мы из сметы выбиваемся! Вы же сами бюджет утверждали.",
        "[exasperated] Уважаемый шеф, опять превышение?! [sighs] Я уже не знаю, по какой статье это проводить!",
    ],
    "red_signal": ["[tired] Шеф, бухгалтерия. Штраф за красный свет. [outraged] Красный, товарищ начальник! Это даже не скорость, это светофор!"],
    "crash": ["[worried] Уважаемый шеф, пришёл штраф за аварию. Вы живы? [relieved] Слава богу. [pause] [stern] А теперь скажите, из каких денег ремонт оплачивать будем?"],
    "no_lights": ["[patiently] Товарищ начальник, штраф за езду без света. Включите фары, пожалуйста. [sarcastic] Это бесплатно, в отличие от штрафа."],
    "avoid_sleeping": ["[concerned] Уважаемый шеф, штраф за нарушение режима отдыха. Поспите! [sarcastic] Сон, между прочим, штрафом не облагается."],
    "wrong_way": ["[shocked] Товарищ начальник, штраф за встречку?! [nervous] Я даже спрашивать боюсь, как вы туда попали."],
    "generic": ["[sighs] Шеф, бухгалтерия беспокоит. Ещё один штраф. [worried] Смета трещит по швам."],
    "escalation": [
        "[exasperated] Товарищ начальник! Это уже третий штраф за сегодня! [frustrated] Я вам отчёт на стол положу. И заявление. [sighs] [pause] Шучу. [quietly] Пока шучу.",
        "[pleading] Уважаемый шеф, если так пойдёт дальше, нам зарплату водителям платить будет нечем. [emotional] Подумайте о коллективе!",
    ],
}

sys.stdout.reconfigure(encoding="utf-8")
data = json.loads(F.read_text(encoding="utf-8"))
a = data["actors"]["buh"]
for k in ("engine", "style"):
    a.pop(k, None)
a.update(voice="Maria - confidence and charisma (ru-moscow)", voice_id="EluqMkib8uTv2OpkCbcD",
         model="eleven_v3", stability=0.5)
b = data["reactions"]["buh"]
for kind, texts in TEXTS.items():
    assert len(b[kind]) == len(texts), kind
    for ln, t in zip(b[kind], texts):
        ln["text"] = t
F.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("тексты и голос обновлены, озвучиваю...")
used = 0
for kind, lines in b.items():
    if kind.startswith("_"):
        continue
    used += ge.voice_lines(ge.ROOT / "audio" / "reactions" / "buh" / kind, lines, data, False, f"buh/{kind}")
print(f"потрачено символов ElevenLabs: {used}")
