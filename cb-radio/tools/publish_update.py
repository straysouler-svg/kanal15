"""Выпуск обновления «Канала 15» в Yandex Object Storage (2026-11-05).

    python tools/publish_update.py --init                 # один раз: ключ подписи + каналы (печатает, что сохранить)
    python tools/publish_update.py neutral [--installer]  # канал public  <- build/app_neutral
    python tools/publish_update.py kirill  [--installer]  # личный канал   <- build/app_kirill

Нужно: cb-radio/yandex_storage_key.txt (1-я строка — идентификатор ключа, 2-я — секрет; Git его не видит),
        cb-radio/update_signing_key.txt (создаёт --init; БЕЗ НЕГО ОБНОВЛЕНИЯ ВЫПУСКАТЬ НЕЛЬЗЯ — храни копию),
        tools/update_channels.json (бакет и имена каналов; личные каналы — со случайной частью в имени).
Порядок выпуска: bump_version -> build_exe -> publish_update (по каналу на сборку)."""
import datetime
import hashlib
import hmac
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CB = Path(__file__).resolve().parents[1]
BUILD = CB.parent / "build"
sys.path.insert(0, str(CB))
import ed25519  # noqa: E402
import updater  # noqa: E402

CHANNELS = Path(__file__).with_name("update_channels.json")
SIGN_KEY = CB / "update_signing_key.txt"
S3_KEY = CB / "yandex_storage_key.txt"
HOST, REGION = "storage.yandexcloud.net", "ru-central1"


# ---------------------------------------------------------------- S3 (AWS Signature V4), stdlib only
def s3_put(bucket, key, data, content_type="application/octet-stream", cache="public, max-age=31536000, immutable"):
    kid, secret = [x.strip() for x in S3_KEY.read_text(encoding="utf-8-sig").splitlines()[:2]]
    now = datetime.datetime.now(datetime.timezone.utc)
    amz, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    ph = hashlib.sha256(data).hexdigest()
    uri = "/" + bucket + "/" + urllib.parse.quote(key, safe="/~")
    hdr = {"host": HOST, "x-amz-content-sha256": ph, "x-amz-date": amz, "content-type": content_type,
           "cache-control": cache}
    signed = ";".join(sorted(hdr))
    canon = "\n".join(["PUT", uri, "", "".join(f"{k}:{hdr[k]}\n" for k in sorted(hdr)), signed, ph])
    scope = f"{day}/{REGION}/s3/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(canon.encode()).hexdigest()])
    k = hmac.new(("AWS4" + secret).encode(), day.encode(), hashlib.sha256).digest()
    for part in (REGION, "s3", "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    sig = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()
    hdr["authorization"] = f"AWS4-HMAC-SHA256 Credential={kid}/{scope}, SignedHeaders={signed}, Signature={sig}"
    req = urllib.request.Request(f"https://{HOST}{uri}", data=data, method="PUT",
                                 headers={k: v for k, v in hdr.items() if k != "host"})
    with urllib.request.urlopen(req, timeout=600) as r:
        if r.status not in (200, 201):
            raise RuntimeError(f"PUT {key}: HTTP {r.status}")


def exists(url):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": updater.UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return False
        raise


# ---------------------------------------------------------------- init: signing key + channels
def init():
    if SIGN_KEY.exists():
        print("ключ подписи уже есть:", SIGN_KEY)
    else:
        SIGN_KEY.write_text(os.urandom(32).hex() + "\n", encoding="utf-8")
        print("создан ключ подписи:", SIGN_KEY, "— СОХРАНИ КОПИЮ (без него обновления выпускать нельзя)")
    pub = ed25519.public_key(bytes.fromhex(SIGN_KEY.read_text().strip())).hex()
    up = CB / "updater.py"
    s = up.read_text(encoding="utf-8")
    s = re.sub(r'^PUBLIC_KEY = "[0-9a-f]*"', f'PUBLIC_KEY = "{pub}"', s, count=1, flags=re.M)
    up.write_text(s, encoding="utf-8")
    print("открытый ключ вписан в updater.py:", pub)
    if not CHANNELS.exists():
        CHANNELS.write_text(json.dumps({"bucket": "kanal15-updates",
                                        "channels": {"neutral": "public", "kirill": "kirill-" + os.urandom(8).hex()}},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
        print("каналы:", CHANNELS)


def channels():
    return json.loads(CHANNELS.read_text(encoding="utf-8"))


def base_url():
    return f"https://{HOST}/{channels()['bucket']}"


# ---------------------------------------------------------------- publish
def notes_of(ver):
    lines, on = [], False
    for ln in (CB / "CHANGELOG.md").read_text(encoding="utf-8").splitlines():
        if ln.startswith("## "):
            if on:
                break
            on = ln.startswith(f"## {ver}")
        elif on and ln.startswith("- "):
            lines.append(ln[2:].strip())
    return lines


def publish(variant, with_installer=False, installer_url=None):
    ch = channels()
    channel, bucket = ch["channels"][variant], ch["bucket"]
    app = BUILD / f"app_{variant}"
    ver = json.loads((CB / "version.json").read_text(encoding="utf-8"))
    files = {rel: [updater.sha256_file(p), p.stat().st_size] for rel, p in updater.local_files(app).items()
             if rel not in updater.NEVER}
    m = {"version": ver["version"], "date": ver["date"], "channel": channel, "notes": notes_of(ver["version"]),
         "base": updater.base_signature(app), "managed": list(updater.MANAGED), "files": files}
    url = base_url()
    if with_installer:
        name = f"Kanal15-Setup{ {'kirill': '-Kirill', 'alive': '-Alexey'}.get(variant, '') }-v{ver['version']}.exe"
        inst = CB.parent / "release" / name
        print("установщик:", inst.name, f"{inst.stat().st_size / 1e6:.0f} МБ")
        s3_put(bucket, f"channels/{channel}/{name}", inst.read_bytes(), "application/vnd.microsoft.portable-executable",
               cache="public, max-age=86400")
        m["installer_url"] = f"{url}/channels/{channel}/{name}"
    if installer_url:                         # an installer already in the bucket (an older version updates itself)
        m["installer_url"] = installer_url
    sent = sent_bytes = 0
    for rel, (h, size) in sorted(files.items()):
        if exists(f"{url}/blobs/{h}"):
            continue
        data = (app / rel).read_bytes()
        if hashlib.sha256(data).hexdigest() != h:          # 2026-11-05: the app folder was rebuilt mid-upload
            raise SystemExit(f"{rel} изменился во время выкладки — пересобери и запусти выкладку заново")
        s3_put(bucket, f"blobs/{h}", data)
        sent, sent_bytes = sent + 1, sent_bytes + size
        if sent % 50 == 0:
            print(f"  ... загружено {sent} файлов, {sent_bytes / 1e6:.0f} МБ")
    raw = json.dumps(m, ensure_ascii=False, indent=1).encode("utf-8")
    sig = ed25519.sign(bytes.fromhex(SIGN_KEY.read_text().strip()), raw).hex()
    s3_put(bucket, f"channels/{channel}/manifest.json", raw, "application/json; charset=utf-8", cache="no-cache")
    s3_put(bucket, f"channels/{channel}/manifest.sig", sig.encode(), "text/plain", cache="no-cache")
    print(f"ВЫПУЩЕНО: {variant} -> канал {channel}, версия {m['version']}, файлов {len(files)}, "
          f"новых загружено {sent} ({sent_bytes / 1e6:.1f} МБ)")
    print(f"манифест: {url}/channels/{channel}/manifest.json")


if __name__ == "__main__":
    if "--init" in sys.argv:
        init()
    else:
        iu = sys.argv[sys.argv.index("--installer-url") + 1] if "--installer-url" in sys.argv else None
        publish(sys.argv[1], "--installer" in sys.argv, iu)
