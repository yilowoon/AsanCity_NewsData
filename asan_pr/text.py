"""제목 정규화, 관련성 판단, 주제 분류, 매체명 추정."""
import html
import re
from urllib.parse import urlparse

from . import config

_TAG = re.compile(r"<[^>]+>")
_BRACKET = re.compile(r"[\[\(【〔<《][^\]\)】〕>》]{0,20}[\]\)】〕>》]")
_NON_WORD = re.compile(r"[^0-9A-Za-z가-힣]+")

# 주요 도메인 → 매체명 (원문 페이지의 og:site_name 으로 다시 보정된다)
KNOWN_PRESS = {
    "yna.co.kr": "연합뉴스", "newsis.com": "뉴시스", "news1.kr": "뉴스1",
    "chosun.com": "조선일보", "joongang.co.kr": "중앙일보", "donga.com": "동아일보",
    "hani.co.kr": "한겨레", "khan.co.kr": "경향신문", "hankookilbo.com": "한국일보",
    "kmib.co.kr": "국민일보", "seoul.co.kr": "서울신문", "segye.com": "세계일보",
    "munhwa.com": "문화일보", "mk.co.kr": "매일경제", "hankyung.com": "한국경제",
    "sedaily.com": "서울경제", "edaily.co.kr": "이데일리", "mt.co.kr": "머니투데이",
    "asiae.co.kr": "아시아경제", "fnnews.com": "파이낸셜뉴스", "heraldcorp.com": "헤럴드경제",
    "nocutnews.co.kr": "노컷뉴스", "ohmynews.com": "오마이뉴스", "kbs.co.kr": "KBS",
    "imbc.com": "MBC", "sbs.co.kr": "SBS", "ytn.co.kr": "YTN", "jtbc.co.kr": "JTBC",
    "tjb.co.kr": "TJB대전방송", "cctoday.co.kr": "충청투데이", "ggilbo.com": "금강일보",
    "daejonilbo.com": "대전일보", "joongdo.co.kr": "중도일보", "dynews.co.kr": "동양일보",
    "ccdailynews.com": "충청일보", "inews365.com": "충북일보", "cnbnews.com": "CNB뉴스",
    "newspim.com": "뉴스핌", "dailian.co.kr": "데일리안", "nspna.com": "NSP통신",
}


def clean(text: str | None) -> str:
    """API 응답의 <b> 태그와 HTML 엔티티를 제거한다."""
    if not text:
        return ""
    return html.unescape(_TAG.sub("", text)).strip()


_LEAD = re.compile(r"^\s*(?:[\[\(【〔<《][^\]\)】〕>》]{0,20}[\]\)】〕>》]\s*)+")


def strip_prefix(title: str) -> str:
    """'[포토]', '(아산=뉴스)' 같은 앞머리 말머리를 떼어 통합 제목으로 쓴다."""
    return _LEAD.sub("", title).strip() or title


def normalize_title(title: str) -> str:
    """유사도 비교용: 말머리·괄호·특수문자 제거."""
    t = _BRACKET.sub(" ", title)
    t = _NON_WORD.sub(" ", t)
    return " ".join(t.split())


def bigrams(title: str) -> frozenset[str]:
    s = normalize_title(title).replace(" ", "")
    return frozenset(s[i:i + 2] for i in range(len(s) - 1))


def words(title: str) -> set[str]:
    stop = {"아산시", "아산", "충남", "충청남도", "개최", "추진", "실시", "진행", "위해", "관련"}
    return {w for w in normalize_title(title).split() if len(w) >= 2 and w not in stop}


def is_relevant(title: str, description: str) -> bool:
    """'아산'이 아산시를 뜻하는 기사인지 판단한다."""
    def strip(s: str) -> str:
        for term in config.UNRELATED_TERMS:
            s = s.replace(term, "")
        return s

    body = strip(f"{title} {description}")
    if "아산" not in body:
        return False
    return "아산" in strip(title) or any(term in body for term in config.LOCAL_TERMS)


def classify_topic(title: str, description: str) -> str:
    text = f"{title} {title} {description}"  # 제목 가중치 2배
    best, best_score = config.DEFAULT_TOPIC, 0
    for topic, keys in config.TOPICS.items():
        score = sum(text.count(k) for k in keys)
        if score > best_score:
            best, best_score = topic, score
    return best


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def press_from_domain(domain: str) -> str:
    for key, name in KNOWN_PRESS.items():
        if domain == key or domain.endswith("." + key):
            return name
    return domain
