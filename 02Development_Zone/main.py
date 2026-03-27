from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict

from mcp_enhance import mcp_enhance
from playwright_collector import collect_jobs
from processing import process
from reporting import generate_report


def run_pipeline(keyword: str = "AI产品经理+广州", max_pages: int = 10) -> Dict[str, Any]:
    collector_result = collect_jobs(keyword=keyword, max_pages=max_pages)
    cleaned_jobs = process(collector_result.jobs)
    enhanced_jobs = mcp_enhance(cleaned_jobs)

    output_dir = Path(__file__).resolve().parents[1] / "04AI_Job_Report"
    report_result = generate_report(
        cleaned_jobs,
        enhanced_jobs,
        output_dir,
        query_scope=f"keyword={keyword}, city=广州",
    )

    return {
        "collector_source": collector_result.source,
        "collector_note": collector_result.note,
        "raw_jobs": len(collector_result.jobs),
        "cleaned_jobs": len(cleaned_jobs),
        "enhanced_jobs": len(enhanced_jobs),
        **report_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Position Radar pipeline")
    parser.add_argument("--keyword", default="AI产品经理+广州", help="search keyword")
    parser.add_argument("--max-pages", type=int, default=10, help="max pages to collect (capped at 30)")
    args = parser.parse_args()

    result = run_pipeline(keyword=args.keyword, max_pages=args.max_pages)
    print("pipeline_done")
    print(f"collector_source={result['collector_source']}")
    print(f"collector_note={result['collector_note']}")
    print(f"raw_jobs={result['raw_jobs']}")
    print(f"cleaned_jobs={result['cleaned_jobs']}")
    print(f"enhanced_jobs={result['enhanced_jobs']}")
    print(f"csv_path={result['csv_path']}")
    print(f"report_path={result['report_path']}")


if __name__ == "__main__":
    main()
