"""Журналы от игроков (2026-11-06): кнопка «Отправить журнал разработчикам…» кладёт архив в хранилище «только для приёма».

    python tools/reports.py --setup    # один раз: создать бакет kanal15-reports, разрешить всем ТОЛЬКО класть в in/
    python tools/reports.py --check    # проверить: аноним может положить, но не может прочитать и перечислить
    python tools/reports.py --fetch    # скачать новые отчёты в promo/telegram/inbox/reports/ (наш закрытый ключ)

Ключ: cb-radio/yandex_storage_key.txt (как у publish_update). В рации НЕТ никаких ключей: она делает анонимный PUT."""
import datetime
import hashlib
import hmac
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CB = Path(__file__).resolve().parents[1]
S3_KEY = CB / "yandex_storage_key.txt"
HOST, REGION = "storage.yandexcloud.net", "ru-central1"
BUCKET = "kanal15-reports"
INBOX = CB.parent / "promo" / "telegram" / "inbox" / "reports"


def s3(method, path, query="", data=b"", headers=None, key_file=None):
    """Signed request (AWS Signature V4) with our private key. path = "/bucket/key"."""
    kid, secret = [x.strip() for x in (key_file or S3_KEY).read_text(encoding="utf-8-sig").splitlines()[:2]]
    now = datetime.datetime.now(datetime.timezone.utc)
    amz, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    ph = hashlib.sha256(data).hexdigest()
    hdr = {"host": HOST, "x-amz-content-sha256": ph, "x-amz-date": amz}
    hdr.update({k.lower(): v for k, v in (headers or {}).items()})
    uri = urllib.parse.quote(path, safe="/~")
    q = "&".join(sorted(f"{urllib.parse.quote(k, safe='~')}={urllib.parse.quote(v, safe='~')}"
                        for k, v in urllib.parse.parse_qsl(query, keep_blank_values=True)))
    signed = ";".join(sorted(hdr))
    canon = "\n".join([method, uri, q, "".join(f"{k}:{hdr[k]}\n" for k in sorted(hdr)), signed, ph])
    scope = f"{day}/{REGION}/s3/aws4_request"
    sts = "\n".join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(canon.encode()).hexdigest()])
    k = hmac.new(("AWS4" + secret).encode(), day.encode(), hashlib.sha256).digest()
    for part in (REGION, "s3", "aws4_request"):
        k = hmac.new(k, part.encode(), hashlib.sha256).digest()
    sig = hmac.new(k, sts.encode(), hashlib.sha256).hexdigest()
    hdr["authorization"] = f"AWS4-HMAC-SHA256 Credential={kid}/{scope}, SignedHeaders={signed}, Signature={sig}"
    url = f"https://{HOST}{uri}" + (f"?{query}" if query else "")
    req = urllib.request.Request(url, data=data if method in ("PUT", "POST") else None, method=method,
                                 headers={k: v for k, v in hdr.items() if k != "host"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.status, r.read()


POLICY = {
    "Version": "2012-10-17",
    "Statement": [{"Effect": "Allow", "Principal": "*", "Action": "s3:PutObject",
                   "Resource": f"arn:aws:s3:::{BUCKET}/in/*"}],
}


def setup():
    try:
        print("бакет:", s3("PUT", f"/{BUCKET}")[0])
    except urllib.error.HTTPError as e:
        print("бакет:", e.code, e.read()[:200])
    body = json.dumps(POLICY).encode()
    print("политика:", s3("PUT", f"/{BUCKET}", "policy", body, {"content-type": "application/json"})[0])
    # журналы удаляются сами через 30 дней (так и написано игроку в окне отправки)
    import base64
    lc = (b'<?xml version="1.0" encoding="UTF-8"?><LifecycleConfiguration><Rule><ID>delete-after-30-days</ID>'
          b'<Status>Enabled</Status><Filter><Prefix>in/</Prefix></Filter><Expiration><Days>30</Days></Expiration>'
          b'</Rule></LifecycleConfiguration>')
    md5 = base64.b64encode(hashlib.md5(lc).digest()).decode()
    print("удаление через 30 дней:", s3("PUT", f"/{BUCKET}", "lifecycle", lc,
                                        {"content-type": "application/xml", "content-md5": md5})[0])


def anon(method, url, data=None):
    try:
        req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/zip"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def check():
    key = f"in/_check_{datetime.datetime.now():%Y%m%d-%H%M%S}.zip"
    url = f"https://{HOST}/{BUCKET}/{key}"
    print("аноним кладёт:", anon("PUT", url, b"test"), "(нужно 200)")
    print("аноним читает:", anon("GET", url), "(нужно 403)")
    print("аноним перечисляет:", anon("GET", f"https://{HOST}/{BUCKET}?list-type=2"), "(нужно 403)")
    print("мы удаляем проверочный:", s3("DELETE", f"/{BUCKET}/{key}")[0])


def fetch():
    INBOX.mkdir(parents=True, exist_ok=True)
    st, body = s3("GET", f"/{BUCKET}", "list-type=2&prefix=in/")
    keys = re.findall(r"<Key>([^<]+)</Key>", body.decode())
    new = 0
    for k in keys:
        name = k.split("/")[-1]
        if name.startswith("_check_") or (INBOX / name).exists():
            continue
        st, data = s3("GET", f"/{BUCKET}/{k}")
        (INBOX / name).write_bytes(data)
        new += 1
        print("новый отчёт:", name, len(data) // 1024, "КБ")
    return new


if __name__ == "__main__":
    a = sys.argv[1:] or ["--fetch"]
    {"--setup": setup, "--check": check, "--fetch": fetch}[a[0]]()
