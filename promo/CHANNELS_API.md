# Внешние каналы: подключение по API (шпаргалка на все проекты)

Документ общий, не только для «Канала 15»: всё, что мы подключили, пригодится в других проектах. Секреты здесь НЕ храним — только пути к локальным файлам с ними (все они в .gitignore). Правила: публикации — только по явному слову пользователя; перед push прогон `cb-radio/tools/check_privacy.py`.

Статусы на 14.11.2026.

## YouTube (работает, автопостинг)

- **Что:** загрузка Shorts по расписанию, смена приватности, статистика канала.
- **Скрипты:** `promo/youtube/autopost_yt.py` (планировщик, задача Windows `Kanal15-Autopost-YouTube`, у задачи ОБЯЗАТЕЛЬНО рабочая папка — иначе код 2), `upload_short.py`, `set_privacy.py`, `channel_stats.py`.
- **Очередь:** `promo/youtube/queue.json` (время мск, не более одного поста за запуск; опубликованное — в `state.json`).
- **Креды:** `client_secret.json` (OAuth-клиент, Google Cloud Console) + `token.json` (обновляется сам).
- **Грабли:** пока OAuth-приложение в «тестировании», авторизоваться могут только тестовые пользователи из консоли (ошибка 403 access_denied — добавить почту в Test users). При нескольких аккаунтах Google внимательно выбирать НУЖНЫЙ канал в диалоге — токен привяжется к выбранному.

## Telegram (работает: бот-автопостинг + стрим)

- **Бот «Канал 15 Паблишер»:** постинг в канал по расписанию `promo/telegram/schedule.json`, скрипт `promo/telegram/autopost.py` (планировщик Windows), токен — `promo/telegram/bot_token.txt`. Текст/HTML, аудио с performer/title, видео с caption. `min_gap_hours` защищает от слипающихся постов.
- **Стрим в ТГ:** отдельный поток из OBS через плагин telegramcast, сервер+ключ — `promo/telegram/telegrammcast key.txt` (локально). Трансляция полноценная 1920×1080, НЕ вертикальная.
- **Грабли:** голые посты без ссылок — упущение; в caption всегда ссылка на скачивание/YouTube.

## VK (работает: стена/фото/видео)

- **Группа:** vk.ru/club243244739 (id в `promo/vk/group_id.txt`).
- **Скрипты:** `promo/vk/post_vk.py` (текст, фото), `upload_vk_video.py` (видео в раздел без поста, user_token), `autopost_vk.py` (зеркало очереди YouTube: video.save user_token → wall.post ключом сообщества; задача `Kanal15-Autopost-VK`), `auth_vkid.py` (url/exchange/refresh — пользовательский токен VK ID), `setup_group.py`, `make_vk_art.py` (аватар/обложка).
- **Креды:** `promo/vk/token.txt` — ключ СООБЩЕСТВА. Хватает на `wall.*`, `photos.*`, `groups.*`. Для `video.*` — `promo/vk/user_token.txt` (пользовательский VK ID, живёт 1 ч, refresh через `auth_vkid.py refresh`).
- **Грабли (14.11):** `video.*` ключом сообщества — «error 5». Implicit flow мёртв; рабочий путь — VK ID PKCE (приложение 54897346), и `oauth2/auth` требует сервисный ключ параметром `service_token` (не client_secret, не Bearer — иначе «missing service token»). Подробный рецепт: `promo/vk/Настройка VK.md`.

## TikTok (sandbox, на ревью)

- **Скрипты:** `promo/tiktok/auth_tiktok.py` (OAuth: `auth` → ссылка, `exchange <url>` → токен; code живёт ~1 минуту, действовать быстро), `upload_tiktok.py` (Content Posting API, `video.upload`+`video.publish`).
- **Креды:** `client_key.txt`, `client_secret.txt`, `token.txt`, `refresh_token.txt`.
- **Статус:** приложение «Kanal15-publisher» в sandbox — видео публикуются приватно, пока TikTok не одобрит ревью. Ревью требует: верифицированный URL-префикс (у нас GitHub Pages `straysouler-svg.github.io/kanal15/` + файл `tiktok….txt` в корне сайта), описание продуктов/скоупов, демо-видео полного цикла (у нас `tiktok_review_demo.mp4`, план в `review_plan_2026-11-13.md`).
- **Грабли:** в sandbox тестировать только с аккаунта-тестировщика (добавляется в настройках приложения); redirect_uri в коде и в консоли должны совпадать символ в символ.

## Instagram / Facebook (ЗАБЛОЧЕНО)

- Требует подтверждение личности FB по SMS — SMS в РФ не приходят. План Б: виртуальный номер (CodesSender карты СНГ не берёт — искать других провайдеров). Отложено до решения пользователя.

## Хостинг/витрина

- **Лендинг:** GitHub Pages из репо, `https://straysouler-svg.github.io/kanal15/` (используется и как redirect_uri/верификация для TikTok).
- **Релизы/обновления:** storage.yandexcloud.net/kanal15-updates (ссылки на установщики в постах).
- **Донат:** donationalerts.com/r/straysouler — ссылка в описаниях стримов (`promo/stream/youtube_description.txt`).

## Higgsfield (генерация видео, только веб)

- Сложные генерации (трейлер/тизер для Steam) делаем руками в веб-интерфейсе; API нет. Баланс кредитов и доступ — у пользователя. Брифы готовит Режиссёр.

## Прочее подключённое

- **Стрим-мониторинг:** obsws/сцены OBS; стримы Twitch+YouTube+VK+TG одновременно.
- **Аналитика канала YouTube:** `promo/youtube/channel_stats.py`, снапшоты в `promo/youtube/stats/`.

## Как добавлять новый канал

1. Завести подпапку `promo/<канал>/` с `Настройка <Канал>.md` (шаги для пользователя по-русски, ~15 минут).
2. Секреты — только локальные файлы рядом, в .gitignore, в чат/STATUS/MODLOG не копировать.
3. Скрипт постинга + тестовый пост «глазами», потом удалить.
4. Дописать секцию в этот файл (статус, креды-пути, грабли).
