"""Batch 3 (Lyria 3 Pro, ~$0.08 each): Тень - user wants «Наутилус Помпилиус или очень схожее».
No band name in the prompt (not allowed, and a copy isn't the goal): the style - 1980s Ural rock / Soviet new wave."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_songs_lib as lib  # noqa: E402

STYLE = ("1980s Soviet new wave / Ural rock (уральский рок): deep calm detached male baritone, cold chorus-effect "
         "electric guitar arpeggios, analog synth pads, drum machine, a lonely saxophone line, melancholic poetic "
         "night mood, sung in Russian.")
SONGS = {
    "ten_lyria_ne_spi": (STYLE, """[Verse 1]
Я еду ночью по чужой стране,
Где фары режут темноту на части,
И заяц снова бежит по стерне —
Он знает больше о дороге и о счастье.
[Chorus]
Не спи, не спи, водитель ночной,
Ты сам себе маяк и сам себе конвой,
Кофе остыл, и в зеркале — чужой,
Это я, это я, это я — живой.
[Verse 2]
Четвёртый стаканчик, третий час,
Радио шепчет на непонятном,
Я выбросил всё, что держало нас,
Оставил лишь путь — бесконечный, обратный.
[Chorus]
Не спи, не спи, водитель ночной,
Ты сам себе маяк и сам себе конвой,
Кофе остыл, и в зеркале — чужой,
Это я, это я, это я — живой."""),
    "ten_lyria_sto_metrov": (STYLE, """[Verse 1]
Фары светят на сто метров вперёд,
Дальше — ночь, и никто не ждёт,
Но я еду, и сто метров со мной,
Так и жизнь проходит стороной.
[Chorus]
Тише, тише, эфир молчит,
Только сердце в тишине стучит,
Зажигалка щёлкнет — и опять темно,
Я давно уже не здесь, давно.
[Verse 2]
Где-то там, за чертой рассвета,
Кто-то ищет меня по свету,
А я призрак в своём стекле,
Небритый, живой, на этой земле.
[Chorus]
Тише, тише, эфир молчит,
Только сердце в тишине стучит,
Зажигалка щёлкнет — и опять темно,
Я давно уже не здесь, давно."""),
}

if __name__ == "__main__":
    lib.run(SONGS)
