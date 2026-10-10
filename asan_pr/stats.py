"""홍보 성과 통계 분석 — 수치는 모두 여기서 결정적으로 계산하고, LLM 은 해석만 맡는다.

분석 항목
  A. 기술통계 (주간·일간 보도 건수)
  B. 추세 분석 (주차 ↔ 보도 건수: 선형회귀 + Spearman)
  C. 상관분석 (주간 지표 간 Pearson·Spearman, 95% 신뢰구간, Holm 보정)
  D. 요일 효과 (평일 vs 주말 Mann-Whitney U, 요일별 Kruskal-Wallis)
  E. 주제별 확산력 차이 (이슈당 보도 매체 수, Kruskal-Wallis)
  F. 주제 구성 변화 (주제 × 월 카이제곱 독립성 검정, Cramér's V)
  G. 홍보비 연계 (data/budget.csv 가 있을 때 월별 상관)
"""
import csv
import math
from collections import Counter, defaultdict
from datetime import date, timedelta

import numpy as np
from scipy import stats as st

from . import config

ALPHA = 0.05


def _r(x, nd=4):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), nd)


def _p(x):
    """p값은 반올림으로 0이 되지 않도록 유효숫자 3자리로 보관."""
    return None if x is None or not math.isfinite(float(x)) else float(f"{float(x):.3g}")


def _sig(p):
    if p is None:
        return "판단 불가"
    return "매우 유의 (p<0.001)" if p < 0.001 else "유의 (p<0.01)" if p < 0.01 else "유의 (p<0.05)" if p < ALPHA else "유의하지 않음"


def _strength(r):
    a = abs(r)
    return "매우 강함" if a >= 0.8 else "강함" if a >= 0.6 else "중간" if a >= 0.4 else "약함" if a >= 0.2 else "거의 없음"


def _pearson_ci(r, n):
    if n <= 3 or abs(r) >= 1:
        return None, None
    z, se = math.atanh(r), 1 / math.sqrt(n - 3)
    return math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)


def _holm(pvals):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    adj, running = [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(pvals) - rank) * pvals[i]))
        adj[i] = running
    return adj


def _load(conn):
    rows = conn.execute("SELECT pub_date, press, topic, cluster_id, views, source FROM articles").fetchall()
    return [dict(r) for r in rows]


def _week(d: str) -> str:
    x = date.fromisoformat(d)
    return (x - timedelta(days=x.weekday())).isoformat()


def analyze(conn) -> dict:
    arts = _load(conn)
    if len(arts) < 30:
        return {"ok": False, "reason": "분석에 필요한 기사 수가 부족합니다."}
    first, last = min(a["pub_date"] for a in arts), max(a["pub_date"] for a in arts)

    # ── 주간 집계 (마지막 미완성 주는 제외) ──
    weeks = defaultdict(list)
    for a in arts:
        weeks[_week(a["pub_date"])].append(a)
    last_week_start = _week(last)
    full_weeks = sorted(w for w in weeks if w != last_week_start and w >= _week(first))
    if date.fromisoformat(last).weekday() == 6:
        full_weeks.append(last_week_start)
    W = []
    for w in full_weeks:
        items = weeks[w]
        clusters = defaultdict(set)
        for a in items:
            clusters[a["cluster_id"]].add(a["press"])
        views = [a["views"] for a in items if a["views"] is not None]
        W.append({
            "week": w, "articles": len(items), "issues": len(clusters),
            "press": len({a["press"] for a in items}),
            "wide": sum(1 for p in clusters.values() if len(p) >= 5),
            "spread": len(items) / len(clusters),
            "views": sum(views) if views else None,
        })
    n_w = len(W)
    y = np.array([w["articles"] for w in W], float)

    # ── 일간 집계 ──
    daily = Counter(a["pub_date"] for a in arts)
    d0, d1 = date.fromisoformat(first), date.fromisoformat(last)
    days = [(d0 + timedelta(i)) for i in range((d1 - d0).days + 1)]
    dcount = np.array([daily.get(d.isoformat(), 0) for d in days], float)

    out = {"ok": True, "period": {"from": first, "until": last, "days": len(days), "weeks": n_w},
           "n_articles": len(arts), "alpha": ALPHA}

    # A. 기술통계
    def desc(v):
        return {"n": int(len(v)), "mean": _r(v.mean(), 2), "sd": _r(v.std(ddof=1), 2), "median": _r(np.median(v), 1),
                "min": int(v.min()), "max": int(v.max()), "cv": _r(v.std(ddof=1) / v.mean(), 3) if v.mean() else None}
    out["descriptive"] = {"weekly_articles": desc(y), "daily_articles": desc(dcount)}

    # B. 추세
    t = np.arange(n_w, dtype=float)
    lr = st.linregress(t, y)
    sp = st.spearmanr(t, y)
    out["trend"] = {
        "n": n_w, "slope_per_week": _r(lr.slope, 2), "intercept": _r(lr.intercept, 2),
        "r2": _r(lr.rvalue ** 2, 3), "p": _p(lr.pvalue), "spearman_rho": _r(sp.statistic, 3), "spearman_p": _p(sp.pvalue),
        "significance": _sig(lr.pvalue),
        "direction": "증가" if lr.slope > 0 else "감소",
        "series": [{"week": w["week"], "articles": w["articles"]} for w in W],
    }

    # C. 상관분석 (주간)
    pairs = [
        ("issues", "통합 이슈 수", "보도자료·이슈가 많을수록 보도량이 늘어나는가",
         "보도 건수 = 이슈 수 × 이슈당 보도 건수이므로 구조적으로 높은 상관이 예상됨. '이슈당 보도 건수'와의 상관과 비교하여 보도량 변동의 주된 원인을 판단하는 용도"),
        ("press", "보도 매체 수", "보도 매체 저변이 넓을수록 보도량이 늘어나는가", ""),
        ("wide", "대형 확산 이슈 수", "대형 확산 이슈가 보도량을 견인하는가", ""),
        ("spread", "이슈당 평균 보도 건수", "이슈의 확산력이 보도량과 관련 있는가", ""),
    ]
    corr = []
    for key, label, question, note in pairs:
        x = np.array([w[key] for w in W], float)
        pr, sr = st.pearsonr(x, y), st.spearmanr(x, y)
        lo, hi = _pearson_ci(pr.statistic, n_w)
        corr.append({"var": key, "label": label, "target": "주간 보도 건수", "question": question, "n": n_w,
                     "pearson_r": _r(pr.statistic, 3), "pearson_p": _p(pr.pvalue), "ci95": [_r(lo, 3), _r(hi, 3)],
                     "spearman_rho": _r(sr.statistic, 3), "spearman_p": _p(sr.pvalue),
                     "strength": _strength(pr.statistic), "note": note,
                     "points": [[_r(w[key], 3), w["articles"]] for w in W]})
    vw = [w for w in W if w["views"]]
    if len(vw) >= 5:
        x, yy = np.array([w["views"] for w in vw], float), np.array([w["articles"] for w in vw], float)
        pr, sr = st.pearsonr(x, yy), st.spearmanr(x, yy)
        lo, hi = _pearson_ci(pr.statistic, len(vw))
        corr.append({"var": "views", "label": "확인 조회수", "target": "주간 보도 건수", "question": "보도량이 많을수록 조회수(도달)도 높은가",
                     "n": len(vw), "pearson_r": _r(pr.statistic, 3), "pearson_p": _p(pr.pvalue), "ci95": [_r(lo, 3), _r(hi, 3)],
                     "spearman_rho": _r(sr.statistic, 3), "spearman_p": _p(sr.pvalue), "strength": _strength(pr.statistic),
                     "points": [[w["views"], w["articles"]] for w in vw], "small_sample": True})
    adj = _holm([c["pearson_p"] for c in corr])
    for c, p in zip(corr, adj):
        c["p_holm"] = _p(p)
        c["significance"] = _sig(p)
    out["correlation"] = corr

    # 상관행렬 (주간 지표)
    keys = [("articles", "보도 건수"), ("issues", "통합 이슈"), ("press", "보도 매체"), ("wide", "대형 확산"), ("spread", "이슈당 보도")]
    M = np.array([[w[k] for k, _ in keys] for w in W], float)
    R = np.corrcoef(M, rowvar=False)
    out["corr_matrix"] = {"labels": [l for _, l in keys], "r": [[_r(v, 3) for v in row] for row in R]}

    # D. 요일 효과
    names = ["월", "화", "수", "목", "금", "토", "일"]
    by_wd = [dcount[[d.weekday() == k for d in days]] for k in range(7)]
    weekday = np.concatenate(by_wd[:5]); weekend = np.concatenate(by_wd[5:])
    mw = st.mannwhitneyu(weekday, weekend, alternative="two-sided")
    z = st.norm.isf(mw.pvalue / 2) if mw.pvalue > 0 else 10.0
    kw = st.kruskal(*by_wd)
    out["weekday"] = {
        "means": [{"day": names[k], "mean": _r(by_wd[k].mean(), 2), "n": int(len(by_wd[k]))} for k in range(7)],
        "weekday_mean": _r(weekday.mean(), 2), "weekend_mean": _r(weekend.mean(), 2),
        "ratio": _r(weekday.mean() / weekend.mean(), 2) if weekend.mean() else None,
        "mannwhitney_u": _r(mw.statistic, 1), "p": _p(mw.pvalue), "effect_r": _r(z / math.sqrt(len(dcount)), 3),
        "kruskal_h": _r(kw.statistic, 2), "kruskal_p": _p(kw.pvalue), "significance": _sig(mw.pvalue),
    }

    # E. 주제별 확산력 (이슈 단위: 보도 매체 수)
    cl = defaultdict(lambda: {"press": set(), "topics": Counter()})
    for a in arts:
        c = cl[a["cluster_id"]]
        c["press"].add(a["press"]); c["topics"][a["topic"]] += 1
    by_topic = defaultdict(list)
    for c in cl.values():
        by_topic[c["topics"].most_common(1)[0][0]].append(len(c["press"]))
    groups = {k: np.array(v, float) for k, v in by_topic.items() if len(v) >= 20}
    if len(groups) >= 3:
        kw = st.kruskal(*groups.values())
        n_total = sum(len(v) for v in groups.values())
        eps2 = (kw.statistic - len(groups) + 1) / (n_total - len(groups))
        out["topic_spread"] = {
            "groups": sorted([{"topic": k, "issues": int(len(v)), "mean_press": _r(v.mean(), 2), "median_press": _r(np.median(v), 1),
                               "wide_share": _r((v >= 5).mean(), 3)} for k, v in groups.items()],
                             key=lambda g: -g["mean_press"]),
            "kruskal_h": _r(kw.statistic, 2), "p": _p(kw.pvalue), "epsilon2": _r(max(eps2, 0), 3),
            "significance": _sig(kw.pvalue),
        }

    # F. 주제 구성 변화 (주제 × 월)
    months = sorted({a["pub_date"][:7] for a in arts})
    topics = [k for k, _ in Counter(a["topic"] for a in arts).most_common()]
    table = np.array([[sum(1 for a in arts if a["pub_date"][:7] == m and a["topic"] == tp) for m in months] for tp in topics], float)
    chi = st.chi2_contingency(table)
    v = math.sqrt(chi.statistic / (table.sum() * (min(table.shape) - 1)))
    out["topic_month"] = {"chi2": _r(chi.statistic, 2), "dof": int(chi.dof), "p": _p(chi.pvalue), "cramers_v": _r(v, 3),
                          "significance": _sig(chi.pvalue), "months": months, "topics": topics,
                          "share": {tp: [_r(table[i, j] / table[:, j].sum(), 3) for j in range(len(months))]
                                    for i, tp in enumerate(topics)}}

    # G. 홍보비 연계
    budget_file = config.DATA_DIR / "budget.csv"
    if budget_file.exists():
        with open(budget_file, encoding="utf-8-sig") as f:
            budget = {r["month"]: float(r["amount"]) for r in csv.DictReader(f)}
        mcount = Counter(a["pub_date"][:7] for a in arts)
        ms = [m for m in months if m in budget]
        if len(ms) >= 4:
            x, yy = np.array([budget[m] for m in ms]), np.array([mcount[m] for m in ms], float)
            pr, sr = st.pearsonr(x, yy), st.spearmanr(x, yy)
            out["budget"] = {"n": len(ms), "pearson_r": _r(pr.statistic, 3), "pearson_p": _p(pr.pvalue),
                             "spearman_rho": _r(sr.statistic, 3), "spearman_p": _p(sr.pvalue), "significance": _sig(pr.pvalue),
                             "cost_per_article": _r(x.sum() / yy.sum(), 0),
                             "points": [[m, budget[m], mcount[m]] for m in ms]}
    if "budget" not in out:
        out["budget"] = {"available": False, "note": "홍보비 집행 자료(data/budget.csv: month,amount) 연계 시 분석"}

    # 데이터 한계 (해석 시 반드시 함께 제시)
    sources = Counter(a["source"] for a in arts)
    limits = ["주간 시계열은 자기상관이 있을 수 있어 상관분석의 p값은 참고용으로 해석해야 함",
              "상관관계는 인과관계를 의미하지 않음"]
    if set(sources) <= {"naver"}:
        limits.insert(0, "현재 자료는 포털 검색 API 기준으로 검색어별 최근 1,000건만 수집되어 과거 기간이 과소 집계됨 — 추세·상관 결과에 수집 편향이 반영될 수 있음")
    if len(vw) < 20:
        limits.append(f"조회수 공개 주가 {len(vw)}주에 불과하여 도달 지표(조회수) 관련 결과는 결론을 유보함")
    out["limitations"] = limits
    out["sources"] = dict(sources)
    return out
