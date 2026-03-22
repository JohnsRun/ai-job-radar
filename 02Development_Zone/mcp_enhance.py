from __future__ import annotations

import random
import re
import time
from collections import Counter
from typing import Any, Dict, List

from mcp_adapter import MCPEnhanceAdapter


AI_SKILL_TERMS = [
    "AIGC",
    "LLM",
    "RAG",
    "机器学习",
    "深度学习",
    "提示词",
    "大模型",
    "知识图谱",
    "NLP",
    "多模态",
    "Python",
    "SQL",
]

TOOL_TERMS = ["LangChain", "PyTorch", "TensorFlow", "Docker", "Kubernetes", "FastAPI", "Redis", "Milvus"]


def _sleep_random(min_s: float = 2.0, max_s: float = 5.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


def _parse_with_stub_llm(job: Dict[str, Any], jd_text: str) -> Dict[str, Any]:
    raw = f"{job.get('job_title', '')} {jd_text}".lower()

    skills = [term for term in AI_SKILL_TERMS if term.lower() in raw]
    tools = [term for term in TOOL_TERMS if term.lower() in raw]

    ai_hit = sum(term.lower() in raw for term in ["ai", "aigc", "llm", "大模型", "人工智能", "智能"])
    if ai_hit >= 4:
        ai_level = "High"
    elif ai_hit >= 2:
        ai_level = "Medium"
    else:
        ai_level = "Low"

    if any(x in raw for x in ["to b", "b端", "企业", "saas"]):
        product_type = "ToB"
    elif any(x in raw for x in ["to c", "c端", "用户增长", "消费者"]):
        product_type = "ToC"
    else:
        product_type = "Platform"

    return {
        "skills": sorted(set(skills)),
        "ai_level": ai_level,
        "product_type": product_type,
        "tools": sorted(set(tools)),
    }


def mcp_enhance(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Enhancement layer (MCP adapter + stub parser).

    Rules:
    - sort by post_date desc
    - only process latest 5 items
    - delay 2-5s per item
    - timeout 10s per fetch
    - any failure should be skipped and must not break main flow
    """
    if not jobs:
        return jobs

    sorted_jobs = sorted(jobs, key=lambda x: x.get("post_date", ""), reverse=True)
    top_jobs = sorted_jobs[:5]
    adapter = MCPEnhanceAdapter()

    enhanced_map: Dict[str, Dict[str, Any]] = {}

    for job in top_jobs:
        key = f"{job.get('job_title','')}|{job.get('company_name','')}|{job.get('job_url','')}"
        _sleep_random(2.0, 5.0)
        try:
            adapter_result = adapter.fetch_jd_text(job.get("job_url", ""), timeout_sec=10)
            jd_text = adapter_result.jd_text
            fields = _parse_with_stub_llm(job, jd_text)
            fields["enhance_source"] = adapter_result.source
        except Exception:
            fields = {
                "skills": [],
                "ai_level": "",
                "product_type": "",
                "tools": [],
                "enhance_source": "failed",
            }
        enhanced_map[key] = fields

    output: List[Dict[str, Any]] = []
    for job in jobs:
        key = f"{job.get('job_title','')}|{job.get('company_name','')}|{job.get('job_url','')}"
        fields = enhanced_map.get(
            key,
            {"skills": [], "ai_level": "", "product_type": "", "tools": [], "enhance_source": "not_sampled"},
        )
        output.append({**job, **fields})

    return output


def summarize_enhancement(enhanced_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    all_skills = []
    all_tools = []
    ai_hits = 0
    ai_total = 0

    for job in enhanced_jobs:
        skills = job.get("skills") or []
        tools = job.get("tools") or []
        level = (job.get("ai_level") or "").strip()

        all_skills.extend(skills)
        all_tools.extend(tools)
        if level:
            ai_total += 1
            if level in {"High", "Medium"}:
                ai_hits += 1

    skill_top5 = Counter(all_skills).most_common(5)
    tool_top3 = Counter(all_tools).most_common(3)
    ai_ratio = round((ai_hits / ai_total) * 100.0, 2) if ai_total else 0.0

    return {
        "top_skills": skill_top5,
        "ai_related_ratio": ai_ratio,
        "top_tools": tool_top3,
    }
