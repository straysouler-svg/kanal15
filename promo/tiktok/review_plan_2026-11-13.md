# План прохождения ревью TikTok для kanal15-publisher (13.11.2026)

Цель: приложение проходит App Review → посты становятся публичными (PUBLIC_TO_EVERYONE),
появляется доступ с открытого аккаунта. Домен покупать НЕ нужно — используем бесплатный
GitHub Pages на нашем же репозитории: https://straysouler-svg.github.io/kanal15/

## Уже готово (13.11)

- Песочница настроена и работает: Login Kit + Content Posting API, Direct Post, скоупы
  user.info.basic + video.upload + video.publish, target user jeleziaaka, токены получены.
- Заливка работает технически (одним куском до 64 МБ); упор сейчас только в
  unaudited_client_can_only_post_to_private_accounts.
- Лендинг написан и лежит в `docs/`: index.html (витрина), privacy.html, terms.html, icon.png.
  Тексты на английском — ревьюеры TikTok англоязычные.
- check_privacy почищен от ложных срабатываний, в коммитах для пуша — чисто.

## Шаг 1. Включить GitHub Pages (нужен пуш — по слову пользователя)

1. Закоммитить `docs/` и запушить main.
2. GitHub → репозиторий kanal15 → Settings → Pages → Source: «Deploy from a branch» →
   Branch: main, папка /docs → Save.
3. Через 1–2 минуты сайт живёт на https://straysouler-svg.github.io/kanal15/
   (privacy: /privacy.html, terms: /terms.html). Проверить, что открывается.

## Шаг 2. Верификация URL у TikTok

1. developers.tiktok.com → наше приложение → кнопка «URL properties» (справа вверху).
2. Add property → вписать https://straysouler-svg.github.io/kanal15/ → TikTok даст
   проверочный файл вида tiktok-verify....txt или мета-тег.
3. Положить файл в `docs/` (или мета-тег в index.html), закоммитить, запушить.
4. Вернуться в портал → Verify. После этого URL считается подтверждённым.

## Шаг 3. Обновить Production-драфт

1. Production → App details:
   - Terms of Service URL → https://straysouler-svg.github.io/kanal15/terms.html
   - Privacy Policy URL → https://straysouler-svg.github.io/kanal15/privacy.html
   - Web/Desktop URL → https://straysouler-svg.github.io/kanal15/
2. Login Kit Redirect URI добавить https://straysouler-svg.github.io/kanal15/
   (после этого обновить REDIRECT_URI в promo/tiktok/auth_tiktok.py — при смене
   редиректа OAuth-код нужно будет получить заново).
3. App review → поле «Explain how each product and scope works» уже заполнено.
4. Save — после верификации URL ошибки «not verified» уйдут.

## Шаг 4. Демо-видео (обязательно для ревью)

Требования TikTok: mp4/mov до 50 МБ, показать ПОЛНЫЙ цикл: сайт (тот же домен!),
авторизация через Login Kit, загрузка через Content Posting API, все скоупы видны.
Пишем OBS-ом в один дубль, сценарий (~60–90 сек):

1. Браузер: открыть https://straysouler-svg.github.io/kanal15/ (видно домен и сайт).
2. Перейти по OAuth-ссылке (client_key sbaw3d0yboyj2eg5vl) → экран согласия TikTok
   с видимыми скоупами → Authorize → редирект с ?code=...
3. Терминал: `python promo/tiktok/auth_tiktok.py exchange "<url>"` → токены получены.
4. Терминал: `python promo/tiktok/upload_tiktok.py short.mp4 --title "..."` → прогресс, publish_id.
5. Приложение TikTok на телефоне/эмуляторе: ролик появился в профиле (приватный).
6. Склеить/обрезать до <50 МБ, залить в App review → Upload.

## Шаг 5. Submit for review

- Production → Submit for review. Срок ответа обычно 1–7 дней.
- Пока идёт ревью — песочница продолжает работать (посты приватные, аккаунт закрытый).

## Откат

- Всё локально обратимо: песочницу можно удалить кнопкой Delete Sandbox,
  приложение — в списке приложений. GitHub Pages выключается в Settings → Pages → None.
- Токены отзываются в настройках аккаунта TikTok (Apps and services).
