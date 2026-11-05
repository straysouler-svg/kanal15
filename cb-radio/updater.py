"""Автообновление «Канала 15» (2026-11-05). Тихо, в фоне, без окон; без интернета — просто ничего не делает.

Сервер (Yandex Object Storage, раздаёт tools/publish_update.py):
  <url>/channels/<channel>/manifest.json   {"version","date","notes","base","files":{rel:[sha256,size]},"managed":[..]}
  <url>/channels/<channel>/manifest.sig    подпись Ed25519 манифеста (hex), ключ — PUBLIC_KEY ниже
  <url>/blobs/<sha256>                     содержимое файлов (одно на все каналы)
Рация: проверяет подпись -> сравнивает файлы -> качает изменившиеся в update/staged/files/ (каждый сверяет по sha256)
-> пишет plan.json и READY. Ставит launcher.py при следующем запуске (с резервной копией и откатом).
Exe и библиотеки (_internal) обновление НЕ трогает: если поменялись они («base»), рация просит поставить установщик.
"""
import hashlib
import json
import shutil
import sys
import threading
import time
import urllib.request
from pathlib import Path

import ed25519

PUBLIC_KEY = "1b4d3f6abe5bf516a16a51c86a881e7a4556af50b10de03a71f39dd7746170d0"          # hex, вписывается tools/publish_update.py --init (ключ подписи хранится только у автора)
UA = "Kanal15-Radio-Updater"
MANAGED = ("app/", "audio/", "phrases/", "map/", "installer/", "README.md", "CHANGELOG.md", "CREDITS.md",
           "version.json")
NEVER = ("config.json", "state.json", "world_state.json", "install.json")


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def sha256_file(p, buf=1 << 20):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(buf), b""):
            h.update(b)
    return h.hexdigest()


def base_signature(root):
    """What only a full installer can change: the exe + the library folder (names and sizes)."""
    h = hashlib.sha256()
    exe = Path(root) / "CB-Radio.exe"
    if exe.exists():
        h.update(sha256_file(exe).encode())
    lib = Path(root) / "_internal"
    if lib.exists():
        for f in sorted(lib.rglob("*")):
            if f.is_file() and f.suffix != ".pyc":
                h.update(f"{f.relative_to(lib).as_posix()}:{f.stat().st_size}\n".encode())
    return h.hexdigest()


def local_files(root):
    out = {}
    root = Path(root)
    for m in MANAGED:
        p = root / m
        if m.endswith("/"):
            if p.exists():
                for f in p.rglob("*"):
                    if f.is_file() and "__pycache__" not in f.parts:
                        out[f.relative_to(root).as_posix()] = f
        elif p.exists():
            out[m] = p
    return out


class Updater:
    def __init__(self, root, cfg, version, log=print, notify=None):
        u = cfg.get("update") or {}
        self.root, self.version, self.log, self.notify = Path(root), version, log, notify
        self.url = str(u.get("url", "")).rstrip("/")
        self.channel = str(u.get("channel", "public"))
        self.auto = bool(u.get("auto", True))
        self.status = "ещё не проверяли"
        self.available = None                 # version waiting for the next start
        self.need_installer = False
        self._lock = threading.Lock()
        self.enabled = bool(getattr(sys, "frozen", False) and self.url and PUBLIC_KEY)

    # ---------------------------------------------------------------- public
    def start(self, first_delay=60, every=6 * 3600):
        if not self.enabled:
            self.status = "выключено (сборка без обновлений)"
            return

        def loop():
            time.sleep(first_delay)
            while True:
                if self.auto:
                    self.check()
                time.sleep(every)
        threading.Thread(target=loop, daemon=True).start()

    def mark_ok(self):
        """The radio works: the update applied at this start is kept (launcher won't roll it back)."""
        a = self.root / "update" / "applied.json"
        try:
            info = json.loads(a.read_text(encoding="utf-8"))
            if not info.get("ok"):
                info["ok"] = True
                a.write_text(json.dumps(info), encoding="utf-8")
                self.log(f"обновление {info.get('version')} работает")
        except (OSError, ValueError):
            pass

    def check(self):
        """Fetch, verify and stage. Never raises; returns a short status for the tray."""
        if not self.enabled or not self._lock.acquire(blocking=False):
            return self.status
        try:
            self.status = self._check()
        except Exception as e:  # noqa: BLE001 — offline, server down, anything: the radio goes on
            self.status = "нет связи с сервером обновлений"
            self.log(f"обновления: {e!r}")
        finally:
            self._lock.release()
        return self.status

    # ---------------------------------------------------------------- inside
    def _check(self):
        base = f"{self.url}/channels/{self.channel}"
        raw = _get(f"{base}/manifest.json")
        sig = bytes.fromhex(_get(f"{base}/manifest.sig").decode().strip())
        if not ed25519.verify(bytes.fromhex(PUBLIC_KEY), raw, sig):
            self.log("обновления: ПОДПИСЬ НЕ СОШЛАСЬ — обновление отклонено")
            return "обновление отклонено: неверная подпись"
        m = json.loads(raw.decode("utf-8"))
        ver = str(m.get("version"))
        if ver == self.version:
            return f"последняя версия ({ver})"
        if m.get("base") and m["base"] != base_signature(self.root):
            self.need_installer = True
            self.log(f"обновления: версия {ver} требует нового установщика")
            if self.notify:
                self.notify(f"Вышла версия {ver}. Её нужно поставить установщиком: {m.get('installer_url', '')}")
            return f"версия {ver}: нужен установщик"
        st = self.root / "update" / "staged"
        if (st / "READY").exists():
            plan = json.loads((st / "plan.json").read_text(encoding="utf-8"))
            if plan.get("version") == ver:
                return f"версия {ver} скачана, установится при следующем запуске"
        if st.exists():
            shutil.rmtree(st)
        have = local_files(self.root)
        want = m["files"]
        need = [rel for rel, (h, size) in want.items()
                if not any(rel.startswith(n) or rel == n for n in NEVER)
                and (rel not in have or have[rel].stat().st_size != size or sha256_file(have[rel]) != h)]
        delete = [rel for rel in have if rel not in want and any(rel.startswith(d) for d in m.get("managed", MANAGED))]
        total = sum(want[r][1] for r in need)
        self.log(f"обновления: {self.version} -> {ver}: качаю {len(need)} файлов ({total / 1e6:.1f} МБ), удалить {len(delete)}")
        for rel in need:
            h, size = want[rel]
            data = _get(f"{self.url}/blobs/{h}", timeout=120)
            if len(data) != size or hashlib.sha256(data).hexdigest() != h:
                raise ValueError(f"файл {rel} пришёл повреждённым")
            out = st / "files" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(data)
        (st / "plan.json").write_text(json.dumps({"version": ver, "from": self.version, "files": need, "delete": delete},
                                                 ensure_ascii=False), encoding="utf-8")
        (st / "READY").write_text(ver, encoding="utf-8")
        self.available = ver
        self.log(f"обновления: версия {ver} скачана — установится при следующем запуске рации")
        if self.notify:
            notes = "; ".join(m.get("notes", [])[:2])
            self.notify(f"Скачана версия {ver}. Установится при следующем запуске рации. {notes}"[:250])
        return f"версия {ver} скачана, установится при следующем запуске"
