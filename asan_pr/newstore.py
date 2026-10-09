"""뉴스토어(빅카인즈) 뉴스검색 API 수집 — 기간 지정 검색으로 과거분까지 빠짐없이 모은다.

API 명세: https://www.newstore.or.kr/store/prodct/news-search/api-list.do
  POST {"access_key": ..., "argument": {"query", "published_at": {"from", "until"}, "sort",
        "return_from", "return_size", "fields"}}
  return_from 최대 20,000 · return_size 최대 10,000 → 한 달 단위로 나눠 요청한다.
"""
import json
import os
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

from . import config, db, text
from .collect import load_env

BASE = "https://www.newstore.or.kr/api-newstore/v1/search/"
FIELDS = ["news_id", "title", "published_at", "provider", "category", "byline",
          "provider_link_page", "hilight"]
PAGE_SIZE = 1000


def _key() -> str:
    load_env()
    key = os.environ.get("NEWSTORE_API_KEY", "")
    if not key or key.startswith("여기에"):
        raise SystemExit(".env 파일에 NEWSTORE_API_KEY 를 입력하세요.")
    return key


def _post(endpoint: str, body: dict) -> dict:
    req = urllib.request.Request(
        BASE + endpoint, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
            break
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == 2:
                raise SystemExit(f"뉴스토어 API 오류: {e}")
            time.sleep(3 * (attempt + 1))
    if data.get("result") != 0:
        raise SystemExit(f"뉴스토어 API 오류: {data.get('reason') or data}")
    obj = data.get("returnObject") or data.get("return_object") or {}
    return json.loads(obj) if isinstance(obj, str) else obj


def _months(start: date, end: date):
    cur = start
    while cur <= end:
        nxt = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
        yield cur, min(nxt - timedelta(days=1), end)
        cur = nxt


def collect(conn, start: date | None = None, end: date | None = None,
            queries: list[str] | None = None, with_body: bool = False) -> dict:
    """기간을 월 단위로 나눠 검색어별 전체 결과를 수집한다."""
    key = _key()
    endpoint = "newsAllList.json" if with_body else "newsList.json"
    fields = FIELDS + (["content"] if with_body else [])
    start, end = start or config.START_DATE, end or date.today()
    stats = {"fetched": 0, "new": 0, "irrelevant": 0}

    for query in queries or config.SEARCH_QUERIES:
        for m_from, m_until in _months(start, end):
            offset, seen = 0, set()
            while True:
                res = _post(endpoint, {"access_key": key, "argument": {
                    "query": query,
                    "published_at": {"from": m_from.isoformat(), "until": m_until.isoformat()},
                    "sort": {"date": "asc"}, "hilight": 200,
                    "return_from": offset, "return_size": PAGE_SIZE, "fields": fields,
                }})
                docs = res.get("documents", [])
                if docs and all(d["news_id"] in seen for d in docs):
                    break   # 같은 페이지가 반복되면 중단 (시험용 키 등)
                seen.update(d["news_id"] for d in docs)
                for d in docs:
                    stats["fetched"] += 1
                    title = text.clean(d.get("title"))
                    desc = text.clean(d.get("content") or d.get("hilight"))
                    if not text.is_relevant(title, desc):
                        stats["irrelevant"] += 1
                        continue
                    url = d.get("provider_link_page") or f"bigkinds:{d['news_id']}"
                    day = (d.get("published_at") or "")[:10]
                    cur = conn.execute(
                        """INSERT OR IGNORE INTO articles
                           (url, title, description, pub_date, pub_datetime, press, domain,
                            source, query, topic)
                           VALUES (?,?,?,?,?,?,?, 'newstore', ?, ?)""",
                        (url, title, desc[:300], day, d.get("dateline") or d.get("published_at"),
                         d.get("provider"), text.domain_of(url) if url.startswith("http") else "",
                         query, text.classify_topic(title, desc)),
                    )
                    stats["new"] += cur.rowcount
                conn.commit()
                offset += len(docs)
                total = res.get("total_hits", 0)
                if not docs or offset >= total or offset >= 20_000:
                    break
                time.sleep(0.3)
            print(f"  [{query}] {m_from:%Y-%m} 누적 신규 {stats['new']}건")

    db.log_run(conn, "newstore", json.dumps(stats, ensure_ascii=False))
    return stats
