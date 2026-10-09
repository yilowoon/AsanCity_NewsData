"""빅카인즈(bigkinds.or.kr) 검색 결과 엑셀 가져오기 — 과거 기간 보강용."""
from datetime import datetime
from pathlib import Path

from . import db, text


def _find(header: list[str], *names: str) -> int | None:
    for name in names:
        for i, h in enumerate(header):
            if h and name in str(h):
                return i
    return None


def import_excel(conn, path: Path) -> dict:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = ws.iter_rows(values_only=True)
    header = [str(h).strip() if h else "" for h in next(rows)]
    col = {
        "date": _find(header, "일자"),
        "press": _find(header, "언론사"),
        "title": _find(header, "제목"),
        "body": _find(header, "본문"),
        "url": _find(header, "URL", "url"),
        "id": _find(header, "뉴스 식별자", "식별자"),
    }
    if col["date"] is None or col["title"] is None:
        raise SystemExit(f"빅카인즈 엑셀 형식이 아닙니다. 헤더: {header}")

    stats = {"rows": 0, "new": 0, "irrelevant": 0}
    for row in rows:
        stats["rows"] += 1
        raw_date = row[col["date"]]
        if isinstance(raw_date, datetime):
            day = raw_date.date().isoformat()
        else:
            s = str(raw_date).strip()
            day = f"{s[:4]}-{s[4:6]}-{s[6:8]}" if s.isdigit() else s[:10]
        title = text.clean(str(row[col["title"]] or ""))
        body = str(row[col["body"]] or "") if col["body"] is not None else ""
        desc = body[:200]
        if not title or not text.is_relevant(title, body):
            stats["irrelevant"] += 1
            continue
        url = str(row[col["url"]] or "").strip() if col["url"] is not None else ""
        if not url:
            url = f"bigkinds:{row[col['id']]}" if col["id"] is not None else f"bigkinds:{day}:{title}"
        press = str(row[col["press"]] or "").strip() if col["press"] is not None else ""
        cur = conn.execute(
            """INSERT OR IGNORE INTO articles
               (url, title, description, pub_date, press, domain, source, topic)
               VALUES (?,?,?,?,?,?, 'bigkinds', ?)""",
            (url, title, desc, day, press or text.press_from_domain(text.domain_of(url)),
             text.domain_of(url) if url.startswith("http") else "",
             text.classify_topic(title, desc)),
        )
        stats["new"] += cur.rowcount
    conn.commit()
    db.log_run(conn, "import_bigkinds", f"{path.name}: {stats}")
    return stats
