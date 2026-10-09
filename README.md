# 아산시 홍보 사업 성과 분석 시스템

아산시 관련 온라인 뉴스를 매일 수집해 유사 기사를 이슈 단위로 통합하고, 보도 건수·매체 수·공개 조회수를 일간/주간/월간으로 분석하는 대시보드.

## 구성

| 경로 | 역할 |
|---|---|
| `run.py` | 실행 진입점 |
| `asan_pr/collect.py` | 네이버 API HUB 뉴스 검색 수집 |
| `asan_pr/newstore.py` | 뉴스토어(빅카인즈) 뉴스검색 API 기간 수집 |
| `asan_pr/bigkinds.py` | 빅카인즈 엑셀 가져오기 (과거분 보강) |
| `asan_pr/cluster.py` | 유사 제목 통합 → 이슈 |
| `asan_pr/views.py` | 원문 페이지의 공개 조회수 수집 |
| `asan_pr/export.py` | 대시보드 데이터(`dashboard/data.js`) 생성 |
| `asan_pr/config.py` | 검색어·주제 분류·통합 기준 설정 |
| `dashboard/index.html` | 대시보드 |
| `data/asan_news.db` | 수집 DB (SQLite) |

## 사용법

1. `.env` 에 NAVER API HUB 의 Client ID / Secret, 뉴스토어 `NEWSTORE_API_KEY` 입력
2. 실행
   ```
   python run.py daily                  # 수집 → 조회수 → 통합 → 대시보드
   python run.py newstore --from 2026-01-01   # 뉴스토어 API로 1월~현재 전체 수집
   python run.py bigkinds 파일.xlsx     # (API 없이) 빅카인즈 엑셀로 보강
   python run.py sample                 # 샘플 데이터로 화면 미리보기
   ```
3. 대시보드 보기: `python -m http.server 8765 --directory dashboard` 후 http://localhost:8765
   (또는 `dashboard/index.html` 을 브라우저로 직접 열기)
4. 매일 자동 실행: GitHub Actions(`.github/workflows/daily.yml`)가 매일 08:00(KST)에 수집 후
   `data/asan_news.db`, `dashboard/data.js` 를 커밋 → Render 가 자동 재배포
   - GitHub 저장소 Settings → Secrets and variables → Actions 에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `NEWSTORE_API_KEY` 등록 필요
   - 로컬 PC에서 돌리려면 Windows 작업 스케줄러에 `daily.bat` 등록

## Render 배포

- 유형: **Static Site**, Publish directory: `dashboard`, Build command: `echo ok`
- 또는 저장소의 `render.yaml` 을 Blueprint 로 사용

## 데이터 한계

- 네이버 검색은 검색어별 최신 1,000건까지만 조회 → 매일 누적 수집 필요, 과거분은 빅카인즈로 보강
- 조회수는 원문 페이지에 조회수를 공개하는 매체만 수집 가능 (포털·중앙지는 비공개)
