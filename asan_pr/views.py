"""기사 원문 페이지에 공개된 조회수를 읽어온다.

언론사 내부 통계는 외부에서 볼 수 없으므로, 페이지에 '조회수'를 표시하는 매체(주로 지역
인터넷신문 CMS)만 수집된다. robots.txt 에서 막힌 사이트는 건너뛴다.
"""
import re
import threading
import urllib.error
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

from . import config, db, text

_VIEW_PATTERNS = [
    # 날짜(2026.10.09) 오인을 막기 위해 숫자 뒤에 . - / 와 숫자가 이어지면 제외
    re.compile(r"조회\s*수?\s*[:：]?\s*([0-9][0-9,]{0,10})(?![0-9,]*[.\-/][0-9])"),
    re.compile(r"(?:Hit|hit|HIT|Views?)\s*[:：]?\s*([0-9][0-9,]{0,10})(?![0-9,]*[.\-/][0-9])"),
]
_SITE_NAME = re.compile(
    r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)["\']', re.I)
_SITE_NAME_REV = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:site_name["\']', re.I)
_CHARSET = re.compile(rb'charset=["\']?([A-Za-z0-9_-]+)', re.I)
_TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>|<[^>]+>", re.S | re.I)

_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
_robots_lock = threading.Lock()


def _allowed(url: str) -> bool:
    domain = url.split("/")[2]
    with _robots_lock:
        if domain not in _robots:
            rp = urllib.robotparser.RobotFileParser(f"https://{domain}/robots.txt")
            try:
                rp.read()
            except Exception:
                rp = None
            _robots[domain] = rp
        rp = _robots[domain]
    return rp is None or rp.can_fetch(config.USER_AGENT, url)


def _decode(raw: bytes, header_charset: str | None) -> str:
    candidates = [header_charset] if header_charset else []
    m = _CHARSET.search(raw[:3000])
    if m:
        candidates.append(m.group(1).decode())
    candidates += ["utf-8", "cp949"]
    for cs in candidates:
        try:
            return raw.decode(cs)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", "replace")


def parse_page(page: str) -> tuple[int | None, str | None]:
    site = _SITE_NAME.search(page) or _SITE_NAME_REV.search(page)
    body = _TAGS.sub(" ", page)
    body = re.sub(r"\s+", " ", body)
    views = None
    for pat in _VIEW_PATTERNS:
        m = pat.search(body)
        if m:
            views = int(m.group(1).replace(",", ""))
            break
    return views, (site.group(1).strip() if site else None)


def fetch_one(url: str) -> tuple[str, int | None, str | None]:
    if not url.startswith("http") or "news.naver.com" in url:
        return "none", None, None
    if not _allowed(url):
        return "blocked", None, None
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as resp:
            raw = resp.read(1_500_000)
            page = _decode(raw, resp.headers.get_content_charset())
    except Exception:
        return "error", None, None
    views, site = parse_page(page)
    if text.domain_of(url) not in config.VIEWS_TRUSTED_DOMAINS:
        views = None   # 매체명(og:site_name)만 사용
    return ("ok" if views is not None else "none"), views, site


def update_views(conn, limit: int | None = None) -> dict:
    recheck_from = (date.today() - timedelta(days=config.VIEWS_RECHECK_DAYS)).isoformat()
    today = date.today().isoformat()
    sql = """SELECT id, url FROM articles
             WHERE views_checked IS NULL
                OR (pub_date >= ? AND substr(views_checked, 1, 10) < ? AND views_status = 'ok')
             ORDER BY pub_date DESC"""
    targets = conn.execute(sql, (recheck_from, today)).fetchall()
    if limit:
        targets = targets[:limit]

    stats = {"checked": 0, "ok": 0, "none": 0, "error": 0, "blocked": 0}
    now = datetime.now().isoformat(timespec="seconds")
    with ThreadPoolExecutor(config.VIEWS_WORKERS) as pool:
        for row, (status, views, site) in zip(targets, pool.map(lambda r: fetch_one(r["url"]), targets)):
            stats["checked"] += 1
            stats[status] += 1
            conn.execute(
                """UPDATE articles SET views=COALESCE(?, views), views_status=?, views_checked=?,
                   press=CASE WHEN ? IS NOT NULL AND (press IS NULL OR press = domain) THEN ? ELSE press END
                   WHERE id=?""",
                (views, status, now, site, site, row["id"]),
            )
            if stats["checked"] % 100 == 0:
                conn.commit()
                print(f"  조회수 확인 {stats['checked']}/{len(targets)} (확보 {stats['ok']})")
    conn.commit()
    db.log_run(conn, "views", str(stats))
    return stats
