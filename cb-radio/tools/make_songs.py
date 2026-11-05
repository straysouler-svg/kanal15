"""Batch 1 of cab radio songs (Lyria 3 Pro via OpenRouter, ~$0.08 each). Our own lyrics, no artist names.
Skips songs already made. -> music/<name>.mp3 + mono 22.05 kHz wav for cab_extras."""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_music as gm  # noqa: E402

M = gm.ROOT / "music"
SONGS = {
    "chanson_lyria_kilometry": (
        "Russian chanson (русский шансон) ballad, 1990s trucker cassette sound: hoarse warm male baritone, acoustic guitar, "
        "accordion, soft synth strings, slow sentimental tempo, sung in Russian.",
        """[Verse 1]
Снова трасса мне стелет дорогу,
Фонари провожают в ночи,
Я у Бога прошу понемногу:
Довези, а потом помолчи.
[Chorus]
Километры, мои километры,
Вы как годы летите назад,
Только ветер, попутный мой ветер
Знает, как я спешу к вам назад.
[Verse 2]
На стекле отпечаток рассвета,
В старом термосе стынет мой чай,
Дома ждут меня с прошлого лета,
Говорят: возвращайся, встречай.
[Chorus]
Километры, мои километры,
Вы как годы летите назад,
Только ветер, попутный мой ветер
Знает, как я спешу к вам назад."""),
    "chanson_lyria_starushka": (
        "Upbeat Russian chanson with a light swing, 1990s restaurant band sound: gravelly male voice, accordion, "
        "acoustic guitar, bass, simple drums, warm and humorous, sung in Russian.",
        """[Verse 1]
Старушка моя, ты скрипишь, как и я,
Два миллиона, а всё у руля,
Мы с тобой повидали полсвета, подруга,
Нам дорога — и дом, и семья.
[Chorus]
Ой, дорога, дорога моя,
Без тебя мне и жизнь не своя,
Пусть мотор барахлит, лишь бы сердце не спит,
Довезём, дорогая моя.
[Verse 2]
Помнишь, как на границе стояли три дня,
Как в метель ты не бросила меня,
Мы с тобою ещё повоюем, родная,
Синей изолентой обмотав края.
[Chorus]
Ой, дорога, дорога моя,
Без тебя мне и жизнь не своя,
Пусть мотор барахлит, лишь бы сердце не спит,
Довезём, дорогая моя."""),
    "chanson_lyria_shlagbaum": (
        "Ironic Russian chanson, mid tempo: tired confident male baritone, nylon guitar, accordion, bass, brushed drums, "
        "a bit of self-irony, sung in Russian.",
        """[Verse 1]
Двадцать лет я стоял с полосатым жезлом,
Всех ловил, кто спешил за рулём,
А теперь я и сам по ночам на трассе,
И квитанции копятся в бардачке моём.
[Chorus]
Эх, судьба — полосатый шлагбаум,
То поднимет, то снова закрыт,
Я на трассе теперь не начальник,
Только совесть со мной говорит.
[Verse 2]
Мне бывает не спится, я слушаю сканер,
Там знакомые голоса,
А я еду себе потихоньку,
И гляжу, как светлеют небеса.
[Chorus]
Эх, судьба — полосатый шлагбаум,
То поднимет, то снова закрыт,
Я на трассе теперь не начальник,
Только совесть со мной говорит."""),
    "folk_lyria_kolyosa": (
        "1990s Russian folk-pop (народная эстрада): bright female folk vocal with open-throat village singing, "
        "accordion, balalaika, synthesizer, danceable drum machine, cheerful and heartfelt, sung in Russian.",
        """[Verse 1]
Ой, рябина у дороги,
Ой, калина у ворот,
Провожала я в дороги
Поезда за годом год.
[Chorus]
Колёса, колёса, стучите, колёса,
Несите меня по родной стороне,
А вслед мне берёзы да синие росы,
И песня, что сердце согреет во мне.
[Verse 2]
Чай в стакане с подстаканником,
Ложечка звенит, звенит,
Кто в пути — тот мне не странник,
Всех накормит, всех простит.
[Chorus]
Колёса, колёса, стучите, колёса,
Несите меня по родной стороне,
А вслед мне берёзы да синие росы,
И песня, что сердце согреет во мне."""),
    "rock_lyria_kardan": (
        "2000s Russian rock band, energetic: raspy male lead vocal, distorted electric guitars, driving bass, "
        "big live drums, anthemic chorus, sung in Russian.",
        """[Verse 1]
Ночь, асфальт и восемь цилиндров,
Фары рвут темноту, как струна,
Я не помню ни лиц, ни мотивов,
Только трасса и только луна.
[Chorus]
Кардан крутится — значит, живой!
Значит, утро придёт за спиной!
Громче, громче, пусть слышит весь мир:
Это мой рок-н-ролльный эфир!
[Verse 2]
Двенадцать человек в этом зале,
Двенадцать сердец на весь свет,
Нас когда-то по радио крутили,
А теперь мы крутим рассвет.
[Chorus]
Кардан крутится — значит, живой!
Значит, утро придёт за спиной!
Громче, громче, пусть слышит весь мир:
Это мой рок-н-ролльный эфир!"""),
    "rock_light_lyria_arbuz": (
        "Modern Russian pop-rock, upbeat summer road song: young male vocal, bright electric guitars, punchy drums, "
        "catchy singalong chorus, sung in Russian.",
        """[Verse 1]
Арбузы в кузове, мечты в голове,
Сорок просмотров — уже успех,
Я еду к морю, ну или к тебе,
Камера пишет, и в кадре смех.
[Chorus]
Подписывайся, ставь лайк, лови волну,
Я по трассе лечу в свою весну,
Пусть кредит, пусть дождик, ну и пусть,
Я вернусь, я обязательно вернусь!
[Verse 2]
Зарядка потерялась, тапки в пути,
Батя по рации учит жить,
А я смеюсь и знаю: впереди
Всё, что не страшно и стоит любить.
[Chorus]
Подписывайся, ставь лайк, лови волну,
Я по трассе лечу в свою весну,
Пусть кредит, пусть дождик, ну и пусть,
Я вернусь, я обязательно вернусь!"""),
}


def to_wav(mp3, wav):
    x, sr = sf.read(mp3, dtype="float32", always_2d=True)
    x = x.mean(axis=1)
    from math import gcd
    g = gcd(22050, sr)
    y = resample_poly(x, 22050 // g, sr // g).astype(np.float32)
    sf.write(wav, y / (np.max(np.abs(y)) + 1e-9) * 0.9, 22050, subtype="PCM_16")
    return len(y) / 22050


total = 0.0
for name, (style, lyrics) in SONGS.items():
    if (M / f"{name}.wav").exists():
        continue
    data, fmt, text, cost = gm.generate("song", f"{style}\nLyrics:\n{lyrics}")
    total += cost
    if not data:
        print(f"{name}: звука нет (${cost:.3f}) {text[:200]!r}", flush=True)
        continue
    mp3 = M / "lyria_src" / f"{name}.{gm.ext_of(data, fmt)}"
    mp3.parent.mkdir(exist_ok=True)
    mp3.write_bytes(data)
    dur = to_wav(mp3, M / f"{name}.wav")
    print(f"{name}: {dur / 60:.1f} мин, ${cost:.3f}", flush=True)
print(f"итого ${total:.3f}")
