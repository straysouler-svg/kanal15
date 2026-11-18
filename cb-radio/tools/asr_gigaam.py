"""GigaAM v3 (sherpa-onnx, Сбер) — распознавание для QA сухих TTS-треков.

Только для dry-записей: на звуке с радиоэффектом кабины сыплется (там — faster-whisper).
Веса и параметры init (feature_dim=64, model_type="nemo_transducer") проверены 18.11.
"""
from pathlib import Path

import numpy as np

WS_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = WS_ROOT / "build" / "sherpa-onnx-nemo-transducer-punct-giga-am-v3-russian-2025-12-16"

_REC = None


def recognizer():
    global _REC
    if _REC is None:
        import sherpa_onnx
        d = MODEL_DIR
        _REC = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(d / "encoder.int8.onnx"),
            decoder=str(d / "decoder.onnx"),
            joiner=str(d / "joiner.onnx"),
            tokens=str(d / "tokens.txt"),
            num_threads=4,
            sample_rate=16000,
            feature_dim=64,
            decoding_method="greedy_search",
            model_type="nemo_transducer",
        )
    return _REC


def heard_text(x):
    """x — float32 mono 16 кГц (диапазон [-1,1]) -> распознанный текст."""
    rec = recognizer()
    stream = rec.create_stream()
    stream.accept_waveform(16000, np.clip(x, -1.0, 1.0).astype(np.float32))
    rec.decode_stream(stream)
    return stream.result.text
