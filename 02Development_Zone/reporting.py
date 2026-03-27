from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from mcp_enhance import summarize_enhancement
from processing import summarize_base_metrics


def _format_today() -> str:
    now = datetime.now()
    return f"{now.year}年{now.month}月{now.day}日"


def _report_filename() -> str:
    return f"Report_{datetime.now().strftime('%Y%m%d')}.md"


def _csv_filename() -> str:
    return f"jobs_{datetime.now().strftime('%Y%m%d')}.csv"


def _build_heat_bar(value: int, max_value: int) -> str:
    if value <= 0 or max_value <= 0:
        return "0"
    bar_len = max(1, int((value / max_value) * 30))
    return f"{'█' * bar_len} {value}"


def _safe_md_text(text: Any) -> str:
    value = str(text or "")
    return value.replace("[", "\\[").replace("]", "\\]")


def _job_title_link(job: Dict[str, Any]) -> str:
    title = _safe_md_text(job.get("job_title", ""))
    url = str(job.get("job_url", "") or "").strip()
    return f"[{title}]({url})" if url else title


def _write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    columns = [
        "job_title",
        "company_name",
        "city",
        "salary_raw",
        "salary_min",
        "salary_max",
        "salary_avg",
        "post_date",
        "job_url",
        "skills",
        "ai_level",
        "product_type",
        "tools",
        "enhance_source",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            out = dict(row)
            out["skills"] = ", ".join(row.get("skills") or [])
            out["tools"] = ", ".join(row.get("tools") or [])
            writer.writerow({k: out.get(k, "") for k in columns})


def generate_report(
    cleaned_jobs: List[Dict[str, Any]],
    enhanced_jobs: List[Dict[str, Any]],
    output_dir: Path,
    query_scope: str,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    base = summarize_base_metrics(cleaned_jobs)
    enhanced = summarize_enhancement(enhanced_jobs)

    csv_path = output_dir / _csv_filename()
    report_path = output_dir / _report_filename()
    _write_csv(enhanced_jobs, csv_path)

    dist = base["salary_distribution"]
    dist_values = [dist["0-20K"], dist["20K-40K"], dist["40K-60K"], dist["60K+"]]
    max_dist = max(dist_values) if dist_values else 0

    skill_text = (
        "、".join([f"{name}({count})" for name, count in enhanced["top_skills"]])
        if enhanced["top_skills"]
        else "无"
    )
    tool_text = (
        "、".join([f"{name}({count})" for name, count in enhanced["top_tools"]])
        if enhanced["top_tools"]
        else "无"
    )

    top_jobs = sorted(cleaned_jobs, key=lambda x: x.get("post_date", ""), reverse=True)[:15]

    lines: List[str] = []
    lines.append(f"# 广州 AI产品经理 招聘市场报告（{_format_today()}）")
    lines.append("")
    lines.append("## 市场仪表盘")
    lines.append("")
    lines.append("| 指标 | 数值 |")
    lines.append("|---|---:|")
    lines.append("| 查询条件 | Top50活跃职位 |")
    lines.append(f"| 薪资中位数（K/月） | **{base['median_salary'] if base['median_salary'] is not None else 'N/A'}** |")
    lines.append(f"| 查询范围 | `{query_scope}` |")
    lines.append("")
    lines.append("### 薪资热力条")
    lines.append("")
    lines.append(f"- `0-20K` : {_build_heat_bar(dist['0-20K'], max_dist)}")
    lines.append(f"- `20K-40K` : {_build_heat_bar(dist['20K-40K'], max_dist)}")
    lines.append(f"- `40K-60K` : {_build_heat_bar(dist['40K-60K'], max_dist)}")
    lines.append(f"- `60K+` : {_build_heat_bar(dist['60K+'], max_dist)}")
    lines.append("")
    lines.append("### 薪资分布图")
    lines.append("")
    lines.append("```mermaid")
    lines.append("pie title 广州 AI产品经理 薪资分布（样本）")
    lines.append(f"  \"0-20K\" : {dist['0-20K']}")
    lines.append(f"  \"20K-40K\" : {dist['20K-40K']}")
    lines.append(f"  \"40K-60K\" : {dist['40K-60K']}")
    lines.append(f"  \"60K+\" : {dist['60K+']}")
    lines.append("```")
    lines.append("")
    lines.append("## Top 15 最新岗位")
    lines.append("")
    for idx, job in enumerate(top_jobs, start=1):
        company = _safe_md_text(job.get("company_name", ""))
        title = _safe_md_text(job.get("job_title", ""))
        city = _safe_md_text(job.get("city", ""))
        salary = _safe_md_text(job.get("salary_raw", ""))
        post_date = _safe_md_text(job.get("post_date", ""))

        lines.append("<details>")
        lines.append(
            f"<summary><strong>#{idx} {company} - {title}（{city}，{salary}）</strong></summary>"
        )
        lines.append("")
        lines.append(f"- 岗位：{_job_title_link(job)}")
        lines.append(f"- 公司：{company}")
        lines.append(f"- 城市：{city}")
        lines.append(f"- 薪资：{salary}")
        lines.append(f"- 发布时间：{post_date}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    lines.append("")
    lines.append("## 🤖 AI深度分析（MCP增强）")
    lines.append("")
    lines.append(f"- 高频技能 Top5: {skill_text}")
    lines.append(f"- AI相关岗位占比: {enhanced['ai_related_ratio']}%")
    lines.append(f"- 常见工具 Top3: {tool_text}")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "csv_path": str(csv_path),
        "report_path": str(report_path),
        "base_metrics": base,
        "enhance_metrics": enhanced,
    }
