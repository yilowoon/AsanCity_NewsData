# 배포용 프롬프트 — 지자체 홍보 사업 성과 분석 시스템

> 이 문서는 [아산시 홍보 사업 성과 분석 시스템](README.md)을 **AI 코딩 도구(Claude Code 등)로 처음부터 다시 만들 수 있도록** 정리한 프롬프트 모음입니다.
> 수강생은 아래 `{{ }}` 변수만 자기 지역·주제로 바꿔서 순서대로 붙여 넣으면 됩니다.

---

## 사용 방법

1. **AI 코딩 도구 준비** — Claude Code(유료 요금제 권장, [README 0장](README.md#0-권장-환경-유료-ai-도구-사용-권고)) 또는 이에 준하는 도구
2. **빈 폴더**에서 도구를 실행
3. **[A. 마스터 프롬프트](#a-마스터-프롬프트-전체-설계)**를 먼저 붙여 넣어 AI가 전체 설계를 이해하게 함
4. **[B. 단계별 프롬프트](#b-단계별-실행-프롬프트)** 1 → 7을 하나씩 붙여 넣고, 각 단계의 **완료 기준**을 확인한 뒤 다음 단계로 진행
5. 막히면 **[C. 점검·수정 프롬프트](#c-점검수정-프롬프트)** 사용

> ⚠️ **API 키는 프롬프트에 절대 붙여 넣지 마세요.** AI가 `.env` 파일 틀을 만들면, 키 값은 본인이 직접 입력합니다.

### 바꿔 넣을 변수

| 변수 | 설명 | 아산시 예시 |
|---|---|---|
| `{{지역명}}` | 분석 대상 지자체 | 아산시 |
| `{{상위지역}}` | 시·도 | 충청남도 |
| `{{시작일}}` | 분석 시작일 | 2026-01-01 |
| `{{검색어}}` | 수집 검색어 8~12개 | 아산시, 아산시장, 아산시의회, 아산시청, 아산 온양온천, 아산 배방, 아산 탕정, 아산 이순신축제, 아산 곡교천, 아산 신정호 |
| `{{지역어}}` | 읍면동·대표 장소·행사명 | 온양, 배방, 탕정, 음봉, 둔포, 곡교천, 신정호, 외암마을, 현충사, 이순신축제 |
| `{{제외어}}` | 지역명이 들어가지만 무관한 고유명사 | 서울아산병원, 현대아산, 아산나눔재단, 아산정책연구원 |
| `{{운영기관}}` | 푸터에 표시할 운영 주체 | 사단법인 도시공동체본부 |
| `{{제작자}}` | Powered By 표기 | YILOWOON |
| `{{브랜드색}}` | 지자체 상징색 3가지 | #1d4f9c(파랑), #e8891a(주황), #2f8a3b(초록) |
| `{{저장소}}` | GitHub 저장소 | 계정명/저장소명 |
| `{{갱신시각}}` | 매일 자동 갱신 시각(KST) | 오전 8시 |

---

## A. 마스터 프롬프트 (전체 설계)

아래 블록 전체를 복사해 AI 도구에 붙여 넣으세요.

````text
너는 공공 데이터 분석 시스템을 만드는 시니어 개발자다. 아래 설계서대로
「{{지역명}} 홍보 사업 성과 분석 시스템」을 만든다. 지금은 설계만 이해하고,
내가 단계별 프롬프트를 줄 때마다 해당 단계만 구현한다. 이해했으면 설계 요약과
구현 순서(7단계)를 10줄 이내로 답하라.

# 1. 목적
- {{지역명}}이 보도자료로 홍보한 효과를 데이터로 증명한다.
- {{지역명}} 관련 온라인 뉴스를 매일 자동 수집하고, 유사 기사를 이슈로 묶고,
  보도량·확산·매체·주제를 일/주/월 단위로 집계·통계 분석하고,
  AI(Gemini)가 그 통계를 공무원 보고서체로 해석해 웹 대시보드로 공개한다.
- 독자: 시의회·시민(공개 페이지), 홍보 담당자(관리자 페이지).

# 2. 아키텍처 (반드시 이 구조)
- 무거운 작업(수집·분석·AI)은 GitHub Actions가 하루 한 번 실행한다.
- 결과는 SQLite DB(data/asan_news.db 대신 data/news.db 등 지역에 맞게)와
  dashboard/data.js(window.ASAN_DATA, window.ASAN_REPORT 전역 변수) 두 파일로 저장소에 커밋한다.
- Render 웹서비스(Node, 의존성 없는 server.js)가 dashboard 폴더를 제공한다.
  저장소에 푸시되면 Render가 자동 재배포한다.
- 관리자는 /admin에서 로그인 후 버튼으로 GitHub API(workflow_dispatch)를 호출해 즉시 갱신한다.

# 3. 기술 스택
- Python 3.10+ (표준 라이브러리 urllib 사용, 외부 라이브러리는 numpy·scipy·openpyxl만)
- SQLite, Chart.js(cdnjs), 순수 HTML/CSS/JS(빌드 도구 없음), Node 18+ 표준 모듈만
- 외부 API: NAVER API HUB 뉴스 검색, 뉴스토어(빅카인즈) 뉴스검색 API(선택), Gemini API

# 4. 폴더 구조
run.py                       # CLI 진입점: daily|collect|newstore|bigkinds|cluster|views|build|report|sample
<패키지>/config.py           # 검색어·제외어·지역어·주제 키워드·임계값 (지역 교체 시 이 파일만 수정)
<패키지>/db.py               # 테이블: articles, clusters, runs
<패키지>/collect.py          # 네이버 API HUB 수집
<패키지>/newstore.py         # 뉴스토어 API 기간 수집
<패키지>/bigkinds.py         # 빅카인즈 엑셀 가져오기
<패키지>/text.py             # 정제·관련성·주제 분류·매체명
<패키지>/cluster.py          # 유사 제목 → 이슈
<패키지>/views.py            # 원문 페이지에서 매체명(og:site_name)·조회수
<패키지>/stats.py            # 통계 분석 (숫자는 여기서만 만든다)
<패키지>/llm.py              # Gemini 해석 (숫자를 만들지 않는다)
<패키지>/report.py           # 통계 + AI 결과 묶기, 실패 시 직전 해석 재사용
<패키지>/export.py           # DB → dashboard/data.js
<패키지>/sample.py           # 키 없이 화면 확인용 샘플 데이터(화면에 '샘플' 배너)
dashboard/index.html         # 공개 대시보드 + 관리자 모드
dashboard/report.html        # 성과 통계 보고서
dashboard/assets/            # 로고, og-image.png(1200x630)
server.js, package.json      # Render 웹서비스 (npm start)
render.yaml                  # Render Blueprint
.github/workflows/daily.yml  # 매일 자동 실행
requirements.txt, .gitignore(.env 반드시 포함), README.md

# 5. 핵심 규칙
- 비밀값(API 키·관리자 비밀번호·토큰)은 절대 코드·README·커밋에 넣지 않는다.
  로컬은 .env, Actions는 GitHub Secrets, Render는 Environment에서 읽는다.
- 통계 수치는 scipy로 결정적으로 계산하고, LLM에는 계산 결과 JSON만 보낸다.
- 데이터 한계(수집 편향, 조회수 공개율, 상관≠인과)를 화면과 보고서에 항상 표시한다.
- 어떤 단계가 실패해도 기존 화면은 유지되어야 한다.
- 모든 사용자 화면 문구는 한국어, 보고서 문장은 공무원 개조식("~함", "~임").

# 6. 지역 설정값
- 지역: {{지역명}} ({{상위지역}}), 분석 시작일: {{시작일}}
- 검색어: {{검색어}}
- 지역어(관련성 판단): {{지역어}}
- 제외어(무관 기사): {{제외어}}
- 주제 9개: 행정·시정 / 경제·산업·일자리 / 관광·문화·축제 / 복지·보건 / 교육·청년 /
  도시·교통·개발 / 환경·안전 / 의회·정치 / 체육 (+기타)
- 운영기관: {{운영기관}}, 제작: Powered By {{제작자}}, 브랜드색: {{브랜드색}}
- 저장소: {{저장소}}, 자동 갱신: 매일 {{갱신시각}}(KST)
````

---

## B. 단계별 실행 프롬프트

각 단계를 끝낼 때마다 **완료 기준**을 직접 확인하세요.

### 1단계 — 프로젝트 골격과 DB

````text
1단계를 구현하라.
- 마스터 설계의 폴더 구조대로 파일을 만든다(아직 빈 함수여도 됨).
- config.py에 지역 설정값을 모두 넣는다.
- db.py: articles(id, url UNIQUE, naver_link, title, description, pub_date YYYY-MM-DD,
  pub_datetime, press, domain, source[naver|newstore|bigkinds|sample], query, topic,
  cluster_id, views, views_checked, views_status, collected_at),
  clusters(id, title, first_date, last_date, article_cnt, press_cnt, views_sum, topic),
  runs(id, step, started, detail) 테이블과 인덱스.
- .gitignore에 .env, __pycache__, data/sample.db, data/*.log, data/report.json, .claude/ 포함.
- .env.example에 키 이름만 적는다(값은 비움):
  NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NEWSTORE_API_KEY, GEMINI_API_KEY,
  GEMINI_BASE_URL=https://generativelanguage.googleapis.com, GEMINI_TEXT_MODEL, ADMIN_ID, ADMIN_PASSWORD
- run.py에 명령어 골격과 사용법 docstring을 작성한다.
완료 후 생성한 파일 목록과 각 역할을 표로 보여줘라.
````
**완료 기준:** `python run.py --help`가 동작, `.env`가 `.gitignore`에 포함

### 2단계 — 뉴스 수집과 정제

````text
2단계를 구현하라.
[text.py]
- clean(): <b> 태그와 HTML 엔티티 제거
- strip_prefix(): 제목 앞 말머리([포토], (지역=뉴스) 등) 제거
- is_relevant(title, desc): 제외어를 지운 뒤에도 지역명이 남고, 제목에 지역명이 있거나
  본문에 지역어가 있으면 관련 기사로 판단
- classify_topic(): 주제별 키워드 출현 수(제목 가중치 2배)로 분류, 없으면 '기타'
- domain_of(), press_from_domain(): 주요 언론사 도메인→매체명 사전
[collect.py] NAVER API HUB 뉴스 검색
- GET https://naverapihub.apigw.ntruss.com/search/v1/news
  헤더 X-NCP-APIGW-API-KEY-ID / X-NCP-APIGW-API-KEY, 파라미터 query, display=100, start, sort=date
- 검색어마다 start=1,101,...,901(최대 1,000건), 시작일 이전 기사가 나오면 중단
- 429는 지수 대기 후 재시도, 그 외 오류는 응답 본문과 함께 종료
- 관련 없는 기사는 버리고 URL 기준 중복 없이 저장(INSERT OR IGNORE), runs에 통계 기록
[sample.py] 키 없이 화면을 볼 수 있는 샘플 데이터(매체명은 '샘플매체 01' 형식, 실제 언론사명 금지)
키가 없으면 ".env 파일에 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 을 입력하세요." 메시지로 종료하라.
````
**완료 기준:** `python run.py collect` 실행 시 검색어별 신규 건수가 출력되고 DB에 저장됨. 무관 기사(제외어)가 걸러짐

### 3단계 — 이슈 통합과 원문 확인

````text
3단계를 구현하라.
[cluster.py] 같은 보도자료로 쓴 기사들을 하나의 이슈로 묶는다.
- 제목 정규화(말머리·괄호·특수문자 제거) → 문자 2-gram 집합 → 자카드 유사도 ≥ 0.45면 같은 이슈
- 3일 이내 기사끼리만 비교, (날짜, 단어) 역색인으로 후보를 줄여 수만 건도 수 초 안에 처리
- union-find로 묶되 한 이슈의 기간은 최대 7일(연쇄 병합 방지)
- 대표 제목 = 다른 제목과 평균 유사도가 가장 높은 제목(medoid), 말머리 제거
- 이슈 id = 구성 기사 중 최소 article id(재실행해도 안정적)
[views.py] 원문 페이지 확인
- robots.txt 허용 시에만 접속, 6개 스레드, 타임아웃 12초, charset 자동 판별
- og:site_name으로 매체명 보정(도메인으로 표시되던 것을 실제 매체명으로)
- '조회수' 패턴을 읽되 날짜 오인 방지, 검증된 도메인 목록(VIEWS_TRUSTED_DOMAINS)만 조회수로 인정
- 최근 14일 기사는 매일 재확인
````
**완료 기준:** `python run.py cluster` 결과 이슈 수가 기사 수보다 적고, 대표 제목에 말머리가 없음

### 4단계 — 대시보드 화면

````text
4단계를 구현하라. export.py와 dashboard/index.html을 만든다.
[export.py] DB → dashboard/data.js
- window.ASAN_DATA = {meta, press[], topics[], clusters{id:title}, articles[[id,date,cluster,pressIdx,title,url,views,topicIdx]]}
  (매체·주제는 인덱스로 압축)
[index.html] 단일 파일, Chart.js, 브랜드색 {{브랜드색}}, 라이트/다크 모드(CSS 변수, prefers-color-scheme + 토글)
- 상단: 로고, 제목, 데이터 기간·갱신 시각, "본 시스템은 매일 {{갱신시각}}(한국시간) 자동 갱신됩니다."
- 맨 위 얇은 띠: "Powered By {{제작자}}", 맨 아래 푸터: "{{운영기관}}"
- 고정 필터 바: 기간 프리셋(7일/30일/이번 달/3개월/전체)+날짜 직접 입력, 집계 단위(일/주/월), 주제
- KPI 6개(보도 건수, 통합 이슈, 보도 매체, 확인 조회수+공개율, 이슈당 평균 보도, 대형 확산 이슈=5개 매체↑)
  각각 직전 동기간 대비 증감
- 차트: 보도 추이, 조회수 추이, 주제별 분포, 매체별 보도 TOP15, 매체별 조회수 TOP15 (이중 축 금지)
- 홍보 성과 요약: 자동 요약 문장 + 노출·확산·도달·지속·매체 다양성·이슈 집중도 6개 지표
- 기간별 성과표, 주요 이슈 표(행 클릭 시 기사 펼침, 정렬·검색·CSV), 기사 목록(검색·페이지·CSV)
- 지표 정의 및 데이터 한계 안내
- 레이아웃 주의: 2열 그리드는 minmax(0,1fr)로(차트 넘침 방지), [hidden]{display:none!important}
샘플 데이터로 열어서 콘솔 오류가 없는지 확인하라.
````
**완료 기준:** `python run.py sample` 후 `python -m http.server 8765 --directory dashboard` → 모든 섹션 표시, 창 크기를 줄여도 차트가 카드 밖으로 넘치지 않음

### 5단계 — 통계 분석과 AI 해석

````text
5단계를 구현하라.
[stats.py] scipy로 결정적으로 계산(진행 중인 마지막 주는 제외, p값은 유효숫자 3자리 보존)
- 기술통계(주간·일간: n, 평균, 표준편차, 중앙값, 최소, 최대, 변동계수)
- 추세: 주차↔주간 보도량 선형회귀(기울기, R², p) + Spearman
- 상관: 주간 [이슈 수, 매체 수, 대형 확산 이슈 수, 이슈당 보도 건수, 조회수(5주 이상일 때)] ↔ 보도 건수
  Pearson r, 95% CI(Fisher z), Spearman ρ, Holm 보정 p, 강도 라벨.
  '이슈 수'에는 "보도 건수 = 이슈 수 × 이슈당 보도"라 구조적 상관이 있다는 note를 붙인다.
- 상관행렬(주간 지표 5개)
- 요일 효과: 평일 vs 주말 Mann-Whitney U(효과크기 r=Z/√N), 7요일 Kruskal-Wallis
- 주제별 확산력: 이슈당 매체 수를 주제별 Kruskal-Wallis(ε²), 이슈 20개 이상 주제만
- 주제 구성 변화: 주제×월 카이제곱(Cramér's V)
- 홍보비 연계: data/budget.csv(month,amount)가 있으면 월별 상관과 보도 1건당 홍보비, 없으면 available=false
- limitations: 수집 편향, 자기상관, 상관≠인과, 조회수 표본 부족을 조건에 따라 자동 기재
[llm.py] Gemini
- POST {GEMINI_BASE_URL}/v1beta/models/{GEMINI_TEXT_MODEL}:generateContent, 헤더 x-goog-api-key
- generationConfig: temperature 0.2, responseMimeType application/json
- 차트용 원자료(points, series)는 빼고 보낸다
- 프롬프트 규칙: JSON 수치만 사용·새 수치 금지, Holm p 기준 판단, 인과 단정 금지,
  수집 편향은 추세 문장에 명시, 작은 표본은 결론 유보, 공무원 개조식
- 출력: {headline, key_findings[], sections{trend,correlation,weekday,topic_spread,topic_month,budget}, recommendations[], caveats[]}
- 키 없음·실패 시 None
[report.py] 통계는 매번 계산, AI는 daily/report 명령에서만 호출, 실패하거나 키가 없으면
  data/report.json 또는 기존 data.js의 ASAN_REPORT에서 직전 해석 재사용
[export.py] data.js에 window.ASAN_REPORT 추가
[report.html] 분석 요약 → 기술통계 → 추세(막대+회귀선) → 상관(표, 산점도+회귀선 선택, 발산형 히트맵)
  → 요일 → 주제별 확산력 → 주제 구성(월×주제 비중 히트맵) → 홍보비 → 제언·데이터 한계·분석 방법.
  각 장에 'AI 해석' 박스. 유의성 배지(*, **, ***). y축은 0부터.
[index.html] 홍보 성과 요약 아래 '통계 분석 요약'(AI 헤드라인, 핵심 수치 4칸, 발견 3개)과
  [성과 보고내용 보기 →] 버튼(report.html)
````
**완료 기준:** `python run.py report` → "AI 해석 포함" 출력, report.html의 모든 장이 표시되고 p값이 0이 아니라 `<0.001`로 표시

### 6단계 — 웹서버와 관리자 모드

````text
6단계를 구현하라. server.js(의존성 없음)와 package.json("start": "node server.js").
- dashboard 정적 제공. 경로 검사는 file.startsWith(ROOT + path.sep), decodeURIComponent는 try/catch(실패 시 400)
- html/js는 no-cache. HTML의 %%ORIGIN%%를 접속 도메인(x-forwarded-proto + host, 또는 PUBLIC_URL)으로 치환
- /admin → index.html, /admin/ → /admin 리다이렉트. 공개 페이지에는 관리자 링크 없음
- 관리자 인증: ADMIN_ID/ADMIN_PASSWORD 환경변수(없으면 503 안내), timingSafeEqual 비교,
  HMAC 서명 쿠키(HttpOnly, SameSite=Strict, https면 Secure, 8시간)
- 무차별 대입 방지: IP별 5회 실패 시 15분 잠금(IP는 cf-connecting-ip 우선, X-Forwarded-For는 마지막 값),
  IP 무관 전체 한도 1시간 20회 실패 시 1시간 잠금
- POST /api/refresh(관리자만): 실행 중이면 거절, 10분 쿨다운, GitHub API로 daily.yml workflow_dispatch(ref main)
- GET /api/refresh-status(관리자만): 최근 실행 상태 + 현재 배포된 data.js의 generated 값
- GITHUB_TOKEN/GITHUB_REPO 환경변수, 토큰이 없으면 버튼 비활성 안내
- uncaughtException/unhandledRejection은 로그만 남기고 서버 유지
[index.html] /admin일 때만: 로그인 창 → '관리자 모드' 배지, [최신 데이터로 갱신], [로그아웃].
  갱신 시 '수집 중 → 배포 중' 진행 표시, data.js 버전이 바뀌면 자동 새로고침
[OG] dashboard/assets/og-image.png(1200x630, 지역명·시스템명·브랜드색·제작자·운영기관, 매일 바뀌는 수치는 넣지 않음),
  og:title/description/url/image(+width,height,alt), twitter:card=summary_large_image, favicon
보안 시험(경로 우회, 잘못된 %인코딩, 무단 API 호출, 쿠키 위조, 잠금 우회)을 curl로 수행하고 결과를 표로 보여줘라.
````
**완료 기준:** `npm start` 후 `/admin` 로그인 동작, 보안 시험이 모두 차단(400/403/404/401)

### 7단계 — 자동화와 배포

````text
7단계를 구현하라.
[.github/workflows/daily.yml]
- schedule: 정각을 피해 KST 기준 {{갱신시각}} 직전·직후 3회 (예: UTC "7 22 * * *", "37 22 * * *", "7 23 * * *")
  + workflow_dispatch. cron은 UTC로 적는다(KST = UTC+9).
- permissions: contents: write, concurrency 그룹 지정
- 예약 실행일 때 오늘 07시(KST) 이후 github-actions 커밋이 있으면 나머지 단계 건너뜀
- Python 3.12 → pip install -r requirements.txt → python run.py daily
  env: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET, NEWSTORE_API_KEY, GEMINI_API_KEY(모두 secrets), GEMINI_TEXT_MODEL, TZ=Asia/Seoul
- data/*.db와 dashboard/data.js만 커밋, 메시지 "데이터 갱신 YYYY-MM-DD HH:MM KST",
  push 전 git pull --rebase, 최대 3회 재시도, 변경 없으면 커밋 생략
[render.yaml] type web, runtime node, buildCommand npm install, startCommand npm start,
  envVars ADMIN_ID/ADMIN_PASSWORD/GITHUB_TOKEN(sync:false), GITHUB_REPO
[README.md] 수강생용: 목적, 아키텍처(mermaid), 폴더 구조, API 키 발급(NAVER API HUB 이관 안내 포함),
  로컬 실행, 기능 상세, API 연동 코드, Secrets/Render 설정, 지역 바꾸기, FAQ, 데이터 한계
마지막으로 내가 직접 해야 할 일(Secrets 등록, Render 환경변수, 토큰 발급)을 체크리스트로 정리하라.
````
**완료 기준:** Actions에서 수동 실행 성공 → "데이터 갱신" 커밋 생성 → Render 재배포 → 사이트 갱신 시각 변경

> ℹ️ AI 도구의 Git 인증에 `workflow` 권한이 없으면 `.github/workflows/` 파일 푸시가 거부됩니다. 그때는 GitHub 웹에서 파일을 직접 만들어 붙여 넣으세요.

---

## C. 점검·수정 프롬프트

### 보안 점검
````text
이 저장소의 보안을 점검하라.
1) 현재 파일과 git 이력 전체에서 API 키·토큰·비밀번호 노출 여부(.env 값과 대조, github_pat_/AIza 등 패턴)
2) server.js 경로 우회·잘못된 인코딩·무단 API·쿠키 위조·로그인 잠금 우회를 로컬과 배포 주소({{배포주소}})에서 시험
3) 저장소 공개 범위와 협업자
발견된 문제는 수정하고, 결과를 '항목 | 결과 | 판정' 표로 보고하라. 확인하지 못한 항목은 그렇다고 명시하라.
````

### 지역 교체
````text
이 시스템을 {{새 지역명}}용으로 바꿔라. config.py의 검색어·지역어·제외어·시작일, 화면 제목과 문구,
로고(assets), OG 이미지, README의 지역명을 모두 교체하고, 동명이인 지명(예: '중구')으로 인한
오수집 가능성을 검토해 제외어를 제안하라. 샘플 데이터로 화면을 확인한 뒤 변경 파일 목록을 보여줘라.
````

### 오류 해결
````text
아래 오류가 났다. 원인을 로그·코드에서 확인하고, 추측이 아니라 근거를 들어 설명한 뒤 고쳐라.
수정 후 같은 상황을 재현해 해결됐는지 확인하라.
[오류 내용 또는 스크린샷 설명 붙여넣기]
````

### 홍보비 연계 분석 켜기
````text
data/budget.csv(month,amount)를 추가했다. 홍보비와 월별 보도량 상관, 보도 1건당 홍보비가
보고서와 대시보드에 반영되도록 하고, 표본(개월 수)이 적을 때 결론을 유보하는 문구가 들어가는지 확인하라.
````

---

## D. 프롬프트 작성 원칙 (이 문서가 이렇게 구성된 이유)

| 원칙 | 적용 |
|---|---|
| **한 번에 하나씩** | 7단계로 나누고 단계마다 완료 기준 제시 → AI가 빠뜨리거나 임의로 바꾸는 것 방지 |
| **구체적 수치와 이름** | 임계값(0.45, 3일, 7일), 엔드포인트, 헤더명, 파일명을 명시 → 재현 가능 |
| **"하지 말 것" 명시** | 비밀값 커밋 금지, LLM 수치 생성 금지, 이중 축 금지 → 흔한 실수 차단 |
| **검증을 시킨다** | 각 단계 끝에 실행·확인·표 보고 요구 → "만들었다"가 아니라 "동작한다"를 확인 |
| **변수화** | `{{ }}`만 바꾸면 다른 지역·주제로 재사용 |
| **사람이 할 일 분리** | 키 입력·Secrets·Render 설정은 사람이 직접 → 보안 사고 예방 |

<p align="center"><sub>Powered By <b>YILOWOON</b> · © 2026 사단법인 도시공동체본부</sub></p>
