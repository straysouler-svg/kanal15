"""2026-11-04: песни в кабины новых водителей. Рустам — узбекская народная с дутаром, Бахтияр — узбекская попса.
Тексты свои, в запросе только описание стиля (без имён артистов). ~$0.08 за песню (Lyria 3 через OpenRouter)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_songs_lib as lib  # noqa: E402

SONGS = {
    "dutar_lyria_oppok": (
        "Uzbek folk song: a two-string dutar leads, doira frame drum, a soft nay flute, a warm middle-aged male voice "
        "with Central Asian melisma, unhurried and heartfelt, like a song at a family wedding in Samarkand. "
        "Sung in Russian with a few Uzbek words.",
        """[Verse 1]
Белый мой Оппок, дорога далека,
Курагой пахнет кабина, как базар издалека,
Казан за сиденьем, пиала у окна,
Дома ждёт Мадина, айва уже красна.
[Chorus]
Ехай, ехай, Оппок, по чужой стороне,
Самарканд мой голубой снится ночью мне,
Где бы ни стоял я — там накрою дастархан,
Гость в доме — Бог в доме, заходи, братан.
[Verse 2]
Рис помою семь раз, морковь соломкой нарежу,
Брат умчался вперёд — догоню, не перебежит,
Пусть дорога длинна, как песня у костра,
Плов поспеет к рассвету, а там и домой пора.
[Chorus]
Ехай, ехай, Оппок, по чужой стороне,
Самарканд мой голубой снится ночью мне,
Где бы ни стоял я — там накрою дастархан,
Гость в доме — Бог в доме, заходи, братан."""),
    "uzpop_lyria_kovboy": (
        "Modern Uzbek pop, upbeat dance track: catchy synth hook mixed with a doira groove and a dutar riff, "
        "a young energetic male voice, playful and bright, radio-friendly. Sung in Russian with an English chorus line.",
        """[Verse 1]
Синяя Скания, кредит на три года,
Мама в голосовом: надень куртку, погода!
Брат говорит — не гони, а я гоню вперёд,
Ковбой из Самарканда никогда не устаёт.
[Chorus]
Cowboy from Samarkand, еду на закат,
Сто двадцать подписчиков, и каждый мне рад,
Шляпа на сиденье, музыка в окно,
Америка далеко, но я доеду всё равно!
[Verse 2]
Ай эм э трак драйвер — седьмой урок прошёл,
Бургер против плова — брат опять ушёл,
Пахтакор забил, я кричу на весь эфир,
Вой-бо, какая жизнь, вой-бо, какой мир!
[Chorus]
Cowboy from Samarkand, еду на закат,
Сто двадцать подписчиков, и каждый мне рад,
Шляпа на сиденье, музыка в окно,
Америка далеко, но я доеду всё равно!"""),
}

if __name__ == "__main__":
    lib.run(SONGS)
