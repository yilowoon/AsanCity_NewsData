"""SQLite 저장소."""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT NOT NULL UNIQUE,      -- 원문 링크 (없으면 네이버 링크)
    naver_link    TEXT,
    title         TEXT NOT NULL,
    description   TEXT,
    pub_date      TEXT NOT NULL,             -- YYYY-MM-DD
    pub_datetime  TEXT,                      -- ISO 8601
    press         TEXT,                      -- 매체명
    domain        TEXT,
    source        TEXT NOT NULL,             -- naver | bigkinds | sample
    query         TEXT,                      -- 수집에 쓴 검색어
    topic         TEXT,
    cluster_id    INTEGER,
    views         INTEGER,                   -- 원문 페이지에 공개된 조회수
    views_checked TEXT,                      -- 조회수 확인 시각
    views_status  TEXT,                      -- ok | none | error | blocked
    collected_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE INDEX IF NOT EXISTS idx_articles_date ON articles(pub_date);
CREATE INDEX IF NOT EXISTS idx_articles_cluster ON articles(cluster_id);

CREATE TABLE IF NOT EXISTS clusters (
    id           INTEGER PRIMARY KEY,
    title        TEXT NOT NULL,              -- 통합 제목
    first_date   TEXT NOT NULL,
    last_date    TEXT NOT NULL,
    article_cnt  INTEGER NOT NULL,
    press_cnt    INTEGER NOT NULL,
    views_sum    INTEGER,
    topic        TEXT
);

CREATE TABLE IF NOT EXISTS runs (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    step      TEXT NOT NULL,
    started   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    detail    TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def log_run(conn: sqlite3.Connection, step: str, detail: str) -> None:
    conn.execute("INSERT INTO runs(step, detail) VALUES (?, ?)", (step, detail))
    conn.commit()
