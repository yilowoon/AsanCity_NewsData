"""네이버 API HUB 뉴스 검색 수집."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from email.utils import parsedate_to_datetime

from . import config, db, text

NEWS_URL = "https://naverapihub.apigw.ntruss.com/search/v1/news"


def load_env() -> None:
    env = config.ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _credentials() -> tuple[str, str]:
    load_env()
    cid, secret = os.environ.get("NAVER_CLIENT_ID", ""), os.environ.get("NAVER_CLIENT_SECRET", "")
    if not cid or not secret or cid.startswith("여기에") or secret.startswith("여기에"):
        raise SystemExit(".env 파일에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 을 입력하세요.")
    return cid, secret


def _search(cid: str, secret: str, query: str, start: int) -> dict:
    params = urllib.parse.urlencode({"query": query, "display": 100, "start": start, "sort": "date"})
    req = urllib.request.Request(
        f"{NEWS_URL}?{params}",
        headers={"X-NCP-APIGW-API-KEY-ID": cid, "X-NCP-APIGW-API-KEY": secret},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 429 and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise SystemExit(f"API 오류 HTTP {e.code} ({query}): {body}")
    return {"items": []}


def collect(conn, queries: list[str] | None = None) -> dict:
    """검색어별로 최신순 수집. 시작일 이전 기사가 나오면 그 검색어는 멈춘다."""
    cid, secret = _credentials()
    stats = {"fetched": 0, "new": 0, "irrelevant": 0}
    start_date = config.START_DATE.isoformat()

    for query in queries or config.SEARCH_QUERIES:
        reached_start = False
        for start in range(1, 1001, 100):
            data = _search(cid, secret, query, start)
            items = data.get("items", [])
            for item in items:
                stats["fetched"] += 1
                pub = parsedate_to_datetime(item["pubDate"])
                day = pub.date().isoformat()
                if day < start_date:
                    reached_start = True
                    continue
                title = text.clean(item.get("title"))
                desc = text.clean(item.get("description"))
                if not text.is_relevant(title, desc):
                    stats["irrelevant"] += 1
                    continue
                url = item.get("originallink") or item.get("link")
                domain = text.domain_of(url)
                cur = conn.execute(
                    """INSERT OR IGNORE INTO articles
                       (url, naver_link, title, description, pub_date, pub_datetime,
                        press, domain, source, query, topic)
                       VALUES (?,?,?,?,?,?,?,?, 'naver', ?, ?)""",
                    (url, item.get("link"), title, desc, day, pub.isoformat(),
                     text.press_from_domain(domain), domain, query,
                     text.classify_topic(title, desc)),
                )
                stats["new"] += cur.rowcount
            conn.commit()
            if reached_start or len(items) < 100:
                break
            time.sleep(0.15)
        print(f"  [{query}] 누적 신규 {stats['new']}건")

    db.log_run(conn, "collect", json.dumps(stats, ensure_ascii=False))
    stats["at"] = datetime.now().isoformat(timespec="seconds")
    return stats
