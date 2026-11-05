"""Copy the Lyria originals (stereo mp3, full quality) to cb-radio/Песни with readable names, to listen to on their own.
Never deletes anything; re-run any time after new songs are made."""
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "music" / "lyria_src"
OUT = ROOT / "Песни"
NAMES = {
    "chanson_lyria_kilometry": "Михалыч — Километры",
    "chanson_lyria_starushka": "Михалыч — Старушка",
    "chanson_lyria_shlagbaum": "Палыч — Шлагбаум",
    "folk_lyria_kolyosa": "Петровна — Колёса",
    "rock_lyria_kardan": "Кардан — Кардан крутится",
    "rock_light_lyria_arbuz": "Стас — Арбузы в кузове",
    "pop_lyria_lastochka": "Ласточка — Ласточка, лети",
    "dance_lyria_lisa": "Лиса — Ночная полоса",
    "svadba_lyria_vitek": "Витёк — Горько!",
    "romance_lyria_sova": "Сова — Ой ты, ночь",
    "yanek_lyria_med": "Янек — Мёд на донышке",
    "ten_lyria_ne_spi": "Тень — Не спи, водитель ночной",
    "ten_lyria_sto_metrov": "Тень — Свет на сто метров",
    "dutar_lyria_oppok": "Самарканд — Оппок",
    "uzpop_lyria_kovboy": "Ковбой — Cowboy from Samarkand",
}
OUT.mkdir(exist_ok=True)
n = 0
for f in sorted(SRC.glob("*.*")):
    dst = OUT / (NAMES.get(f.stem, f.stem) + f.suffix)
    if not dst.exists():
        shutil.copy2(f, dst)
        n += 1
test = ROOT / "music" / "lyria_test" / "clip_chanson.mp3"
if test.exists() and not (OUT / "_проба — шансон 30 сек.mp3").exists():
    shutil.copy2(test, OUT / "_проба — шансон 30 сек.mp3")
print(f"скопировано {n}, всего в папке: {len(list(OUT.glob('*.mp3')))} -> {OUT}")
