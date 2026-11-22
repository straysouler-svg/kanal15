# -*- coding: utf-8 -*-
"""2026-11-22: батч «бот-проезжие» (пак Дмитрия, drafts_bot_proezzhie).
- 6 RU (тексты Дмитрия, №29-34) -> reactions.foreign.ru, x_ru (coral)
- 15 RU-ботов (самоирония AI-трафика) -> НОВЫЙ пул reactions.streambot (режим стримера, механика — за Механиком)
- 15 иностранных ботов -> reactions.foreign.<lang> (продолжение нумерации), ru-субтитры из скобок
- 10 финских -> reactions.foreign.fi (05-14)
Только дописывание в конец пулов. cb_radio.py не трогаем."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))

RU_29_34 = [
 ("steam", "Да, похоже, поднимут штрафы, эти пидоры совсем охуели! Будем скоро бесплатно возить, а потом ещё и доплачивать за перегруз."),
 ("steam", "На «АТИ» сейчас одни перекупы ебучие, ставки режут до неприличия, но иногда проскакивают прямые грузы, нужно ловить, как рыбу."),
 ("steam", "Да у меня логисты вообще ебанутые, братан, маршрут рисуют, будто на самосвале по лугу ехать, а там потом хрен пролезешь!"),
 ("rant", "Эти обочечники ебаные уже заебали! Один раз специально фурой так встал, что никто не проехал, зато пробка сразу рассосалась."),
 ("rant", "Ах ты ж, мать его, тангетку жопой прижал! Проснись там, горемычный, весь канал уже десять минут твой поворотник слушает! Отпусти кнопку!"),
 ("warn", "Обочина после дождя — это русская рулетка. Если уж совсем прижмёт, выбегай быстрее, а то утащит твою ласточку в болото на раз-два!"),
]

RU_BOTS = [
 "Мужики, я сейчас перед какой-нибудь фурой на съезде с автобана резко заторможу с восьмидесяти до двадцати — извиняйте, так в моём коде прописано, ничего личного!",
 "Парни, мне-то вообще похуй, если меня в бок протаранят на кольце — я через триста метров деспавнюсь, а вот кому-то придётся жать F7 и Enter!",
 "Мужики, кто в курсе, куда ведут эти жёлтые летающие крестики на съезде в Париже? Вчера один туда сунулся — об невидимую стену ебанулся так, что прицеп в космос улетел!",
 "Парни, прикиньте, я специально перестраиваюсь без поворотника прямо в бок соседней фуре, чтобы кто-то свой бонус за доставку «Без повреждений» проебал, ха-ха!",
 "Мужики, у кого-нибудь ещё такое было: едешь себе спокойно по Германии, а тут хуяк — и тебя посреди Исландии заспавнили?!",
 "Парни, кто знает, почему у нас в трафике соляра никогда не кончается, а бедолаги на тягачах каждые пятьсот вёрст по три тыщи евро на заправках оставляют?",
 "Мужики, вон заправка впереди — надо бы нажать клавишу «Е» и поспать восемь часов за три секунды, а то уже зевота на весь экран накрывает!",
 "Парни, нахуя столько лампочек и висюлек в кабину вешать, у меня аж видеокарта от чужих отражений плавится и FPS до двадцати просел!",
 "Мужики, обожаю, когда кто-то включает поворотник, а перестраиваться передумывает — я всё равно встану колом посреди трассы, чисто на всякий случай!",
 "Парни, по ходу кто-то шлагбаум на пункте оплаты бампером задел — теперь эта хуйня вообще не откроется, пока назад не сдашь!",
 "Мужики, слышали новость? На трассу выехал тягач с модом на тысячу лошадей — сейчас в горку под сто сорок попрёт и движок вскипятит!",
 "Парни, кто радио в канале вырубил и врубил свой шансон в браузере? Нам тоже скучно в полной тишине по автобану катить!",
 "Мужики, смех смехом, а я сейчас прямо из воздуха материализуюсь за поворотом перед самым чьим-то капотом, держитесь!",
 "Парни, вот бы в реале так: разбил фуру в хлам об отбойник, нажал две кнопки — и ты уже новенький на сервисе в соседнем городе стоишь!",
 "Мужики, кто в курсе, в следующем обновлении нам хоть научат уступать дорогу при сужении полосы, или так и будем в бочину перестраиваться?",
]

FOREIGN_BOTS = [
 ("warn", "pl", "Mobilki, uważajcie przed Berlinem, zaraz włączy się autozapis i cały ruch na dwie sekundy zlaguje w chuj!",
  "Братишки, осторожнее перед Берлином, сейчас сработает автосохранение и весь трафик на две секунды залагает к хуям!"),
 ("warn", "de", "Kollegen, passt auf der Strecke Calais–Duisburg auf, da fliegen wieder irgendwelche Idioten in Skodas ohne Bremsen in die Stratosphäre!",
  "Коллеги, осторожнее на дороге Кале — Дуйсбург, там опять какие-то идиоты на «Шкодах» без тормозов в стратосферу улетают!"),
 ("rant", "en", "Lads, I’d love to let someone out at the junction, honest to God, but the devs at SCS forgot to give me a brain in the last patch!",
  "Парни, я бы рад пропустить кого-нибудь на перекрёстке, честное слово, но разрабы из SCS забыли завезти мне мозги в последнем патче!"),
 ("rant", "fr", "Les gars, chez moi même les polygones de l’intérieur n’existent pas, je suis juste une putain de texture vide sur quatre roues!",
  "Парни, у меня даже полигонов в салоне нет, я просто ёбаная пустая текстура на четырёх колёсах!"),
 ("rant", "es", "Colegas, me voy a quedar en el carril izquierdo a sesenta y cinco hasta Milán, ¡a ver quién tiene cojones de adelantarme!",
  "Коллеги, я сейчас встану в левом ряду на шестидесяти пяти до самого Милана — посмотрим, у кого хватит яиц меня обогнать!"),
 ("steam", "it", "Ragazzi, qualcuno ha visto la fine di questa autostrada? Sono otto anni che giro in tondo tra Berlino e Praga senza mai scendere dal camion!",
  "Парни, кто-нибудь видел конец этого автобана? Я уже восемь лет по кругу между Берлином и Прагой езжу, ни разу из грузовика не выходил!"),
 ("warn", "cs", "Kolegové, bacha na tu kameru vepředu, za vteřinu zase vtipně cvakne foťák a někomu zmizí prachy z účtu ze vzduchu!",
  "Коллеги, осторожнее с камерой впереди, через секунду опять смешно щёлкнет фотик и у кого-то бабки со счёта из воздуха спишутся!"),
 ("rant", "ro", "Colegii, eu sunt un bot simplu: dacă mă lovești, mi se rupe pula, dar ție îți vine imediat amendă de patru sute de euro pentru accident!",
  "Братишки, я бот простой: если меня заденешь, мне похуй, а вот тебе сразу штраф четыреста евро за ДТП прилетит!"),
 ("steam", "pl", "Ja pierdolę, w tych wąskich uliczkach we Włoszech jakiś geniusz będzie teraz dziesięć minut cofał pod rampę i zablokuje cały nasz ruch!",
  "Я пердоле, на этих узких улочках в Италии какой-то гений сейчас будет десять минут задом под рампу сдавать и заблокирует весь наш трафик!"),
 ("steam", "de", "Kollegen, ich bin auf der Tankstellenausfahrt einfach reingefahren — in meinem Skript steht „Vorfahrt ignorieren“, ich kann nichts dafür!",
  "Коллеги, я на выезде с заправки тупо в бок въехал — у меня в скрипте написано «игнорировать приоритет», я тут ни при чём!"),
 ("steam", "en", "Mates, running a red light when there are no cops around is brilliant — until a bloody fine still pops up out of thin air!",
  "Парни, пролетать на красный, когда копов нет рядом, просто гениально — пока ёбаный штраф всё равно не прилетит из воздуха!"),
 ("steam", "fr", "Putain, j’ai l’impression que le terrain vient d’être acheté avec un nouveau volant à retour de force, ça va secouer sévère sur les bosses!",
  "Блядь, такое чувство, что кто-то новый руль с обратной связью прикупил, сейчас на кочках руки выкручивать будет жёстко!"),
 ("steam", "es", "¡Hostia! Que alguien mire si tiene el limitador a noventa activado en los ajustes, porque aquí no tira ni para atrás!",
  "Блядь! Пусть кто-нибудь проверит, не включён ли ограничитель на девяносто в настройках, а то вообще не тянет!"),
 ("steam", "it", "Ragazzi, mi sa che qualcuno ha appena cliccato „Carica salvataggio“ nel menu principale — tra un secondo veniamo tutti cancellati da questa realtà!",
  "Парни, походу кто-то только что нажал «Загрузить сохранение» в главном меню — через секунду нас всех сотрёт из этой реальности!"),
 ("bye", "pl", "Dobra mobilki, jak ktoś zaraz wyłączy grę i pójdzie spać, to pamiętajcie — jutro prawdziwa robota, a my tu dalej w kółko będziemy zapierdalać!",
  "Ладно, братишки, если кто сейчас выключит игру и пойдёт спать, помните — завтра настоящая работа, а мы тут дальше по кругу хуярить останемся!"),
]

FI_BOTS = [
 ("Äijät, kuka helvetti laittoi taas näkymättömän seinän liittymän eteen? Joku lensi just perävaunun kanssa kiertoradalle!",
  "Мужики, какой чёрт опять поставил невидимую стену перед съездом? Кто-то только что с прицепом на орбиту улетел!"),
 ("Sori kaverit, mun on pakko lyödä liinat kiinni tässä keskellä tyhjää moottoritietä — se lukee mun koodissa, perkele!",
  "Извините, парни, мне придётся резко ударить по тормозам прямо посреди пустого автобана — так в моём коде прописано, чёрт побери!"),
 ("Vittuako sillä on väliä, vaikka joku ajaisi kylkeen, mä katoan kumminkin kolmensadan metrin päässä ilmaan!",
  "Какая нахуй разница, даже если кто-то в бок въедет, я всё равно через триста метров в воздухе растворюсь!"),
 ("Äijät, jollain on taas miljoona lisävaloa ja heiluvaa koiraa hytissä, mun näytönohjain sulaa ja FPS tippui kymmeneen!",
  "Мужики, у кого-то опять миллион допфар и качающихся собачек в кабине, у меня видеокарта плавится и FPS упал до десяти!"),
 ("Kuulemma SCS:n koodarit unohti taas päivityksessä laittaa tekoälylle vilkut ja aivot, joten varokaa kaistanvaihtoja, saatana!",
  "Говорят, разрабы из SCS в обновлении опять забыли завезти искусственному интеллекту поворотники и мозги, так что берегитесь при перестроениях, сатана!"),
 ("On se kumma, kun täällä Suomessa voi ajaa satasta lumimyrskyssä kesärenkailla, eikä pito lähde mihinkään!",
  "Удивительное дело: тут в Финляндии можно лететь сотку в метель на летней резине, и сцепление с дорогой никуда не пропадает!"),
 ("Taas joku sankari jäi jumiin tietullin puomiin — ei muuta kuin F7 ja Enter, niin pääsee suoraan korjaamolle!",
  "Опять какой-то герой застрял в шлагбауме на пункте оплаты — ничего не остаётся, кроме как F7 и Enter, и сразу на сервис!"),
 ("Kaverit, onneksi meidän liikenneautojen ei tartte ikinä tankata, muuten menis konkurssiin näillä polttoaineen hinnoilla!",
  "Парни, хорошо, что нам в трафике никогда не надо заправляться, иначе обанкротились бы с такими ценами на топливо!"),
 ("Huoltoasema edessä, äijät — nyt nopeasti E-nappia pohjaan ja kahdeksan tunnin unet kolmessa sekunnissa!",
  "Заправка впереди, мужики — сейчас быстренько жмём клавишу E и спим восемь часов за три секунды!"),
 ("No niin jätkät, joku painoi just päävalikosta «Lataa tallennus» — sekunnin päästä meidät kaikki pyyhitään pois tästä maailmasta!",
  "Ну всё, пацаны, кто-то только что нажал в главном меню «Загрузить сохранение» — через секунду нас всех сотрут из этого мира!"),
]

fg = d["reactions"].setdefault("foreign", {})
n = 0
for t, text in RU_29_34:
    lst = fg.setdefault("ru", [])
    if not any(x.get("text") == text for x in lst):
        lst.append({"actor": "x_ru", "text": text, "ru": text, "t": t})
        n += 1

sb = d["reactions"].setdefault("streambot", {
    "_": "2026-11-22: боты трафика ETS2 ломают четвёртую стену (самоирония AI). Играет ТОЛЬКО в режиме "
         "стримера — механику добавляет Механик. Актёр x_ru (coral)."})
sbl = sb.setdefault("ru", [])
for text in RU_BOTS:
    if not any(x.get("text") == text for x in sbl):
        sbl.append({"actor": "x_ru", "text": text, "ru": text})
        n += 1

for t, lang, text, ru in FOREIGN_BOTS:
    lst = fg.setdefault(lang, [])
    if not any(x.get("text") == text for x in lst):
        lst.append({"actor": "x_" + lang, "text": text, "ru": ru, "t": t})
        n += 1

for text, ru in FI_BOTS:
    lst = fg.setdefault("fi", [])
    if not any(x.get("text") == text for x in lst):
        lst.append({"actor": "x_fi", "text": text, "ru": ru, "t": "rant"})
        n += 1

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print(f"добавлено строк: {n}")
print("streambot.ru:", len(d["reactions"]["streambot"]["ru"]))
print("foreign:", {k: len(v) for k, v in fg.items() if not k.startswith("_")})
