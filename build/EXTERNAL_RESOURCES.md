# Внешние ресурсы сборки «Канала 15»

Зачем: собрать CB-Radio.exe из чистого клона нельзя — часть ресурсов живёт только на машине
разработчика и в приватных хранилищах. Этот файл перечисляет, что именно нужно, где оно лежит
у разработчика и что из этого воспроизводимо публично.

## Публично воспроизводимая часть (есть в репозитории / ставится из PyPI)

- Код рации: `cb-radio/*.py` (чистый Python, зависимости — `cb-radio/requirements.txt`, Python 3.13).
- Сборка: PyInstaller (спеки `build/radio.spec`, генерируемые `setup_<variant>.spec`/`uninstall.spec`
  пишет `cb-radio/tools/build_exe.py`). Запуск из корня репозитория, пути — относительные.
- Плагин штрафов/заказов: `cb-radio/vendor/scs-telemetry.dll` (RenCloud scs-sdk-plugin, MIT, v1.12.1).
- Ключи и каналы обновлений: `cb-radio/tools/update_channels.json` (имена личных каналов со
  случайной частью — приватны), открытый ключ Ed25519 — прямо в `cb-radio/updater.py`.

## Внешние ресурсы, необходимые для релизной сборки

| Ресурс | Зачем | Где берётся у разработчика | Команда/способ |
|---|---|---|---|
| Аудио эфира (`audio/` в OGG Opus), музыка (`music/`), фразы (`phrases/`) | контент рации | приватный этап упаковки: генерируется ElevenLabs/OpenRouter/F5/XTTS скриптами `cb-radio/tools/` из `cb-radio/phrases/*.json`; **в публичный репозиторий не входит** | `pack_release.py` копирует только нужное из `release/<variant>/CB-Radio` |
| Модель Whisper small (~470 МБ, faster-whisper) | распознавание речи по тангенте, локально | кэш HuggingFace: `~/.cache/huggingface/hub/models--Systran--faster-whisper-small` (качается из HF, воспроизводимо, но большая) | `build_exe.py: build_app` копирует снапшот в `app_<variant>/models/whisper-small` |
| Funbit `ets2-telemetry.dll` | канал `Local\SimTelemetryETS2` (скорость и т.п.) | папка плагинов игры Steam; путь — `ETS2_TELEMETRY_DLL` или авто-поиск в стандартных библиотеках Steam | `pack_release.py` кладёт в `installer/plugins/` |
| DLL Visual C++ (`msvcr110.dll`, `msvcp140.dll`, `vcruntime140*.dll`) | зависимости плагинов и фикс старых DLL из PyInstaller | `C:\Windows\System32` машины сборки | копируются `build_exe.py`/`pack_release.py` |
| Арт установщика (`installer_art/banner_final.png`, `icon.png`, `side_banner.png`, `kardan_kruchitsya.wav`) | окна установщика/удаления | репозиторий (`cb-radio/installer_art/`, генерируется `tools/make_brand_art.py`) | часть репозитория |
| Ключ подписи обновлений `cb-radio/update_signing_key.txt` | подпись manifest.json (Ed25519) | только у автора, **в git не входит**; `--init` в `publish_update.py` создаёт | не нужен для сборки, нужен для выпуска обновления |
| Ключ S3 `cb-radio/yandex_storage_key.txt` | выкладка обновлений в Yandex Object Storage | только у автора, **в git не входит** | `publish_update.py` |
| Ключ отправки диагностических отчётов | upload отчётов (см. P0-4 промта стабилизации) | только у автора; этап упаковки контента | `pack_release.py` (`phrases/x.dat`) |

## Граница «публичное / приватное»

- **Публично воспроизводимо:** код, спеки, чистые модули, unit-тесты, CI (syntax/lint/тесты чистых
  модулей), скачивание зависимостей и модели Whisper.
- **Приватный этап упаковки контента (машина разработчика):** озвучка реплик (платные ключи
  ElevenLabs/OpenRouter), сборка аудио, подпись и выкладка обновлений, личные сборки (kirill/alive).
  Без этого этапа из репозитория собирается только «пустой» каркас: рация запустится, но эфира не будет.
