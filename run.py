"""아산시 홍보 사업 성과 분석 시스템 — 실행 진입점.

  python run.py daily                 # 수집 → 통합 → 조회수 → 대시보드 (매일 실행)
  python run.py collect               # 네이버 API HUB 뉴스 수집만
  python run.py bigkinds 파일.xlsx    # 빅카인즈 엑셀 가져오기 (과거분 보강)
  python run.py cluster               # 유사 제목 통합
  python run.py views [--limit N]     # 원문 페이지 조회수 확인
  python run.py build                 # 대시보드 데이터 생성
  python run.py sample                # 샘플 데이터로 대시보드 미리보기
"""
import argparse
import sys
from pathlib import Path

from asan_pr import cluster, config, db, export

sys.stdout.reconfigure(encoding="utf-8")
DATA_JS = config.DASHBOARD_DIR / "data.js"


def main() -> None:
    p = argparse.ArgumentParser(description="아산시 홍보 성과 분석")
    p.add_argument("command", choices=["daily", "collect", "bigkinds", "cluster", "views", "build", "sample"])
    p.add_argument("file", nargs="?", help="빅카인즈 엑셀 경로")
    p.add_argument("--limit", type=int, help="조회수 확인 최대 건수")
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
    if args.command == "bigkinds":
        from asan_pr import bigkinds
        if not args.file:
            sys.exit("빅카인즈 엑셀 파일 경로를 입력하세요.")
        print("빅카인즈:", bigkinds.import_excel(conn, Path(args.file)))
    if args.command in ("views", "daily"):
        from asan_pr import views
        print("조회수:", views.update_views(conn, args.limit))
    if args.command in ("cluster", "daily", "bigkinds", "collect", "views"):
        print("통합:", cluster.build_clusters(conn))
    if args.command in ("build", "daily", "cluster", "bigkinds", "collect", "views"):
        print("내보내기:", export.export(conn, DATA_JS))


if __name__ == "__main__":
    main()
