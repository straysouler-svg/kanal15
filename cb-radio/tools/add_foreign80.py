# -*- coding: utf-8 -*-
"""2026-11-22: партия «проезжие-европейцы» из drafts_foreign80 (одобрено Дмитрием).
1) Филлеры: из 80 отобрано 39 самодостаточных (без висящих вопросов); поле "t" = тип
   (warn/radio/thanks/bye/rant/steam) для подбора ответа наших. Мат в оригиналах — решение Дмитрия.
2) Наши отвечают: реакции foreign_ans/<lang>__<тип> (вложенные пулы -> плоские каталоги).
   Расклад: Янек pl/en, Профессор de/en, Сова fr, Рустам и Бахтияр tr. Проверено Opus.
3) Новые проезжие: x_en (coral), x_ro (nova). Только дописывание."""
import json
from pathlib import Path

F = Path(__file__).resolve().parents[1] / "phrases" / "level3_eleven.json"
d = json.loads(F.read_text(encoding="utf-8"))

CAB = {"_": "проезжий", "road_db": -18, "window": 0.5, "wind_db": -21, "traffic": 0.1, "traffic_db": -18,
       "horn_chance": 0.1, "engine_db": -25, "rpm": 1450}
RADIO = {"noise_db": -27, "drive": 2.0, "roger_beep": False}

NEW_ACTORS = {
    "x_en": {"lang": "en", "voice": "coral",
             "style": "british trucker on CB radio, dry humour, motorway chatter, friendly"},
    "x_ro": {"lang": "ro", "voice": "nova",
             "style": "romanian long-haul driver, warm, chatty, complains with a laugh"},
}
for key, v in NEW_ACTORS.items():
    d["actors"].setdefault(key, {
        "name": f"иностранец ({v['lang']})", "extra": True, "lang": v["lang"], "engine": "gpt-audio",
        "voice": v["voice"], "voice_id": f"gpt-audio:{v['voice']}:{v['lang']}", "style": v["style"],
        "radio": dict(RADIO), "cab": dict(CAB), "phrases": []})

# (тип, язык, текст, ru-субтитр из подборки Дмитрия)
FILLERS = [
 ("steam", "de", "Kollegen auf der A2 Richtung Hannover, was ist denn da für eine Scheiße los, warum stehen wir hier komplett?",
  "Коллеги на А2 в сторону Ганновера, что там за пиздец творится, почему мы наглухо встали?"),
 ("steam", "it", "Colleghi sulla A1 verso Bologna, ma che cazzo è successo là davanti, c’è una coda della madonna?",
  "Коллеги на А1 в сторону Болоньи, что там впереди случилось, пробка нереальная?"),
 ("steam", "pl", "Koledzy z przeciwka, na obwodnicy Poznania misiaczki suszą czy można lecieć ile fabryka dała?",
  "Ребята со встречки, на объездной Познани «мишки» с феном стоят или можно лететь?"),
 ("warn", "de", "Achtung Gegenverkehr auf der A8, am Irschenberg ist Blitzeis, fahrt vorsichtig, sonst landet ihr im Graben, verdammt!",
  "Внимание встречке на А8, на подъёме Иршенберг чёрный лёд, езжайте аккуратно, иначе в кювет!"),
 ("warn", "fr", "Attention les gars sur l’A10, il y a un con qui a perdu un pneu au milieu de la voie de droite, ouvrez l’œil!",
  "Внимание, парни на А10, какой-то болван потерял колесо посреди правой полосы, глядите в оба!"),
 ("warn", "de", "Kollegen, auf der A3 bei Würzburg steht die BAG auf dem Parkplatz und zieht alles raus, was nach Ostblock aussieht!",
  "Коллеги, на А3 возле Вюрцбурга транспортники на парковке выдёргивают всех, кто похож на Восточную Европу!"),
 ("steam", "fr", "Putain, encore un connard qui s’est garé en travers et qui bloque trois places, bouge ton cul, mec!",
  "Блин, опять какой-то мудак встал поперёк и три места занял, убери свою жопу, мужик!"),
 ("warn", "de", "Kollegen, auf dem Parkplatz hier wird gerade wieder Diesel geklaut, passt auf eure Tanks auf, die Schweine sind unterwegs!",
  "Коллеги, на этой стоянке прямо сейчас соляру сливают, следите за баками, эти свиньи вышли на охоту!"),
 ("radio", "pl", "Próba radia, mobilki, jak mnie słychać, nie pierdzi mi grucha?",
  "Проверка рации, братишки, как меня слышно, тангета не пердит?"),
 ("warn", "de", "Kollegen, an dem weißen DAF vor mir qualmt es hinten rechts wie Sau, mach mal langsam, deine Bremse hängt fest!",
  "Коллеги, у белого ДАФа передо мной сзади справа дымит как чёрт, притормози, тормоза заклинило!"),
 ("radio", "en", "Radio check, breaker one-nine, how’s this rig getting out today, loud and proud or sounding like a wet fart?",
  "Проверка связи, как меня слышно — громко и чётко или как мокрый пердёж?"),
 ("warn", "fr", "Eh le Scania bleu devant moi, t’as une sangle qui traîne par terre côté gauche, arrête-toi avant de tout arracher!",
  "Эй, на синей «Скании» передо мной, у тебя ремень по земле волочится слева, тормози, пока всё не оторвало!"),
 ("warn", "de", "Hey Kollege mit dem polnischen Kennzeichen, deine hintere Tür vom Auflieger ist nur halb zu, gleich fliegt dir die ganze Ladung raus!",
  "Эй, коллега с польскими номерами, у тебя задняя дверь прицепа наполовину открыта, сейчас весь груз вылетит!"),
 ("warn", "en", "Mate in the red Volvo, your nearside trailer tyre is looking proper flat, pull over at the next lay-by before it blows!",
  "Братан на красном «Вольво», у тебя левое колесо на прицепе спустило, сверни в карман, пока не рвануло!"),
 ("steam", "fr", "Putain de merde, j’ai une durite de turbo qui vient de péter en pleine côte, je me traîne à vingt à l’heure, désolé les gars!",
  "Ёб, у меня патрубок турбины рванул прямо на подъёме, ползу двадцать в час, извините, парни!"),
 ("rant", "es", "¡Joder! ¿Quién tiene el micro pisado en el canal 19? Llevamos diez minutos escuchando tu música de mierda!",
  "Бля! У кого микрофон зажато в 19-м канале? Уже десять минут слушаем твою музыку!"),
 ("steam", "de", "Kollegen, meine Standheizung qualmt wie eine Dampflok und stinkt nach unverbranntem Diesel, fliegt mir die Scheiße gleich um die Ohren?",
  "Коллеги, моя автономка дымит как паровоз и воняет солярой, эта херня мне не рванёт в уши?"),
 ("steam", "en", "Tell you what, mates, these office wankers have no clue — they gave me three drops in central London on a Friday afternoon!",
  "Скажу я вам, парни, эти офисные придурки без мозгов — дали мне три выгрузки в центре Лондона в пятницу вечером!"),
 ("steam", "fr", "Les gars, ça fait trois semaines que je suis sur la route, j’en ai plein le cul, vivement vendredi que je rentre voir ma femme!",
  "Парни, я уже три недели в рейсе, всё заебло, скорее бы пятница, домой к жене!"),
 ("steam", "pl", "Kurwa mać, stoję na rozładunku pod Lidlem już szóstą godzinę, te niemieckie magazyny to jest jakiś pierdolony żart!",
  "Курва мать, стою на выгрузке под «Лидлом» шестой час, эти немецкие склады — ёбаный цирк!"),
 ("steam", "en", "Honestly lads, if they bring in any more of this self-driving bollocks, I’m hanging up my keys and opening a pub!",
  "Честно, парни, если введут ещё больше этой беспилотной хуйни, вешаю ключи на гвоздь и открываю паб!"),
 ("steam", "fr", "Putain, j’ai plus que dix minutes de conduite et le client veut pas me laisser dormir dans sa cour, quel bande d’enfoirés!",
  "Бля, у меня десять минут вождения осталось, а клиент не пускает переночевать на территории, ублюдки!"),
 ("steam", "it", "Colleghi, con questo nuovo tachigrafo intelligente ci hanno proprio rotto i coglioni, non si può neanche più fare un metro per cercare parcheggio!",
  "Коллеги, с этим новым умным тахографом яйца открутили, даже метр нельзя проехать парковку искать!"),
 ("rant", "pl", "Ej, baranie w osobówce, gdzie się kurwa wpierdalasz przed czterdzieści ton, życia nie szanujesz?!",
  "Эй, баран на легковушке, куда ты лезешь перед сорока тоннами, жизнь не ценишь?!"),
 ("rant", "de", "Sag mal, du Arschloch im BMW, hast du deine Blinker beim Kauf nicht mitbezahlt oder bist du einfach nur zu blöd zum Fahren?!",
  "Скажи-ка, мудак на БМВ, ты поворотники не оплатил или просто тупой?!"),
 ("rant", "en", "OI! You absolute wanker in the Audi, stop brake-checking me before I turn your boot into your glovebox!",
  "Эй! Конченый придурок на «Ауди», хватит оттормаживаться передо мной!"),
 ("rant", "fr", "Eh le connard en camionnette blanche, décale-toi ou accélère, ça fait trois kilomètres que tu me bloques dans la côte, putain!",
  "Эй, мудак на белом фургоне, сдвинься или газу дай, три километра на подъёме меня держишь!"),
 ("rant", "es", "¡Me cago en la leche! ¿Pero qué hace ese gilipollas adelantando por el arcén con la que está cayendo?!",
  "Ёб твою! Что творит этот придурок, обгоняя по обочине в такой ливень?!"),
 ("rant", "it", "Ma vaffanculo va, pezzo di merda, ti butti dentro senza guardare gli specchietti, la patente l’hai trovata nelle patatine?!",
  "Да пошёл ты, кусок говна, перестраиваешься не глядя, права в чипсах нашёл?!"),
 ("rant", "pl", "Koledzy na dużych, po chuj się wyprzedzacie pod górkę przez pięć kilometrów, zróbcie trochę miejsca bo nas wszystkich szlag trafi!",
  "Ребята на фурах, нахрена вы обгоняетесь в горку пять километров, дайте места, а то нас всех кондратий хватит!"),
 ("thanks", "de", "Danke dir Kollege fürs Reinlassen und Blinken, komm gut nach Hause und lass dich nicht ärgern!",
  "Спасибо тебе, коллега, что пустил и мигнул, доберись хорошо до дома!"),
 ("rant", "cs", "Ty vole, kdo tam zase chrápe do toho mikrofonu, probuďte toho medvěda, nedá se to poslouchat!",
  "Ёб твою, кто там опять храпит в микрофон, разбудите этого медведя, слушать невозможно!"),
 ("thanks", "en", "Cheers mate, appreciate the flash, keep the shiny side up and the greasy side down, catch you on the flip-flop!",
  "От души, братан, спасибо что моргнул, держи крышу сверху, а колёса снизу, услышимся!"),
 ("rant", "fr", "Les gars, y a un touriste en camping-car qui roule à soixante sur l’autoroute, on dirait qu’il cherche des champignons!",
  "Парни, тут турист на автодоме едет шестьдесят по автобану, будто грибы ищет!"),
 ("rant", "ro", "Băi colegule cu numărul de Bulgaria, dă-i bice la cotețul ăla că ne-ai adormit pe toți în spatele tău!",
  "Эй, коллега с болгарскими номерами, поддай газку своей колымаге, а то мы все за тобой уснули!"),
 ("rant", "es", "¡Oye! Que alguien le diga al del camión azul que lleva las luces largas puestas y nos está dejando ciegos a todos, hostia!",
  "Эй! Пусть кто-нибудь скажет тому на синем грузовике, что он с дальним едет и всех слепит!"),
 ("bye", "it", "Ragazzi, io esco qui per fare la nanna, buonanotte a tutti i lupi della strada e occhi aperti che la notte è lunga!",
  "Парни, я сворачиваю на боковую, спокойной ночи всем волкам дороги, глядите в оба!"),
 ("bye", "de", "So Kollegen, ich mach jetzt Feierabend für heute, wünsche euch allen eine schrott- und gebührenfreie Fahrt, haut rein!",
  "Ну всё, коллеги, я на сегодня завязываю, желаю всем дороги без аварий и штрафов, бывайте!"),
 ("bye", "pl", "Dobra mobilki, ja zjeżdżam na bazę, szerokości i przyczepności wszystkim, do następnego na kanale!",
  "Ладно, братишки, я сворачиваю на базу, всем шершавенькой и сцепления, до следующего в канале!"),
]

ANSWERS = {
 "pl": {
  "radio": [("yanek", "Ładnie słychać, czysto leci, piątka z radiem!", "Слышно отлично, чисто идёт, пятюня за связь!")],
  "thanks": [("yanek", "Nie ma za co, bracie, szerokiej i do zobaczenia na obwodnicy!",
              "Не за что, брат, широкой дороги, увидимся на объездной!")],
  "warn": [("yanek", "Dzięki za info, kurna, zwalniam i się rozglądam!",
            "Спасибо за инфу, притормаживаю и смотрю в оба!")],
  "bye": [("yanek", "No to do zobaczenia, kolego, piątka i szerokiej!",
           "Ну до встречи, коллега, пятюня и широкой!")],
  "rant": [("yanek", "U nas to samo, kurwa, jeszcze się taki nie urodził, co by ich poukładał!",
            "У нас то же самое, ещё такой не родился, кто бы их расселил по местам!")],
  "steam": [("yanek", "Trzymaj się, bracie, każdy to przechodzi, kurwa, taka robota!",
             "Держись, брат, каждый через это проходит, такая работа!")],
 },
 "en": {
  "radio": [("yanek", "Loud and clear, brother, five by five!", "Громко и чётко, брат, пять на пять!"),
            ("professor", "Got you loud and clear, driver, coming in five by five.",
             "Слышу вас громко и чётко, коллега, пять на пять.")],
  "thanks": [("yanek", "Anytime, driver, keep the shiny side up!", "Всегда пожалуйста, водила, держи крышу сверху!")],
  "warn": [("yanek", "Copy that, backing off, eyes peeled!", "Принял, сбрасываю, глазки открыл!"),
           ("professor", "Ten-four, I'll keep my eyes peeled.", "Принято, смотрю в оба.")],
  "bye": [("yanek", "Catch you on the flip side, driver, keep 'em between the ditches!",
           "До связи, водила, держись между кюветами!"),
          ("professor", "Safe travels, driver, and mind your speed.",
           "Ровных дорог, коллега, и смотрите на спидометр.")],
  "rant": [("professor", "Same circus here, driver. The regs just keep piling up.",
            "У нас тот же цирк, коллега. Правила только множатся.")],
  "steam": [("professor", "Same circus here, driver. The regs just keep piling up.",
             "У нас тот же цирк, коллега. Правила только множатся.")],
 },
 "de": {
  "radio": [("professor", "Laut und klar, Kollege, kommt sauber rein.", "Громко и чётко, коллега, чисто идёт.")],
  "warn": [("professor", "Danke für die Warnung, ich pass auf, fahr vorsichtig.",
            "Спасибо за предупреждение, буду внимателен, поеду осторожно.")],
  "rant": [("professor", "Ist überall dasselbe, Kollege, wird nicht besser der Job.",
            "Везде то же самое, коллега, профессия не становится легче.")],
  "bye": [("professor", "Gute Fahrt, Kollege, bleib unterm Radar.",
           "Хорошей дороги, коллега, и держитесь под радаром.")],
  "thanks": [("professor", "Kein Ding, Kollege, man hilft sich auf der Piste.",
              "Не за что, коллега, на трассе друг другу помогают.")],
  "steam": [("professor", "Ist überall dasselbe, Kollege, wird nicht besser der Job.",
             "Везде то же самое, коллега, профессия не становится легче.")],
 },
 "fr": {
  "radio": [("sova", "Tu passes nickel, cinq sur cinq, mon ami.", "Тебя слышно отлично, пять на пять, друг мой.")],
  "warn": [("sova", "Merci pour le tuyau, je lève le pied.", "Спасибо за наводку, сбавляю.")],
  "rant": [("sova", "C'est partout pareil, hélas... Courage, collègue.",
            "Везде так же, увы... Держись, коллега.")],
  "bye": [("sova", "Bonne route, et bonne nuit si tu roules de nuit.",
           "Доброго пути, и спокойной ночи, если едешь до темнота.")],
  "thanks": [("sova", "Y'a pas de quoi, entre routiers on s'entraide.",
              "Не за что, мы, дальнобойщики, друг другу помощники.")],
  "steam": [("sova", "C'est partout pareil, hélas... Courage, collègue.",
             "Везде так же, увы... Держись, коллега.")],
 },
 "tr": {
  "warn": [("rustam", "Sağ ol kardeşim, dikkat ediyorum!", "Спасибо, братишка, смотрю в оба!"),
           ("bahti", "Tamam abi, yavaşlıyorum!", "Понял, брат, притормаживаю!")],
  "radio": [("rustam", "Net geliyorsun, beş üstüne beş!", "Чётко слышу, пять на пять!"),
            ("bahti", "Seni duyuyorum abi, temiz geliyor!", "Слышу тебя, брат, чисто идёт!")],
  "bye": [("rustam", "Görüşürüz kardeşim, kazasız belasız!", "До встречи, братишка, без аварий!")],
  "thanks": [("rustam", "Rica ederim kardeşim, yolun açık olsun!", "Не за что, братишка, пусть дорога будет свободной!")],
  "rant": [("rustam", "Bizde de aynı hikaye, vay be, bu işler hep böyle!",
            "У нас та же история, вай, всегда так!")],
  "steam": [("bahti", "Tam anlamadım ama... çay var, idare ederiz!",
             "Не всё понял, но... чай есть, справимся!")],
 },
}

fg = d["reactions"].setdefault("foreign", {})
n_fill = 0
for t, lang, text, ru in FILLERS:
    lst = fg.setdefault(lang, [])
    item = {"actor": "x_" + lang, "text": text, "ru": ru, "t": t}
    if not any(x.get("text") == text for x in lst):
        lst.append(item)
        n_fill += 1

fa = d["reactions"].setdefault("foreign_ans", {
    "_": "2026-11-22: наши водители отвечают проезжим (знают язык, в зоне, кулдаун). "
         "Вложенные пулы <lang>__<тип>: тип из поля t филлера (warn/radio/thanks/bye/rant/steam)."})
n_ans = 0
for lang, types in ANSWERS.items():
    sub = fa.setdefault(lang, {})
    for t, lines in types.items():
        tl = sub.setdefault(t, [])
        for actor, text, ru in lines:
            item = {"actor": actor, "text": text, "ru": ru}
            if item not in tl:
                tl.append(item)
                n_ans += 1

src = Path(__file__).with_name("add_night_cast.py").read_text(encoding="utf-8")
ns = {"json": json}
exec(src[src.index("def dump("):src.index("F.write_text(")], ns)
F.write_text(ns["dump"](d) + "\n", encoding="utf-8")
json.loads(F.read_text(encoding="utf-8"))
print(f"филлеров добавлено: {n_fill}, ответов добавлено: {n_ans}")
print("foreign:", {k: len(v) for k, v in fg.items() if not k.startswith("_")})
print("foreign_ans:", {k: {t: len(l) for t, l in v.items()} for k, v in fa.items() if not k.startswith("_")})
