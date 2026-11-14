# Настройка автопостинга Reels в Instagram — ВЫПОЛНЕНО 14.11.2026

Meta в РФ заблокирована — весь процесс через VPN (Франция: страна VPN = стране номера).
Мета признана в РФ экстремистской организацией: рекламу не покупаем, только постинг (канон проекта).

## Что сделано

- IG `jeleziaaka` переведён в профессиональный (Creator) и добавлен в Центр аккаунтов Meta.
- Создана FB-страница «Канал 15» (id 61596723953714), IG привязан.
- FB-аккаунт подтверждён по SMS через арендованный французский номер (CodesSender).
- Meta for Developers: приложение `kanal15-radio` (id в app_id.txt), сценарий
  «Управление сообщениями и контентом в Instagram».
- Создано бизнес-портфолио «Kanal15» (без него новый «единый вход» не работает — грабля!),
  IG-аккаунт добавлен в портфолио как объект.
- Конфигурация Instagram API (единый вход), config_id 2065890004076905,
  redirect URI: https://straysouler-svg.github.io/kanal15/
- Токен: **системный (SUAT), бессрочный** — лежит в `promo/instagram/token.txt`.
  Продление не нужно; проверка: `python refresh_token.py check`.
- IG user id (IGSID): в `promo/instagram/ig_user_id.txt`. Нашли через
  `GET /{system_user_id}/assigned_instagram_accounts` — web-id профиля (74210...) НЕ работает, грабля!

## Файлы (секреты, в .gitignore)

token.txt, app_secret.txt, app_id.txt, ig_user_id.txt

## Скрипты

- `post_reel.py short.mp4 --caption "..."` — публикация Reels (resumable upload, graph.facebook.com).
- `exchange_code.py "<url с ?code=>"` — обмен OAuth-кода на токен (если токен отзовут).
- `refresh_token.py check` — валидность токена (debug_token).

## Ограничения

- 25 постов с медиа в сутки через API — нам нужно 2.
- Reels: 3 сек – 15 мин, mp4, вертикаль 9:16 — наши шортсы проходят.
- Приложение в dev-режиме: постим на свой аккаунт, ревью Meta не нужно.
- Если захотим расширить разрешения или публичность — потребуется App Review.

## TODO при смене аккаунта/отзыве токена

Повторить: конфигурация единого входа → URL входа → авторизация → exchange_code.py →
новый IGSID через assigned_instagram_accounts.
