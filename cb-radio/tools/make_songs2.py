"""Batch 2 of cab radio songs (Lyria 3 Pro, ~$0.08 each): Ласточка, Лиса, Витёк, Сова (Есенин, PD), Янек.
Own lyrics (Есенин 1921 = public domain), no artist names. Skips songs already made."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_music as gm  # noqa: E402

M = gm.ROOT / "music"
SONGS = {
    "pop_lyria_lastochka": (
        "1990s Russian pop ballad (эстрада), confident warm female alto, piano, synth pads, electric guitar, "
        "steady mid-tempo drums, strong emotional chorus, sung in Russian.",
        """[Verse 1]
Я сама за рулём, я сама по себе,
Двадцать лет по дорогам, по зимней земле,
Говорили: не сможешь. Ну что ж, посмотри —
Я сама довезу до своей до зари.
[Chorus]
Ласточка, ласточка, лети,
Сколько б ни было в жизни пути,
Не догнать, не поймать, не вернуть,
Мой полёт — это мой путь.
[Verse 2]
На панели цветы, в телефоне — она,
Дочка в Питере ждёт, у неё там весна,
Я ей шлю по ночам свой привет через дождь:
Мама рядом, родная, ты меня подождёшь.
[Chorus]
Ласточка, ласточка, лети,
Сколько б ни было в жизни пути,
Не догнать, не поймать, не вернуть,
Мой полёт — это мой путь."""),
    "dance_lyria_lisa": (
        "1990s Russian eurodance, 130 bpm: bright female vocal, punchy synth bass, supersaw chords, four-on-the-floor "
        "kick, catchy chant chorus, night club energy, sung in Russian.",
        """[Verse 1]
Ночь, неон, заправка, кофе,
Рыжий тягач на автостраде,
Кто там едет — сразу в профиль,
Я лиса, я на параде!
[Chorus]
Лиса, лиса, ночная полоса,
Лиса, лиса, горят мои глаза,
Догони, если сумеешь,
Ты меня не одолеешь!
[Verse 2]
Волки воют по эфиру,
Кто-то просит: тише, тише,
А я делаю погромче,
Пусть вся трасса нас услышит!
[Chorus]
Лиса, лиса, ночная полоса,
Лиса, лиса, горят мои глаза,
Догони, если сумеешь,
Ты меня не одолеешь!"""),
    "svadba_lyria_vitek": (
        "Cheerful Russian wedding pop song (свадебная попса), upbeat: energetic young male vocal, accordion, "
        "synth brass, bouncy bass, party drums, crowd shouts, sung in Russian.",
        """[Verse 1]
Костюм в чехле, ботинки в коробке,
Галстук забыл — ну что за беда,
Мама звонит уже в пятой попытке,
Брат женится — я лечу туда!
[Chorus]
Горько! Горько! Кричат за столом,
Я успеваю, я где-то в пути,
Горько! Горько! Мы всё переждём,
Только бы к тосту успеть подойти!
[Verse 2]
Сто километров, ещё девяносто,
Тост не написан, но я сочиню,
Если опоздаю — это не просто,
Мама убьёт, а потом и родню!
[Chorus]
Горько! Горько! Кричат за столом,
Я успеваю, я где-то в пути,
Горько! Горько! Мы всё переждём,
Только бы к тосту успеть подойти!"""),
    "romance_lyria_esenin": (
        "Russian romance (русский романс), slow and tender: warm female mezzo-soprano, nylon string guitar, "
        "a soft cello, intimate late-night mood, sung in Russian.",
        """[Verse 1]
Не жалею, не зову, не плачу,
Всё пройдёт, как с белых яблонь дым.
Увяданья золотом охваченный,
Я не буду больше молодым.
[Verse 2]
Ты теперь не так уж будешь биться,
Сердце, тронутое холодком,
И страна берёзового ситца
Не заманит шляться босиком."""),
    "yanek_lyria_med": (
        "Gentle Belarusian folk song, slow: calm low male baritone, accordion, cimbalom (цимбалы), soft acoustic guitar, "
        "warm village mood, sung in Russian.",
        """[Verse 1]
Пчёлы спят до весны под снегами,
Улей дремлет в родимом саду,
Я везу этот лес за горами,
Я вернусь, я весною приду.
[Chorus]
Мёд на донышке, хлеб да дорога,
Добрым словом согрета душа,
Тише едешь — дождёшься у порога,
Жизнь, как песня, светла, хороша.
[Verse 2]
Сын мне пишет про умные сети,
Я не понял, но горд за него,
Всё течёт, как вода на рассвете,
А любовь — это больше всего.
[Chorus]
Мёд на донышке, хлеб да дорога,
Добрым словом согрета душа,
Тише едешь — дождёшься у порога,
Жизнь, как песня, светла, хороша."""),
}

if __name__ == "__main__":
    import make_songs_lib as lib
    lib.run(SONGS)
