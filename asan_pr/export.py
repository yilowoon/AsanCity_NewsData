"""DB → 대시보드용 data.js (브라우저에서 파일을 바로 열어도 동작하도록 JS 로 내보낸다)."""
import json
from datetime import datetime
from pathlib import Path

from . import config


def export(conn, out: Path, sample: bool = False) -> dict:
    rows = conn.execute(
        """SELECT id, pub_date, cluster_id, press, title, url, views, topic, source
           FROM articles ORDER BY pub_date, id"""
    ).fetchall()
    press_list, topic_list = [], []
    press_idx, topic_idx = {}, {}

    def idx(value, table, lookup):
        value = value or "미상"
        if value not in lookup:
            lookup[value] = len(table)
            table.append(value)
        return lookup[value]

    articles = []
    for r in rows:
        url = r["url"] if r["url"].startswith("http") else ""
        articles.append([
            r["id"], r["pub_date"], r["cluster_id"] or r["id"],
            idx(r["press"], press_list, press_idx), r["title"], url, r["views"],
            idx(r["topic"], topic_list, topic_idx),
        ])
    clusters = {
        str(c["id"]): c["title"]
        for c in conn.execute("SELECT id, title FROM clusters")
    }
    last_run = conn.execute("SELECT max(started) FROM runs").fetchone()[0]
    sources = dict(conn.execute("SELECT source, count(*) FROM articles GROUP BY source").fetchall())
    payload = {
        "meta": {
            "generated": datetime.now().isoformat(timespec="minutes"),
            "lastRun": last_run,
            "sample": sample,
            "startDate": config.START_DATE.isoformat(),
            "sources": sources,
            "queries": config.SEARCH_QUERIES,
        },
        "press": press_list,
        "topics": topic_list,
        "clusters": clusters,
        "articles": articles,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("window.ASAN_DATA = " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n",
                   encoding="utf-8")
    return {"articles": len(articles), "clusters": len(clusters), "file": str(out)}
