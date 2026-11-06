"""Голос стримера громче (2026-11-06, стрим №1: чат дважды просил «прибавь микрофон»).
Микрофон fifine тихий. Фильтры на «Микр/доп» в наборе «Канал 15»: шумодав RNNoise -> усиление -> компрессор -> лимитер.
Запускать при закрытом OBS. Повторный запуск заменяет эти фильтры, другие не трогает."""
import json
import uuid
from pathlib import Path

COL = Path.home() / "AppData" / "Roaming" / "obs-studio" / "basic" / "scenes" / "Канал_15.json"
GAIN_DB = 8.0

OURS = [
    ("noise_suppress_filter_v2", "Шумодав", {"method": "rnnoise"}),
    ("gain_filter", "Усиление", {"db": GAIN_DB}),
    ("compressor_filter", "Компрессор", {"ratio": 4.0, "threshold": -20.0, "attack_time": 6, "release_time": 60,
                                          "output_gain": 0.0, "sidechain_source": "none"}),
    ("limiter_filter", "Лимитер", {"threshold": -1.5, "release_time": 60}),
]

col = json.loads(COL.read_text(encoding="utf-8"))
mic = col["AuxAudioDevice1"]
names = {n for _, n, _ in OURS}
filters = [f for f in mic.get("filters", []) if f.get("name") not in names]
for fid, name, settings in OURS:
    filters.append({"versioned_id": fid, "id": fid.replace("_v2", "") if fid.endswith("_v2") else fid,
                    "name": name, "uuid": str(uuid.uuid4()), "settings": settings, "enabled": True,
                    "mixers": 0, "sync": 0, "flags": 0, "volume": 1.0, "balance": 0.5, "muted": False,
                    "private_settings": {}, "push-to-mute": False, "push-to-talk": False, "monitoring_type": 0})
mic["filters"] = filters
COL.write_text(json.dumps(col, ensure_ascii=False, indent=2), encoding="utf-8")
print("микрофон:", mic["name"], "фильтры:", [f["name"] for f in filters])
