"""아산시 홍보 사업 성과 분석 시스템 — 실행 진입점.

  python run.py daily                 # 수집 → 통합 → 조회수 → 대시보드 (매일 실행)
  python run.py collect               # 네이버 API HUB 뉴스 수집만
  python run.py newstore [--from 2026-01-01] [--until 2026-10-09] [--body]
                                      # 뉴스토어(빅카인즈) API 기간 수집
  python run.py bigkinds 파일.xlsx    # 빅카인즈 엑셀 가져오기 (과거분 보강)
  python run.py cluster               # 유사 제목 통합
  python run.py views [--limit N]     # 원문 페이지 조회수 확인
  python run.py build                 # 대시보드 데이터 생성
  python run.py sample                # 샘플 데이터로 대시보드 미리보기
"""
import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from asan_pr import cluster, config, db, export

sys.stdout.reconfigure(encoding="utf-8")
DATA_JS = config.DASHBOARD_DIR / "data.js"


def main() -> None:
    p = argparse.ArgumentParser(description="아산시 홍보 성과 분석")
    p.add_argument("command", choices=["daily", "collect", "newstore", "bigkinds", "cluster", "views", "build", "sample"])
    p.add_argument("file", nargs="?", help="빅카인즈 엑셀 경로")
    p.add_argument("--limit", type=int, help="조회수 확인 최대 건수")
    p.add_argument("--from", dest="date_from", type=date.fromisoformat, help="뉴스토어 수집 시작일")
    p.add_argument("--until", dest="date_until", type=date.fromisoformat, help="뉴스토어 수집 종료일")
    p.add_argument("--body", action="store_true", help="본문 포함 API 사용 (본문포함 상품 구매 시)")
    args = p.parse_args()

    if args.command == "sample":
        from asan_pr import sample
        conn = db.connect(config.SAMPLE_DB_PATH)
        print("샘플 생성:", sample.generate(conn))
        print("통합:", cluster.build_clusters(conn))
        print("내보내기:", export.export(conn, DATA_JS, sample=True))
        return

    conn = db.connect(config.DB_PATH)
    if args.command in ("collect", "daily"):
        from asan_pr import collect
        print("수집:", collect.collect(conn))
    if args.command == "newstore":
        from asan_pr import newstore
        print("뉴스토어:", newstore.collect(conn, args.date_from, args.date_until, with_body=args.body))
    if args.command == "daily":
        collect.load_env()
        if os.environ.get("NEWSTORE_API_KEY", "").strip() and not os.environ["NEWSTORE_API_KEY"].startswith("여기에"):
            from asan_pr import newstore
            # 최근 7일을 다시 조회해 늦게 등록된 기사까지 보강
            print("뉴스토어:", newstore.collect(conn, date.today() - timedelta(days=7)))
    if args.command == "bigkinds":
        from asan_pr import bigkinds
        if not args.file:
            sys.exit("빅카인즈 엑셀 파일 경로를 입력하세요.")
        print("빅카인즈:", bigkinds.import_excel(conn, Path(args.file)))
    if args.command in ("views", "daily"):
        from asan_pr import views
        print("조회수:", views.update_views(conn, args.limit))
    if args.command in ("cluster", "daily", "bigkinds", "collect", "newstore", "views"):
        print("통합:", cluster.build_clusters(conn))
    if args.command in ("build", "daily", "cluster", "bigkinds", "collect", "newstore", "views"):
        print("내보내기:", export.export(conn, DATA_JS))


if __name__ == "__main__":
    main()
