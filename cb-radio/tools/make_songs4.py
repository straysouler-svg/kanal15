"""Сова: Lyria refused Esenin's poem (known lyrics filter, $0) -> our own romance in his spirit."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_songs_lib as lib  # noqa: E402

SONGS = {
    "romance_lyria_sova": (
        "Russian romance (русский романс), slow and tender: warm female mezzo-soprano, nylon string guitar, "
        "a soft cello, intimate late-night mood, sung in Russian.",
        """[Verse 1]
Над дорогой луна, как фонарь у крыльца,
Ветер тихо листает поля,
Я пою, чтоб не спать, и не помню конца
Этой песни, что знает земля.
[Chorus]
Ой ты, ночь, моя тихая ночь,
Не гони меня и не зови,
Я сама уезжаю прочь,
Обогретая словом любви.
[Verse 2]
У берёзы в окне белый ситцевый край,
Клён кивает мне вслед головой,
Ты, родная дорога, меня не пугай —
Я давно уже стала тобой.
[Chorus]
Ой ты, ночь, моя тихая ночь,
Не гони меня и не зови,
Я сама уезжаю прочь,
Обогретая словом любви."""),
}

if __name__ == "__main__":
    lib.run(SONGS)
