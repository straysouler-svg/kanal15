"""Выбор микрофона — общий для рации и установщика (2026-11-05).

Кирилл нажимал тангенту, щелчок был, а ответа нет. Одна из причин: «микрофон по умолчанию» в Windows часто
оказывается виртуальным (Steam Streaming Microphone, Стерео микшер, VB-Cable) и всегда молчит. Поэтому
при автовыборе виртуальные пропускаем; выбор виден и меняется в установщике (страница «Микрофон») и в меню
значка рации. Без numpy: установщик собран без него."""

VIRTUAL = ("steam streaming", "stereo mix", "стерео микшер", "cable output", "vb-audio", "voicemeeter",
           "virtual", "виртуальн", "wave out mix", "what u hear")
MAPPER = ("sound mapper", "переназначение")


def _low(s):
    return str(s or "").lower()


def privacy_blocked():
    """Windows «Конфиденциальность → Микрофон»: when access is denied, EVERY microphone records pure zeros
    (Kirill's log 2026-11-05: peak -90 dB on all 10 presses). -> text for the player, or None."""
    try:
        import winreg
    except ImportError:
        return None
    base = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
    for root, sub, what in ((winreg.HKEY_LOCAL_MACHINE, base, "на этом компьютере"),
                            (winreg.HKEY_CURRENT_USER, base, "для вашей учётной записи"),
                            (winreg.HKEY_CURRENT_USER, base + r"\NonPackaged", "для обычных программ")):
        try:
            with winreg.OpenKey(root, sub) as k:
                if str(winreg.QueryValueEx(k, "Value")[0]).lower() == "deny":
                    return (f"В Windows запрещён доступ к микрофону {what}. Откройте Параметры → Конфиденциальность "
                            "→ Микрофон и включите доступ, в том числе «классическим приложениям».")
        except OSError:
            continue
    return None


def is_virtual(name):
    return any(v in _low(name) for v in VIRTUAL)


def inputs(sd):
    """[(index, name)]: microphones as Windows lists them (MME host API), without the «mapper» entry."""
    try:
        apis = sd.query_hostapis()
        mme = next((i for i, a in enumerate(apis) if a["name"] == "MME"), None)
        devs = sd.query_devices()
    except Exception:
        return []
    return [(i, d["name"]) for i, d in enumerate(devs)
            if d["max_input_channels"] > 0 and (mme is None or d["hostapi"] == mme)
            and not any(m in _low(d["name"]) for m in MAPPER)]


def pick(sd, want=""):
    """-> (index, name, why); index None when there is no microphone at all.
    want: the name saved in config.json (part of the name is enough)."""
    want = _low(want).strip()
    try:
        devs = sd.query_devices()
    except Exception:
        return None, None, "звуковые устройства не читаются"
    why = ""
    if want:
        for i, n in inputs(sd):
            if want in _low(n):
                return i, n, "выбран в настройках"
        for i, d in enumerate(devs):                        # the same mic under another host API
            if d["max_input_channels"] > 0 and want in _low(d["name"]):
                return i, d["name"], "выбран в настройках"
        why = f"«{want}» не найден; "
    try:
        di = sd.default.device[0]
        if di is not None and di >= 0:
            n = devs[di]["name"]
            if not is_virtual(n) and not any(m in _low(n) for m in MAPPER):
                return di, n, why + "микрофон Windows по умолчанию"
            why += f"по умолчанию стоит «{n}» (виртуальный, молчит); "
    except Exception:
        pass
    real = [(i, n) for i, n in inputs(sd) if not is_virtual(n)]
    if real:
        return real[0][0], real[0][1], why + "первый настоящий микрофон"
    ins = inputs(sd)
    if ins:
        return ins[0][0], ins[0][1], why + "есть только виртуальные микрофоны"
    return None, None, why + "микрофонов нет"
