"""Выкладка установщика в GitHub-релиз: версионный ассет + стабильный Kanal15-Setup.exe.

    python tools/publish_github.py v1.36 release/Kanal15-Setup-v1.36.exe   # создать релиз тега (если нет) и залить оба ассета
    python tools/publish_github.py v1.36 release/Kanal15-Setup-v1.36.exe --stable-only  # только стабильное имя

Стабильная ссылка https://github.com/straysouler-svg/kanal15/releases/latest/download/Kanal15-Setup.exe
работает, только если ассет с таким именем есть в ПОСЛЕДНЕМ релизе. Поэтому при выкладке нового релиза
сюда же заливается копия установщика под стабильным именем (старый одноимённый ассет из этого релиза
сначала удаляется — GitHub не принимает дубли имён).

Авторизация: переменная GH_TOKEN, иначе токен читается из git credential (как у git push).
Апдейтер рации updater.py НЕ зависит от этих имён: он берёт installer_url из подписанного манифеста
в Object Storage (см. publish_update.py), сюда обращаются только люди по ссылке со страниц релизов.
"""
import argparse
import json
import os
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO = "straysouler-svg/kanal15"
STABLE = "Kanal15-Setup.exe"
UA = {"Accept": "application/vnd.github+json", "User-Agent": "kanal15-release", "X-GitHub-Api-Version": "2022-11-28"}


def gh_token():
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok.strip()
    out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                         capture_output=True, text=True, encoding="utf-8").stdout
    for ln in out.splitlines():
        if ln.startswith("password="):
            return ln.split("=", 1)[1].strip()
    raise SystemExit("нет токена GitHub: задайте GH_TOKEN или настройте git credential")


def api(method, url, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={**UA, "Authorization": f"Bearer {token}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read()) if r.status != 204 else {}
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {url}: HTTP {e.code}: {e.read()[:400]!r}")


def upload(upload_url, name, path, token):
    """upload_url — шаблон .../releases/<id>/assets{?name,...} из объекта релиза. Через curl:
    urllib на больших файлах уходит в chunked/400, а curl шлёт нормально (проверено 2026-11-18)."""
    url = upload_url.replace("{?name,label}", "") + "?" + urllib.parse.urlencode({"name": name})
    r = subprocess.run(["curl", "-sS", "-X", "POST", "-H", f"Authorization: Bearer {token}",
                        "-H", "Accept: application/vnd.github+json",
                        "-H", "Content-Type: application/octet-stream",
                        "--data-binary", f"@{path}", "-w", "%{http_code}", url],
                       capture_output=True, text=True, encoding="utf-8", timeout=7200)
    code = r.stdout.strip()[-3:]
    if code != "201":
        raise SystemExit(f"upload {name}: HTTP {code}: {r.stdout[-400:]!r} {r.stderr[-200:]!r}")
    a = json.loads(r.stdout[:-3])      # тело JSON + напечатанный в конце код 201
    print(f"  залит {name} ({path.stat().st_size / 1e6:.0f} МБ) -> {a['browser_download_url']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("tag")
    p.add_argument("installer", type=Path)
    p.add_argument("--stable-only", action="store_true", help="не трогать версионный ассет")
    a = p.parse_args()
    if not a.installer.is_file():
        raise SystemExit(f"нет файла: {a.installer}")
    token = gh_token()
    base = f"https://api.github.com/repos/{REPO}"

    rel = None
    for r in api("GET", f"{base}/releases?per_page=100", token):
        if r["tag_name"] == a.tag:
            rel = r
            break
    if rel is None:
        ver = json.loads((Path(__file__).resolve().parents[1] / "version.json").read_text(encoding="utf-8"))
        rel = api("POST", f"{base}/releases",
                  {"tag_name": a.tag, "name": a.tag, "body": f"Канал 15, версия {ver['version']}. Подробности — в CHANGELOG.md."},
                  token)
        print(f"создан релиз {a.tag}")

    assets = {x["name"]: x for x in rel["assets"]}
    if not a.stable_only:
        ver_name = a.installer.name
        if ver_name in assets:
            print(f"  версионный ассет {ver_name} уже есть — пропускаю")
        else:
            upload(rel["upload_url"], ver_name, a.installer, token)
            rel = api("GET", rel["url"], token)
            assets = {x["name"]: x for x in rel["assets"]}

    if STABLE in assets:
        api("DELETE", assets[STABLE]["url"], token)
        print(f"  старый {STABLE} удалён из {a.tag}")
    upload(rel["upload_url"], STABLE, a.installer, token)


if __name__ == "__main__":
    main()
