# Канал 15 — мультиплеер для интровертов

Рация для одиночной игры в Euro Truck Simulator 2: водители-персонажи едут своими рейсами по карте игры,
говорят в эфире и отвечают игроку голосом через тангенту на руле. Работает без интернета.

- Telegram-канал: [t.me/kanal15_ets2](https://t.me/kanal15_ets2) — новости, образцы эфира, анкета «стань водителем в эфире»
- YouTube: [@kanal15_ets2](https://www.youtube.com/@kanal15_ets2) — короткие ролики из поездок
- Заявки, анкеты и записи голоса: бот [@kanal15_publisher_bot](https://t.me/kanal15_publisher_bot)

- `cb-radio/` — рация: `cb_radio.py` (эфир, тангента, ответы), `world.py` (живая трасса), `intents.py` (что сказал игрок),
  `gamecheck.py`, `mic.py`, `tray.py`; тексты всех реплик — `phrases/level3_eleven.json`; персонажи — `CHARACTERS.md`.
- `cb-radio/tools/` — озвучка (ElevenLabs, gpt-audio, XTTS), упаковка, сборка установщиков, версии.
- `build/radio.spec` — сборка CB-Radio.exe (PyInstaller).
- `promo/` — канал в Telegram (автопостинг), YouTube, шортсы.
- `MODLOG.md` — журнал работ.

Звук, модели, сборки и ключи в репозиторий не входят (см. `.gitignore`).
