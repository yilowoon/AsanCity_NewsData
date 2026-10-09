"""제목이 유사한 기사를 하나의 이슈(통합 제목)로 묶는다."""
from collections import Counter, defaultdict
from datetime import date, timedelta

from . import config, db, text


def _jaccard(a: frozenset, b: frozenset) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def build_clusters(conn) -> dict:
    rows = conn.execute(
        "SELECT id, title, pub_date, press, views, topic FROM articles ORDER BY pub_date, id"
    ).fetchall()
    n = len(rows)
    grams = [text.bigrams(r["title"]) for r in rows]
    parent = list(range(n))
    first = [r["pub_date"] for r in rows]   # 루트별 이슈 첫 보도일 (연쇄 병합으로 이슈가 길어지는 것 방지)

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    # (날짜, 단어) → 기사 인덱스. 같은 단어를 공유하는 최근 기사만 비교한다.
    index: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, r in enumerate(rows):
        d = date.fromisoformat(r["pub_date"])
        days = [(d - timedelta(days=k)).isoformat() for k in range(config.CLUSTER_WINDOW_DAYS + 1)]
        seen: set[int] = set()
        for w in text.words(r["title"]):
            for day in days:
                for j in index.get((day, w), ()):
                    if j in seen:
                        continue
                    seen.add(j)
                    if _jaccard(grams[i], grams[j]) < config.CLUSTER_SIMILARITY:
                        continue
                    ri, rj = find(i), find(j)
                    if ri == rj:
                        continue
                    start = min(first[ri], first[rj])
                    if (d - date.fromisoformat(start)).days > config.CLUSTER_MAX_SPAN_DAYS:
                        continue
                    parent[ri] = rj
                    first[rj] = start
            index[(r["pub_date"], w)].append(i)

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(i)

    conn.execute("DELETE FROM clusters")
    for members in groups.values():
        cid = min(rows[i]["id"] for i in members)
        # 대표 제목: 다른 제목들과 평균 유사도가 가장 높은 제목 (medoid)
        sample = members[:40]
        if len(sample) <= 2:
            rep = min(sample, key=lambda i: len(rows[i]["title"]))
        else:
            rep = max(sample, key=lambda i: sum(_jaccard(grams[i], grams[j]) for j in sample))
        views = [rows[i]["views"] for i in members if rows[i]["views"] is not None]
        topic = Counter(rows[i]["topic"] for i in members).most_common(1)[0][0]
        conn.execute(
            """INSERT INTO clusters(id, title, first_date, last_date, article_cnt, press_cnt, views_sum, topic)
               VALUES (?,?,?,?,?,?,?,?)""",
            (cid, text.strip_prefix(rows[rep]["title"]), min(rows[i]["pub_date"] for i in members),
             max(rows[i]["pub_date"] for i in members), len(members),
             len({rows[i]["press"] for i in members}), sum(views) if views else None, topic),
        )
        conn.executemany("UPDATE articles SET cluster_id=? WHERE id=?",
                         [(cid, rows[i]["id"]) for i in members])
    conn.commit()
    stats = {"articles": n, "clusters": len(groups),
             "multi": sum(1 for m in groups.values() if len(m) > 1)}
    db.log_run(conn, "cluster", str(stats))
    return stats
