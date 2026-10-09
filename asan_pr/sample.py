"""화면 확인용 샘플 데이터 생성. 실제 기사가 아니며 대시보드에 '샘플' 표시가 붙는다."""
import random
from datetime import date, timedelta

from . import config, text

ISSUES = [
    ("행정·시정", "아산시, {n}년 하반기 주요업무 보고회 개최"),
    ("행정·시정", "아산시장, 읍면동 현장 소통 간담회 진행"),
    ("행정·시정", "아산시, 민원 처리 기간 단축 제도 시행"),
    ("경제·산업·일자리", "아산시, 탕정 디스플레이 산업단지 기업 투자협약 체결"),
    ("경제·산업·일자리", "아산시 일자리 박람회 개최…구직자 {k}명 참여"),
    ("경제·산업·일자리", "아산시, 소상공인 경영안정자금 지원 확대"),
    ("관광·문화·축제", "제{k}회 성웅 이순신 축제 개막…관람객 발길 이어져"),
    ("관광·문화·축제", "아산 신정호 야간 경관 조성사업 완료"),
    ("관광·문화·축제", "온양온천 관광 활성화 프로그램 운영"),
    ("관광·문화·축제", "아산 외암마을 전통문화 체험 행사 열려"),
    ("복지·보건", "아산시, 어르신 돌봄 서비스 확대 운영"),
    ("복지·보건", "아산시 보건소, 감염병 예방 접종 실시"),
    ("교육·청년", "아산시, 청년 창업 지원 사업 참가자 모집"),
    ("교육·청년", "아산시 장학재단, 지역 인재 장학금 수여"),
    ("도시·교통·개발", "아산시, 배방 도시재생 뉴딜사업 본격 추진"),
    ("도시·교통·개발", "아산 시내버스 노선 개편안 발표"),
    ("환경·안전", "아산시, 집중호우 대비 재난안전대책본부 가동"),
    ("환경·안전", "아산시, 곡교천 수질 개선 사업 착수"),
    ("의회·정치", "아산시의회, 제{k}회 임시회 개회"),
    ("의회·정치", "아산시의회 행정사무감사 돌입"),
    ("체육", "충남아산FC, 홈경기서 승리…시민 응원 열기"),
    ("체육", "아산시장배 생활체육 대회 성료"),
]
PREFIXES = ["", "", "", "[아산] ", "[충남] ", "(아산=뉴스) ", "[포토] "]
SUFFIXES = ["", "", "", " 눈길", " 호응", "…시민 관심 높아"]


def generate(conn, seed: int = 7) -> dict:
    rnd = random.Random(seed)
    outlets = [f"샘플매체 {i:02d}" for i in range(1, 41)]
    shows_views = set(rnd.sample(outlets, 14))        # 조회수를 공개하는 매체
    reach = {o: rnd.uniform(0.3, 3.0) for o in outlets}
    conn.execute("DELETE FROM articles")
    conn.execute("DELETE FROM clusters")

    day, end = config.START_DATE, date(2026, 10, 9)
    seq = 0
    while day <= end:
        weekday = day.weekday()
        n_issues = rnd.randint(6, 12) if weekday < 5 else rnd.randint(1, 4)
        if day.month == 4 and 20 <= day.day <= 30:   # 축제 기간 보도 증가
            n_issues += 6
        for _ in range(n_issues):
            topic, tpl = rnd.choice(ISSUES)
            if day.month == 4 and 20 <= day.day <= 30 and rnd.random() < 0.4:
                topic, tpl = ISSUES[6]
            base = tpl.format(n=day.year, k=rnd.randint(10, 300))
            spread = max(1, int(rnd.paretovariate(1.6)))   # 이슈당 기사 수 (소수의 이슈가 크게 확산)
            for press in rnd.sample(outlets, min(spread, len(outlets))):
                seq += 1
                d = day + timedelta(days=rnd.choice([0, 0, 0, 1]))
                if d > end:
                    d = end
                title = rnd.choice(PREFIXES) + base + rnd.choice(SUFFIXES)
                views = None
                if press in shows_views:
                    views = int(rnd.lognormvariate(5.6, 0.9) * reach[press])
                conn.execute(
                    """INSERT INTO articles (url, title, description, pub_date, press, domain, source,
                                             topic, views, views_status)
                       VALUES (?,?,?,?,?,?, 'sample', ?, ?, ?)""",
                    (f"https://example.com/sample/{seq}", title, "", d.isoformat(), press,
                     "example.com", topic, views,
                     "ok" if views is not None else "none"),
                )
        day += timedelta(days=1)
    conn.commit()
    return {"articles": seq}
