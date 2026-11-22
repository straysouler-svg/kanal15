# Проезжие иностранцы — новые ветки (черновик, 2026-11-22)

По образцу x_fi (полная ветка: foreign / foreign_reply / foreign_warm).
НЕ интегрировано в level3_eleven.json, НЕ озвучено. ru = субтитры (по смыслу, не дословно).
Ремарки вида `(laughs)` — для TTS, по образцу существующих пулов.
Языки no/sv/pl — уверенно; **tr помечен на проверку носителем/моделью** (обратный перевод на QA).

## Состав

| Актёр | Язык | Что делаем | Позывной/характер одной строкой |
|---|---|---|---|
| x_no (НОВЫЙ) | no | полная ветка | норвежец — неспешный философ фьордов, всё «bra», про погоду и лосей |
| x_sv (НОВЫЙ) | sv | полная ветка | швед — сухой и дотошный, всё по-правильному, жалуется на электрофуры |
| x_pl (ЕСТЬ) | pl | расширение: foreign.pl +3, foreign_warm.pl новый | поляк — весёлый, говорит быстро и по-свойски (уже описан в json) |
| x_tr (НОВЫЙ) | tr | полная ветка | турок — говорливый душа компании, зовёт на чай, «kardeşim» на каждом шагу |

Поляк уже есть короткой веткой (foreign.pl 3 шт., foreign_reply.pl 3 шт.) — нового актёра не плодим, доводим до полной ветки как у x_fi.

---

## x_no — норвежец (новый актёр)

Профиль TTS (по образцу x_fi):
- `engine`: gpt-audio, `lang`: no, voice: предлагаю `onyx` (глубже/спокойнее fable) — на утверждение Механика/пользователя
- `style`: "норвежский водитель грузовика, неспешный философ, мягкий голос, всё «bra», философствует о погоде и фьордах"

### foreign.no (5) — встречный на дороге

1. `God kveld, kanalen! Hvordan går det på veien?`
   ru: Добрый вечер, канал! Как дорога?
2. `Pass deg! Politiet bak broa, de har radar.`
   ru: Берегись! Полиция за мостом, у них радар.
3. `Her går alt fint, kjør rolig. Det er elg i skumringa.`
   ru: У меня всё нормально, езжай спокойно. В сумерках лоси на дороге.
4. `For en regn! (sighs) Men det er bare vær, det. Bra kjøring, folkens!`
   ru: Вот же дождь!.. Но что поделать, просто погода. Удачи, мужики!
5. `Lange turer, stille radio. (chuckles) Det liker jeg. Ha det bra!`
   ru: Дальняя дорога, тихий эфир… Мне это нравится. Всего доброго!

### foreign_reply.no (3) — игрок ответил, не понял

1. `(laughs) Jeg skjønner ikke et ord, bror, men god tur!`
   ru: Ха! Ни слова не понял, брат, но счастливой дороги!
2. `Russisk? (laughs) Ingen anelse, men hilsen tilbake, kollega!`
   ru: По-русски? Понятия не имею, но привет в ответ, коллега!
3. `(laughs) Ja, ja… Jeg forsto ingenting. Kjør forsiktig, venn!`
   ru: Да-да… Ничего не понял. Осторожнее на дороге, друг!

### foreign_warm.no (2) — игрок ответил по-норвежски

1. `(laughs) Å, du snakker norsk! Så bra, bror! God tur, hilsen til dere!`
   ru: О, ты говоришь по-норвежски! Отлично, брат! Счастливого пути, привет вашим!
2. `(warm) Hei hei, nå ble jeg glad! Vi forstår hverandre. Kjør pent, vennen min!`
   ru: Эй-эй, как я рад! Мы понимаем друг друга. Красиво езжай, мой друг!

---

## x_sv — швед (новый актёр)

Профиль TTS:
- `engine`: gpt-audio, `lang`: sv, voice: предлагаю `shimmer` (ровный, чуть сухой) — на утверждение
- `style`: "шведский водитель фуры, сухой и дотошный, корректный и немного недовольный электрофурами, ровная интонация"

### foreign.sv (5)

1. `God kväll, kanalen! Hur är väglaget där framme?`
   ru: Добрый вечер, канал! Какое покрытие там впереди?
2. `Varning! Polis efter bron, de har laser.`
   ru: Внимание! Полиция после моста, у них лазер.
3. `Allt lugnt här. Kör lagom, då kommer du fram.`
   ru: У меня всё спокойно. Езжай lagom — в меру, так и доедешь.
   (пометка: «lagom» — знаменитое «в меру», можно оставить как шведскую фишку с тем же субтитром)
4. `(sighs) El-lastbilar överallt. De kör tyst och fort, det är farligt.`
   ru: Электрофуры повсюду. Едут тихо и быстро — это опасно.
5. `Vilken kö! (sighs) Men jag har kaffe, så det går bra. Lycka till, grabbar!`
   ru: Вот же пробка!.. Но у меня есть кофе, так что нормально. Удачи, ребята!

### foreign_reply.sv (3)

1. `(laughs) Jag förstår ingenting, bror, men lycklig resa!`
   ru: Ничего не понял, брат, но счастливого пути!
2. `Ryska? (laughs) Ingen aning vad du säger, men hej då, kollega!`
   ru: По-русски? Не знаю, что ты сказал, но привет, коллега!
3. `(laughs) Ja, precis… jag hörde bara brus. Kör försiktigt!`
   ru: Да, точно… Я услышал одни помехи. Осторожней за рулём!

### foreign_warm.sv (2)

1. `(laughs) Å, du talar svenska! Så bra, bror! Lycka till på vägarna!`
   ru: О, ты говоришь по-шведски! Здорово, брат! Удачи на дорогах!
2. `(pleased) Men titta! Vi förstår varandra. Varsågod och kör, vän!`
   ru: Ну надо же! Мы понимаем друг друга. Поехали, друг, дорога твоя!

---

## x_pl — поляк (существующий, расширение)

Стиль/голос уже в json (`echo`, «весёлый, быстро, по-свойски»). Не дублируем.

### foreign.pl — ДОБАВИТЬ 3 (будет 6 с существующими)

Существующие (не трогаем): «Dzień dobry, panowie, jak tam droga?», «Uwaga, policja na parkingu, z radarem!», «Znowu korek. Szerokiej drogi, panowie!»

4. `Siema, kanał! U mnie wszystko git, uważajcie na oblodzenie!`
   ru: Привет, канал! У меня всё гут, смотрите — гололёд!
5. `Co za mróz! (laughs) W kabinie minus, a serce gorące. Szerokiej, bracia!`
   ru: Вот же мороз! В кабине минус, а сердце горячее. Широкой, братья!
6. `Droga czysta aż po horyzont. Miłej jazdy, panowie!`
   ru: Дорога чистая до горизонта. Приятной дороги, мужики!

### foreign_warm.pl (2) — НОВЫЙ

1. `(laughs) O, mówisz po polsku! Brawo, bracie! Szerokiej drogi!`
   ru: О, говоришь по-польски! Браво, брат! Широкой дороги!
2. `(radośnie) No i śmiga! Rozumiemy się! Pozdrowienia dla całej ekipy, kolego!`
   ru: Ну и отлично! Понимаем друг друга! Привет всей вашей команде, приятель!

foreign_reply.pl уже 3 шт. — дополнять не нужно (полная ветка по образцу x_fi, у него 2).

---

## x_tr — турок (новый актёр) ⚠ проверить носителем

Профиль TTS:
- `engine`: gpt-audio, `lang`: tr, voice: предлагаю `alloy` (тёплый, говорливый) — на утверждение
- `style`: "турецкий дальнобойщик, говорливый душа компании, тёплый, зовёт на чай, «kardeşim» на каждом шагу"

### foreign.tr (5) — ⚠ проверить носителем

1. `İyi akşamlar, kanal! Yol nasıl gidiyor, kardeşim?`
   ru: Добрый вечер, канал! Как дорога, братишка?
2. `Dikkat! Köprünün arkasında polis var, radar çalışıyor!`
   ru: Осторожно! За мостом полиция, радар работает!
3. `Yol burada açık, gönül ferah. (laughs) Siz de öyle, kardeşler!`
   ru: Здесь дорога свободная, душа радуется. И вам того же, братья!
4. `Ne yağmur ama! (sighs) Çayım var, ben durmam. Hayırlı yolculuklar!`
   ru: Вот же ливень!.. Но у меня есть чай — я не остановлюсь. Доброго пути!
5. `Uzun yol, sıcak çay, iyi muhabbet. (laughs) Görüşürüz, dostum!`
   ru: Дальняя дорога, горячий чай, хорошие разговоры. Увидимся, друг!

### foreign_reply.tr (3) — ⚠ проверить носителем

1. `(güler) Hiç anlamadım kardeşim, ama hayırlı yolculuklar!`
   ru: (смеётся) Ничего не понял, братишка, но доброго пути!
2. `Rusça mı? (güler) Ne dediğini bilmiyorum, ama selam sana, kaptan!`
   ru: По-русски? Не знаю, что ты сказал, но привет тебе, капитан!
3. `(güler) Evet, evet… tamamen boş konuştum. Dikkatli sür, dostum!`
   ru: Да-да… Я вообще ничего не понял. Осторожнее за рулём, друг!

### foreign_warm.tr (2) — ⚠ проверить носителем

1. `(güler) Aa, Türkçe konuşuyorsun! Bravo kardeşim! Hayırlı yolculuklar!`
   ru: А-а, говоришь по-турецки! Браво, братишка! Доброго пути!
2. `(sevinçle) Vay be! Anlaştık işte! Selamlar, çay benden, kaptan!`
   ru: Вот это да! Мы же поняли друг друга! Привет, чай — за мой счёт, капитан!

---

## Объёмы

- x_no: 5 + 3 + 2 = 10 строк
- x_sv: 5 + 3 + 2 = 10 строк
- x_pl: +3 foreign, +2 warm = 5 новых строк (итог у pl: 6/3/2 = 11)
- x_tr: 5 + 3 + 2 = 10 строк
- Итого новых строк: 35 (10+10+5+10), плюс 3 новых блока warm (no/sv/pl/tr).

## Открытые вопросы

1. **Турецкий — на проверку носителем/моделью**: грамматика на бытовом уровне, но финальный QA обязателен (обратный перевод).
2. **Голоса gpt-audio** для новых актёров (onyx/shimmer/alloy) — предложения, утверждает пользователь/Механик при интеграции.
3. **Поляк**: расширяем x_pl или заводим отдельного? Решено расширять (см. таблицу), если нужен второй характер — скажите.
4. Ремарки `(güler)` турецкие — для единообразия лучше заменить на `(laughs)` при интеграции (у всех остальных англ. ремарки); оставил tu-вариант для читаемости драфта.
5. Слово «lagom» в субтитре x_sv #3 — оставить шведский маркер или перевести полностью? Помечено «на вкус».
