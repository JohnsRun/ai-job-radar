from __future__ import annotations

import json
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import quote

import requests
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

DEFAULT_FALLBACK_SNAPSHOT = (
    Path(__file__).resolve().parents[1] / "00Ad_Hoc" / "51job_search_latest_323.json"
)


@dataclass
class CollectorResult:
    jobs: List[Dict[str, Any]]
    source: str
    note: str = ""


def _sleep_random(min_s: float = 1.0, max_s: float = 3.0) -> None:
    time.sleep(random.uniform(min_s, max_s))


def _extract_total_count(payload: Dict[str, Any]) -> int:
    resultbody = payload.get("resultbody") or {}
    result_job = resultbody.get("job") or {}
    for key in ("totalCount", "total", "count"):
        value = result_job.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def _is_challenge_page(html: str) -> bool:
    marker = (html or "")[:1000]
    return "var arg1=" in marker and "setCookie(" in marker


def _parse_51job_api_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    engine_search_result = payload.get("engine_search_result") or {}
    resultbody = payload.get("resultbody") or {}
    result_job = resultbody.get("job") or {}
    items = (
        engine_search_result.get("joblist")
        or engine_search_result.get("search_data")
        or result_job.get("items")
        or []
    )
    parsed: List[Dict[str, Any]] = []

    for item in items:
        title = item.get("job_name") or item.get("job_title") or item.get("jobName") or ""
        company = item.get("company_name") or ""
        city = item.get("workarea_text") or item.get("workarea") or item.get("jobAreaString") or ""
        salary = item.get("providesalary_text") or item.get("salary") or item.get("provideSalaryString") or ""
        post_date = item.get("issuedate") or item.get("update_time") or item.get("issueDateString") or ""
        job_href = item.get("job_href") or item.get("job_link") or item.get("jobHref") or ""

        if not company:
            company = item.get("companyName") or ""

        if not title and not job_href:
            continue

        parsed.append(
            {
                "job_title": str(title).strip(),
                "company_name": str(company).strip(),
                "city": str(city).strip(),
                "salary_raw": str(salary).strip(),
                "post_date": str(post_date).strip(),
                "job_url": str(job_href).strip(),
            }
        )
    return parsed


def _load_jobs_from_snapshot(snapshot_path: Path) -> List[Dict[str, Any]]:
    if not snapshot_path.exists():
        return []

    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if isinstance(payload, dict):
        return _parse_51job_api_items(payload)

    if isinstance(payload, list):
        normalized: List[Dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "job_title": str(item.get("job_title", "")).strip(),
                    "company_name": str(item.get("company_name", "")).strip(),
                    "city": str(item.get("city", "")).strip(),
                    "salary_raw": str(item.get("salary_raw", "")).strip(),
                    "post_date": str(item.get("post_date", "")).strip(),
                    "job_url": str(item.get("job_url", "")).strip(),
                }
            )
        return normalized

    return []


def _deduplicate_jobs(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped = []
    for job in jobs:
        key = (
            job.get("job_title", "").strip().lower(),
            job.get("company_name", "").strip().lower(),
            job.get("job_url", "").strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(job)
    return deduped


def _build_51job_api_url(keyword: str, page_num: int) -> str:
    encoded_keyword = quote(keyword)
    return (
        "https://we.51job.com/api/job/search-pc?"
        f"api_key=51job&timestamp={int(time.time())}&keyword={encoded_keyword}"
        f"&searchType=2&sortType=1&city=020000&pageNum={page_num}"
    )


def _collect_jobs_via_requests(keyword: str, max_pages: int) -> List[Dict[str, Any]]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://we.51job.com/",
    }

    collected: List[Dict[str, Any]] = []
    detected_total_pages = max_pages
    consecutive_empty = 0

    for page_num in range(1, max_pages + 1):
        _sleep_random(1.0, 3.0)
        page_jobs: List[Dict[str, Any]] = []

        for retry in range(2):
            try:
                response = requests.get(_build_51job_api_url(keyword, page_num), headers=headers, timeout=10)
                response.raise_for_status()
                payload = response.json()
                page_jobs = _parse_51job_api_items(payload)

                if page_num == 1:
                    total_count = _extract_total_count(payload)
                    page_size = max(len(page_jobs), 1)
                    if total_count > 0:
                        detected_total_pages = min(max_pages, (total_count + page_size - 1) // page_size)
                break
            except Exception:
                if retry == 0:
                    _sleep_random(1.0, 2.0)
                    continue

        if page_jobs:
            collected.extend(page_jobs)
            consecutive_empty = 0
        else:
            consecutive_empty += 1

        if page_num >= detected_total_pages:
            break
        if consecutive_empty >= 2:
            break

    return _deduplicate_jobs(collected)


def _collect_jobs_playwright(keyword: str, max_pages: int) -> List[Dict[str, Any]]:
    encoded_keyword = quote(keyword)
    collected: List[Dict[str, Any]] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        _sleep_random()
        page.goto("https://we.51job.com/", timeout=30_000, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        _sleep_random()

        # Simulate a realistic search action once, then iterate pages by URL params.
        page.goto(
            (
                "https://we.51job.com/pc/search?"
                f"keyword={encoded_keyword}&searchType=2&sortType=1&city=020000&pageNum=1"
            ),
            timeout=30_000,
            wait_until="domcontentloaded",
        )

        consecutive_empty = 0
        for page_num in range(1, max_pages + 1):
            _sleep_random()
            page.goto(
                (
                    "https://we.51job.com/pc/search?"
                    f"keyword={encoded_keyword}&searchType=2&sortType=1&city=020000&pageNum={page_num}"
                ),
                timeout=30_000,
                wait_until="domcontentloaded",
            )
            page.wait_for_timeout(2000)
            _sleep_random()

            # Try extracting payload from the page source first.
            html = page.content()
            if _is_challenge_page(html):
                # Let JS challenge set cookies and reload once.
                page.wait_for_timeout(4000)
                page.reload(wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_timeout(2000)
                html = page.content()

            payload_match = re.search(r"window\.__SEARCH_RESULT__\s*=\s*(\{.*?\});", html, re.S)
            page_jobs: List[Dict[str, Any]] = []
            if payload_match:
                try:
                    payload = json.loads(payload_match.group(1))
                    page_jobs = _parse_51job_api_items(payload)
                except json.JSONDecodeError:
                    page_jobs = []

            # If page payload is missing, use context request as fallback while keeping Playwright runtime.
            if not page_jobs:
                # Try fetching via browser context so anti-bot cookies are included.
                try:
                    browser_payload = page.evaluate(
                        """
                        async (url) => {
                            const resp = await fetch(url, { credentials: 'include' });
                            const ct = resp.headers.get('content-type') || '';
                            if (!ct.includes('application/json')) {
                                return null;
                            }
                            return await resp.json();
                        }
                        """,
                        _build_51job_api_url(keyword, page_num),
                    )
                    if isinstance(browser_payload, dict):
                        page_jobs = _parse_51job_api_items(browser_payload)
                except Exception:
                    page_jobs = []

            if not page_jobs:
                api_url = (
                    "https://we.51job.com/api/job/search-pc?"
                    f"api_key=51job&timestamp={int(time.time())}&keyword={encoded_keyword}"
                    f"&searchType=2&sortType=1&city=020000&pageNum={page_num}"
                )
                resp = context.request.get(api_url, timeout=10_000)
                if resp.ok:
                    try:
                        api_payload = resp.json()
                        page_jobs = _parse_51job_api_items(api_payload)
                    except Exception:
                        page_jobs = []

            if not page_jobs:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                continue

            consecutive_empty = 0

            collected.extend(page_jobs)

        browser.close()

    return _deduplicate_jobs(collected)


def collect_jobs(keyword: str, max_pages: int = 3) -> CollectorResult:
    """
    Main collection entry.

    - Uses Playwright (headless=True) as the primary collector.
    - Limits pages to <= 30 with anti-bot delays/retries.
    - Adds random delays between operations.
    - Retries once on failure and then falls back to snapshot.
    """
    capped_pages = max(1, min(int(max_pages), 30))

    for attempt in range(2):
        try:
            jobs = _collect_jobs_playwright(keyword=keyword, max_pages=capped_pages)
            # If Playwright gives too few jobs, supplement with direct API pagination.
            if len(jobs) < min(40, capped_pages * 20):
                api_jobs = _collect_jobs_via_requests(keyword=keyword, max_pages=capped_pages)
                if api_jobs:
                    jobs = _deduplicate_jobs(jobs + api_jobs)

            if jobs:
                note = "playwright_ok"
                if capped_pages < max_pages:
                    note += "_max_pages_capped_to_30"
                return CollectorResult(jobs=jobs, source="playwright", note=note)
        except (PlaywrightTimeoutError, Exception) as exc:
            if attempt == 0:
                _sleep_random(1.0, 2.0)
                continue

            # Online API fallback before local snapshot to preserve pagination.
            api_jobs = _collect_jobs_via_requests(keyword=keyword, max_pages=capped_pages)
            if api_jobs:
                return CollectorResult(
                    jobs=api_jobs,
                    source="api_fallback",
                    note=f"playwright_failed_after_retry:{type(exc).__name__}",
                )

            fallback_jobs = _load_jobs_from_snapshot(DEFAULT_FALLBACK_SNAPSHOT)
            return CollectorResult(
                jobs=_deduplicate_jobs(fallback_jobs),
                source="snapshot_fallback",
                note=f"playwright_failed_after_retry:{type(exc).__name__}",
            )

    api_jobs = _collect_jobs_via_requests(keyword=keyword, max_pages=capped_pages)
    if api_jobs:
        return CollectorResult(
            jobs=api_jobs,
            source="api_fallback",
            note="playwright_empty_after_retry_api_ok",
        )

    fallback_jobs = _load_jobs_from_snapshot(DEFAULT_FALLBACK_SNAPSHOT)
    return CollectorResult(
        jobs=_deduplicate_jobs(fallback_jobs),
        source="snapshot_fallback",
        note="playwright_empty_after_retry",
    )
