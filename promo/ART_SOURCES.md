# Источники арта «Канала 15»

Учёт: по строке на каждый файл арта. Обновляет Художник при каждой сдаче (регламент — `.claude/agents/artist.md`, навык `kanal15-art`). Даты — по файлам на диске. Картинки в git не идут (`.gitignore`), этот файл — их паспорт.

Инструменты: генерация фото — OpenRouter, модель `google/gemini-3.1-flash-image` через `cb-radio/tools/gen_image.py` (ключ `cb-radio/openrouter_key.txt`); весь текст на картинках — PIL поверх (кириллицу нейросеть ломает), шрифты дизайн-пакета: Golos Text (OFL, github.com/googlefonts/golos-text) и Orelega One (OFL, github.com/google/fonts/ofl/orelegaone), файлы и лицензии — `promo/design/Channel15_Design_Pack/fonts/`. Требование ко всем генерациям: кабины без эмблем, шильдиков, текста и читаемых номеров (UNBADGED).

## Портреты водителей — `promo/drivers_art/`

| Файл | Инструмент / дата | Скрипт / запрос |
|---|---|---|
| `portraits/<key>_<n>.png` (2 варианта × 17 водителей) | gemini-3.1-flash-image, 07.11.2026 | `make_portraits.py`, промпт на водителя из словаря `D` (возраст, предмет-характер, машина; общий стиль STYLE + RULES «UNBADGED, no text»). Сорока не рисуется — осознанно, она «только у автора». |
| `selected/<key>.png` | выбор из `portraits/` по `picks.json`, 07.11.2026 | ручной отбор пользователем/Художником; опорные лица, все производные — только из них |
| `sheet_1.jpg`, `sheet_2.jpg` | сборка листов по 2 варианта, 07.11.2026 | `make_portraits.py` (журнал `make_portraits.log`) |
| `group/_reference_collage.jpg` | коллаж опорных лиц | `make_group.py` |
| `group/party_<n>.png`, `party_2_fix*.png`, `party_3_fix.png` | gemini-3.1-flash-image, 07.11.2026 | `make_group.py`: промпт «вечеринка на полянке», референс-коллаж, 17 водителей + игрок со спины; правки `fix_group.py`, `detail_group.py` |
| `banners/youtube_2560x1440.jpg`, `twitch_1200x480.jpg`, `telegram_post.jpg`, `_youtube_safe_preview.jpg` | ресайз группового арта, 07.11.2026 | скрипт не зафиксирован (предположительно PIL/Sharp ресайз `group/`); **уточнить и записать при следующей правке** |

## Капсулы Steam — `promo/steam/`

| Файл | Дата | Скрипт |
|---|---|---|
| `capsules/hero_raw.png`, `library_raw.png` | 10.11.2026 | генерация нейросетью (стол с делами), raw-основы 4:1 и 2:3 |
| `capsules/header.png` (460×215), `small.png` (231×87), `main.png` (616×353), `hero.png`, `library.png` | 10.11.2026 | `promo/steam/make_capsules.py`: кадрирование raw-основ + `article_b/cover_desk_raw.png`, текст PIL (Orelega One / Golos Text), затемнения под текст. **Размеры устарели: Steam с ноября 2024 требует вдвое больше (920×430, 462×174, 1232×706) — пересборка запланирована.** |

## Арт статей — `promo/article_b/`

| Файл | Дата | Скрипт |
|---|---|---|
| `cover_desk_raw.png` | 10.11.2026 | нейросеть (стол с делами), raw |
| `cover_desk.png`, `banner_face.png`, `banner_map.png`, `banner_mug.png`, `banner_radio.png` | 10.11.2026 | `make_art.py` — локальная PIL-сборка (план Б: нейросеть отдавала 403; `random.seed(15)`), композитинг raw + полароиды из `drivers_art/selected/` |
| `pikabu_post_b_longpost.png`, `joy_post_b_longpost.png`, `pikabu_v2_longpost.png`, `joy_v2_longpost.png` (+ `.jpg`) | 10–11.11.2026 | `build_longpost.py` из md-черновиков постов |
| `preview*.html` | 10.11.2026 | те же `build_longpost.py` / `sign_cover.py` |

## Прочее — `promo/`

| Файл | Дата | Скрипт |
|---|---|---|
| `forum_art/collage_all.png` | 08.11.2026 | `make_collage.py`: сетка 6×3 из `drivers_art/selected/`, плашки с позывными (Golos Text) |
| `forum_art/collage_nonames.png` | 09.11.2026 | `make_collage_nonames.py` — тот же состав без имён (для анонсов) |
| `icon/kanal15_icon_256.png` | 04.11.2026 | серия `icon/icon_A..D.png`, сборщик не зафиксирован (см. `promo/icon/`); **уточнить при следующей правке** |

## AI-раскрытие для Steam

Арт портретов/капсул и озвучка — pre-generated контент; в Content Survey Steam (раздел «Generative AI Content») раскрываем оба. Live-generated нет. Сверка требований: 11.11.2026 (см. навык `kanal15-art`).
