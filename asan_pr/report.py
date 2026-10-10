"""통계 분석 + Gemini 해석 → 대시보드 보고서 데이터."""
import json
from datetime import datetime

from . import config, llm, stats

CACHE = config.DATA_DIR / "report.json"


def build(conn, use_llm: bool = True) -> dict:
    """통계는 매번 새로 계산하고, Gemini 해석은 use_llm 일 때만 새로 받는다(아니면 직전 해석 재사용)."""
    result = stats.analyze(conn)
    result["generated"] = datetime.now().isoformat(timespec="minutes")
    prev = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    if result.get("ok") and use_llm:
        result["ai"] = llm.interpret(result) or prev.get("ai")
        if result["ai"] and result["ai"] is not prev.get("ai"):
            result["ai"]["generated"] = result["generated"]
            result["ai"]["period"] = result["period"]
    else:
        result["ai"] = prev.get("ai")
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result
