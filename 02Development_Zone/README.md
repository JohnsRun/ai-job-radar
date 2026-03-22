# AI Trend Radar

## Overview
- Playwright is the primary collector for job list pages.
- MCP enhancement is a lightweight optional layer over latest jobs only.
- The pipeline supports automated runs via cron or GitHub Actions.

## Run
```bash
/Users/runjsh/Script/AI_Position_Radar/.venv/bin/python main.py --keyword "AI 产品经理" --max-pages 3
```

## Outputs
- `output/jobs.csv`
- `output/report.md`

## MCP Enhancement Adapter
- Default mode uses local HTTP page fetch as a stub parser.
- To connect a real MCP service, set environment variable:
```bash
export MCP_ENHANCE_ENDPOINT="https://your-mcp-service/enhance"
```
The endpoint should accept JSON:
```json
{"job_url": "...", "timeout": 10}
```
and return:
```json
{"jd_text": "..."}
```

## Automation
- GitHub Actions workflow: `.github/workflows/scheduled-job-radar.yml`
- Local cron template: `cron.example`
