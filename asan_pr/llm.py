"""Gemini 로 통계 분석 결과를 해석해 성과 보고서 문안을 만든다.

LLM 에는 stats.analyze() 가 계산한 수치만 전달하며, 새로운 수치를 만들지 않도록 지시한다.
키가 없거나 호출에 실패하면 None 을 돌려주고 보고서는 통계표만으로 표시된다.
"""
import json
import os
import urllib.error
import urllib.request

from .collect import load_env

DEFAULT_MODEL = "gemini-2.5-flash"

PROMPT = """당신은 지방자치단체 홍보 성과를 분석하는 통계 전문가입니다.
아래 JSON은 아산시 관련 언론 보도 데이터를 Python(scipy)으로 분석한 결과입니다.

[작성 원칙]
1. JSON에 있는 수치만 사용하고, 새로운 수치를 계산하거나 추정하지 마십시오.
2. 상관계수(r, ρ), p값(Holm 보정 p값 우선), 95% 신뢰구간, 효과크기를 근거로 유의성을 판단하십시오. 유의수준은 0.05입니다.
3. 상관관계를 인과관계로 단정하지 마십시오. "limitations"의 한계는 해석에 반드시 반영하고,
   특히 수집 편향(과거 기간 과소 집계)이 있으면 추세 해석 문장 안에 "수집 편향 가능성"을 함께 명시하십시오.
   표본이 작은 항목(n<10, small_sample=true)은 결론을 유보하십시오.
4. "note"가 있는 항목은 그 설명(구조적 상관 등)을 고려해 해석하십시오.
5. 문체는 공무원 보고서체(개조식, 명사형 종결: "~함", "~임", "~필요")로 간결하게 작성하십시오.
6. 예산(budget)이 available=false이면 비용 대비 효과를 판단하지 말고 자료 연계 필요성만 언급하십시오.

[출력 형식] 다음 키를 가진 JSON 하나만 출력하십시오.
{
  "headline": "핵심 결론 한 문장",
  "key_findings": ["핵심 발견 3~5개, 각 문장에 근거 수치(r, p 등) 포함"],
  "sections": {
    "trend": "추세 분석 해석 2~3문장",
    "correlation": "상관분석 종합 해석 3~4문장",
    "weekday": "요일 효과 해석 1~2문장",
    "topic_spread": "주제별 확산력 차이 해석 2문장",
    "topic_month": "주제 구성 변화 해석 1~2문장",
    "budget": "홍보비 연계 분석 해석 1~2문장"
  },
  "recommendations": ["홍보 개선 제언 3~4개"],
  "caveats": ["해석 시 유의사항 2~3개"]
}

[분석 결과 JSON]
"""


def _slim(stats: dict) -> dict:
    """차트용 원자료(points, series, share)는 빼고 수치 요약만 전달."""
    s = json.loads(json.dumps(stats))
    for c in s.get("correlation", []):
        c.pop("points", None)
    s.get("trend", {}).pop("series", None)
    s.get("topic_month", {}).pop("share", None)
    s.get("budget", {}).pop("points", None)
    return s


def interpret(stats: dict) -> dict | None:
    load_env()
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key or key.startswith("여기에"):
        print("  Gemini 키 없음 — 해석 생략")
        return None
    base = os.environ.get("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com").rstrip("/")
    model = os.environ.get("GEMINI_TEXT_MODEL") or DEFAULT_MODEL
    body = {
        "contents": [{"role": "user", "parts": [{"text": PROMPT + json.dumps(_slim(stats), ensure_ascii=False)}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    req = urllib.request.Request(
        f"{base}/v1beta/models/{model}:generateContent",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.load(resp)
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        result = json.loads(text)
        result["model"] = model
        return result
    except urllib.error.HTTPError as e:
        print(f"  Gemini 오류 HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    except Exception as e:
        print(f"  Gemini 해석 실패: {e}")
    return None
