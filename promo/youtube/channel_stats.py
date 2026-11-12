"""Аналитика канала «Канал 15»: подписчики, просмотры, таблица по роликам.
Снимок сохраняется в promo/youtube/stats/YYYY-MM-DD.json — по ним смотрим динамику.

  python channel_stats.py            # таблица + сохранить снимок
  python channel_stats.py --no-save  # только показать

Требует scope youtube.readonly (добавляется в consent screen, см. Настройка YouTube API.md).
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

HERE = Path(__file__).resolve().parent
SECRET = HERE / "client_secret.json"
TOKEN = HERE / "token.json"
STATS_DIR = HERE / "stats"
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
]


def youtube():
    creds = None
    if TOKEN.exists():
        stored = json.loads(TOKEN.read_text(encoding="utf-8"))
        if set(SCOPES) <= set(stored.get("scopes", [])):
            creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    if not creds or not creds.valid:
        creds = InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES).run_local_server(port=0)
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds)


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    p = argparse.ArgumentParser()
    p.add_argument("--no-save", action="store_true")
    a = p.parse_args()

    yt = youtube()
    ch = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()
    if not ch.get("items"):
        sys.exit("канал не найден — вошёл не в тот аккаунт?")
    c = ch["items"][0]
    uploads = c["contentDetails"]["relatedPlaylists"]["uploads"]
    chan = {
        "title": c["snippet"]["title"],
        "subscribers": int(c["statistics"].get("subscriberCount", 0)),
        "total_views": int(c["statistics"].get("viewCount", 0)),
        "video_count": int(c["statistics"].get("videoCount", 0)),
    }

    ids = []
    page = None
    while True:
        pl = yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                     maxResults=50, pageToken=page).execute()
        ids += [i["contentDetails"]["videoId"] for i in pl["items"]]
        page = pl.get("nextPageToken")
        if not page:
            break

    videos = []
    for i in range(0, len(ids), 50):
        v = yt.videos().list(part="snippet,statistics,status",
                             id=",".join(ids[i:i + 50])).execute()
        for item in v["items"]:
            s = item["statistics"]
            videos.append({
                "id": item["id"],
                "title": item["snippet"]["title"],
                "published": item["snippet"]["publishedAt"][:10],
                "privacy": item["status"]["privacyStatus"],
                "views": int(s.get("viewCount", 0)),
                "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)),
            })
    videos.sort(key=lambda x: -x["views"])

    print(f"== {chan['title']} | подписчики: {chan['subscribers']} | "
          f"всего просмотров: {chan['total_views']} | роликов: {chan['video_count']}")
    for v in videos:
        print(f"{v['views']:>7} просм. {v['likes']:>4} лайк {v['comments']:>3} комм. "
              f"{v['published']} [{v['privacy']}] {v['title'][:60]}  https://youtu.be/{v['id']}")

    if not a.no_save:
        STATS_DIR.mkdir(exist_ok=True)
        snap = STATS_DIR / f"{date.today().isoformat()}.json"
        snap.write_text(json.dumps({"channel": chan, "videos": videos},
                                   ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nснимок сохранён: {snap}")


if __name__ == "__main__":
    main()
