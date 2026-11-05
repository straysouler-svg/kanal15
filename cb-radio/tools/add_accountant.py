"""One-off: the company accountant who sends you a voice message (phone, not CB) after a fine.
Actor 'buh' (extra, fx=phone); reactions.buh.<kind>. Kinds follow the SDK offence ids."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))
d["actors"].setdefault("buh", {
    "name": "Людмила Сергеевна (бухгалтерия)", "extra": True, "fx": "phone", "engine": "gpt-audio",
    "voice": "shimmer", "voice_id": "gpt-audio:shimmer",
    "style": "строгая женщина-бухгалтер за пятьдесят, записывает голосовое сообщение в мессенджере, раздражённая, "
             "но вежливая, говорит чётко и быстро, считает каждую копейку",
    "about": "бухгалтер транспортной компании; присылает голосовое после твоего штрафа: смета, статьи расходов",
    "phrases": []})
B = d["reactions"].setdefault("buh", {"_": "voice message from the accountant after a fine (phone sound, not CB). "
                                            "kind = fine offence; 'escalation' from the 3rd fine in a game day."})
L = lambda t: {"actor": "buh", "text": t}  # noqa: E731
lines = {
    "speeding": ["Железяка, это Людмила Сергеевна, бухгалтерия. Пришёл штраф за превышение скорости. Мы из сметы выбиваемся! Езжайте по знакам, пожалуйста.",
                 "Железяка, опять превышение?! (вздыхает) Я уже не знаю, по какой статье это проводить!"],
    "red_signal": ["Железяка, бухгалтерия. Штраф за красный свет. Красный, Железяка! Это даже не скорость, это светофор!"],
    "crash": ["Железяка, мне пришёл штраф за аварию. Вы живы? Хорошо. А теперь объясните, кто будет платить за ремонт?"],
    "no_lights": ["Железяка, штраф за езду без света. Включите фары. Это бесплатно, в отличие от штрафа."],
    "avoid_sleeping": ["Железяка, штраф за нарушение режима отдыха. Поспите! Сон, между прочим, штрафом не облагается."],
    "wrong_way": ["Железяка, штраф за встречку?! Я даже спрашивать боюсь, как вы туда попали."],
    "generic": ["Железяка, бухгалтерия беспокоит. Ещё один штраф. Смета трещит по швам."],
    "escalation": ["Железяка! Это уже третий штраф за день! Я директору докладную пишу. (вздыхает) И себе валерьянку.",
                   "Железяка, если так пойдёт дальше, премии не будет. Ни у вас, ни у меня."],
}
for kind, ts in lines.items():
    lst = B.setdefault(kind, [])
    for t in ts:
        if L(t) not in lst:
            lst.append(L(t))

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print("accountant:", {k: len(v) for k, v in B.items() if not k.startswith("_")})
