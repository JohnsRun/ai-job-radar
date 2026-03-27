from __future__ import annotations

import re
from collections import Counter
from statistics import median
from typing import Any, Dict, List, Optional, Tuple


TITLE_RELEVANCE_TERMS = [
    "AI PM",
    "AI 产品经理",
    "AI builder",
    "AI Owner",
    "人工智能产品经理",
    "LLM产品经理",
    "AI Header",
    "AI Lead",
]


def _is_guangzhou_city(city: str) -> bool:
    return "广州" in (city or "")


def _matches_title_relevance(job_title: str) -> bool:
    title = (job_title or "").strip().lower()
    if not title:
        return False

    title_norm = " ".join(title.split())
    title_compact = "".join(title.split())
    for term in TITLE_RELEVANCE_TERMS:
        term_norm = " ".join(term.lower().split())
        term_compact = "".join(term.lower().split())
        if term_norm in title_norm or term_compact in title_compact:
            return True
    return False


def parse_salary_k_per_month(salary_raw: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    text = (salary_raw or "").strip().lower()
    if not text or "面议" in text or "薪资" in text and "面" in text:
        return None, None, None

    if "元/天" in text or "元/日" in text:
        return None, None, None

    # Normalize common separators.
    text = text.replace("－", "-").replace("~", "-").replace("至", "-")

    range_match = re.search(
        r"(\d+(?:\.\d+)?)(万|千|k)?\s*-\s*(\d+(?:\.\d+)?)(万|千|k)?",
        text,
        re.IGNORECASE,
    )

    def _to_k(value: float, unit: str, annual: bool) -> float:
        if unit == "万":
            k = value * 10.0
        elif unit in {"千", "k"}:
            k = value
        elif value >= 1000:
            k = value / 1000.0
        else:
            k = value
        if annual:
            k /= 12.0
        return k

    is_year = "年" in text

    if range_match:
        min_v_raw = float(range_match.group(1))
        min_unit = (range_match.group(2) or "").lower()
        max_v_raw = float(range_match.group(3))
        max_unit = (range_match.group(4) or "").lower()

        # If only one side carries unit (e.g. 1.2-1.8万), apply it to both sides.
        if not min_unit and max_unit:
            min_unit = max_unit
        if not max_unit and min_unit:
            max_unit = min_unit

        min_v = _to_k(min_v_raw, min_unit, is_year)
        max_v = _to_k(max_v_raw, max_unit, is_year)
        if min_v > max_v:
            min_v, max_v = max_v, min_v
        avg_v = (min_v + max_v) / 2.0
        return round(min_v, 2), round(max_v, 2), round(avg_v, 2)

    single_match = re.search(r"(\d+(?:\.\d+)?)(万|千|k)?", text, re.IGNORECASE)
    if not single_match:
        return None, None, None

    val_raw = float(single_match.group(1))
    unit = (single_match.group(2) or "").lower()
    min_v = _to_k(val_raw, unit, is_year)
    max_v = min_v

    avg_v = (min_v + max_v) / 2.0
    return round(min_v, 2), round(max_v, 2), round(avg_v, 2)


def process(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned: List[Dict[str, Any]] = []
    seen = set()

    for job in jobs:
        item = {
            "job_title": str(job.get("job_title", "")).strip(),
            "company_name": str(job.get("company_name", "")).strip(),
            "city": str(job.get("city", "")).strip(),
            "salary_raw": str(job.get("salary_raw", "")).strip(),
            "post_date": str(job.get("post_date", "")).strip(),
            "job_url": str(job.get("job_url", "")).strip(),
        }

        # Enforce fixed report scope: Guangzhou only.
        if not _is_guangzhou_city(item["city"]):
            continue

        title_lower = item["job_title"].lower()
        if "实习" in item["job_title"] or "intern" in title_lower:
            continue

        # Keep only records whose title matches one of the configured relevance phrases.
        if not _matches_title_relevance(item["job_title"]):
            continue

        key = (item["job_title"].lower(), item["company_name"].lower(), item["job_url"].lower())
        if key in seen:
            continue
        seen.add(key)

        salary_min, salary_max, salary_avg = parse_salary_k_per_month(item["salary_raw"])
        item["salary_min"] = salary_min
        item["salary_max"] = salary_max
        item["salary_avg"] = salary_avg
        cleaned.append(item)

    return cleaned


def summarize_base_metrics(cleaned_jobs: List[Dict[str, Any]]) -> Dict[str, Any]:
    salary_values = [j["salary_avg"] for j in cleaned_jobs if isinstance(j.get("salary_avg"), (int, float))]

    distribution = {"0-20K": 0, "20K-40K": 0, "40K-60K": 0, "60K+": 0}
    for val in salary_values:
        if val < 20:
            distribution["0-20K"] += 1
        elif val < 40:
            distribution["20K-40K"] += 1
        elif val < 60:
            distribution["40K-60K"] += 1
        else:
            distribution["60K+"] += 1

    city_counter = Counter([j.get("city", "") for j in cleaned_jobs if j.get("city")])

    return {
        "total_jobs": len(cleaned_jobs),
        "median_salary": round(median(salary_values), 2) if salary_values else None,
        "salary_distribution": distribution,
        "salary_sample_jobs": len(salary_values),
        "salary_distribution_total": sum(distribution.values()),
        "top_cities": city_counter.most_common(3),
    }
