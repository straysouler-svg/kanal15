# vendor: сторонние файлы для сборки (бинарники в git не кладём)

- scs-telemetry.dll: RenCloud scs-sdk-plugin v1.12.1 (MIT), Win64.
  Источник: https://github.com/RenCloud/scs-sdk-plugin/releases/tag/V.1.12.1 (release_v_1_12_1.zip, Win64/scs-telemetry.dll)
  SHA-256: 1d03dbc7a975e72203c60a7b9998021ceb8800b836bf28a131279979ad386cd4
  Зачем: даёт штрафы и данные заказа в общей памяти Local\SCSTelemetry. Без него (и без SimHub) бухгалтерия молчит.
  Нужен Visual C++ 2015-2022 x64 (msvcp140.dll, vcruntime140.dll); сборка кладёт их рядом.
