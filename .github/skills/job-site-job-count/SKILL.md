---
name: job-site-job-count
description: Agent 驱动执行广州 AI产品经理岗位采集与分析，固定口径输出岗位总量、薪酬分析与最新优先 Top15 岗位。
---

# Job Site Job Analysis Skill

当用户希望分析岗位市场而不是只看数量时，使用此 Skill。

典型请求：
- 在某招聘网站查询某岗位并分析薪资分布。
- 输出 High-level 总结和最新优先 Top15 岗位。

## Agent 驱动模式（必须）
- 优先通过 Agent 运行项目脚本，而不是手工拼接：
  - `python 02Development_Zone/AI-TrendRadar/main.py --keyword "AI产品经理+广州" --max-pages 10`
- 读取脚本产物并汇总：
  - `04AI_Job_Report/jobs.csv`
  - `04AI_Job_Report/Report_YYYYMMDD.md`
- 仅在脚本失败时，进入浏览器抓取/快照兜底。

## 输入参数
- `job_site`：网站 URL 或站点名
- `keyword`：固定 `AI产品经理+广州`
- `city`：固定 `广州`
- `top_n`：默认 15

## 固定查询口径（必须）
- 报告范围仅限广州。
- 搜索关键词固定为 `AI产品经理+广州`。
- 若用户输入其他城市或关键词，执行时改写为固定口径，并在最终输出备注该改写。

## 默认工具策略（必须）
- 浏览器抓取默认使用 Playwright 作为主采集器（headless 模式），优先抓取列表页数据。
- MCP 仅用于增强层：对最新岗位样本做少量深度分析（最多 5 条），不得用于全量采集。
- 当 Playwright 失败时，先自动重试一次；重试后仍失败才允许降级到替代路径（如离线快照）。
- 若判定当前为“Agent 子代理受限环境”（缺少浏览器抓取或脚本落盘所需能力），必须立即停止执行，不得继续降级或改走手工流程。
- 发生降级时必须在 Evidence 中记录：
  - `browser_tool`: `fallback`
  - `fallback_reason`: 具体失败原因
  - `subagent_limited`: `yes/no`
  - `stop_reason`: 当 `subagent_limited=yes` 时的停止原因

## 默认分析策略（必须）
- 文件分析默认使用“脚本流程”，禁止手工拼接统计文本。
- 脚本流程：读取搜索 JSON 快照 -> 解析/过滤/去重/统计 -> 落盘 `data/jobs.csv` 与 `report.md`。
- 快照输入优先级：
  - `00Ad_Hoc/51job_search_latest_323.json`
  - 若存在更新的分页合并快照，优先使用更新快照。
- 当在线抓取受阻但快照可用时，允许进入离线脚本分析模式，并在报告中声明阻塞点与样本口径。

## 执行步骤
0. 工具初始化
- 优先初始化 chrome-devtools-mcp 会话用于页面导航、交互和网络请求读取。
- 若初始化失败，先判断是否为“子代理受限环境”；若是则立即停止执行。
- 仅在非受限环境下，才允许进入降级流程。

1. 打开网站并搜索
- 打开 `job_site`，输入固定关键词 `AI产品经理+广州`，进入搜索结果页。
- 若站点支持城市筛选，强制设置城市为 `广州`。
- 如可选排序，切换为“最新优先”。

2. 提取岗位总数
- 优先读取页面可见文本（如“共xx个职位”）。
- 若无明确文本，读取搜索接口响应字段：
  - `totalCount` > `total` > `count` > `totalPage * pageSize`

2.1 分页抓取（必须）
- 统计分析不能只用第一页。
- 从接口读取 `totalCount` 与 `pageSize`，按 `pageNum` 分页抓取，目标为覆盖全部页。
- 若无法全量抓取，至少抓取前 5 页，并在输出中标明样本口径：
  - `sample_pages`
  - `sample_jobs`
  - `coverage = sample_jobs / total_jobs`
- 建议停止条件：最后一页、连续2页无新增、或达到 `max_pages=30`。

3. 必要时登录
- 仅在登录墙阻塞时读取：
  - `00Ad_Hoc/key.txt`
- 登录后重新执行搜索与提取。

4. 抓取 TopN（默认15）岗位
- 字段：
  - `job_title`
  - `company_name`
  - `city`
  - `salary_raw`
  - `experience_required`
  - `education_required`
  - `job_description`
  - `post_date`

4.1 Top15 前扩样（必须）
- 在生成 Top15 前，先抓取更多岗位样本：
  - 优先全量分页。
  - 若受限，至少抓取 `max(top_n*3, 30)` 条。

4.2 关键词相关性过滤（必须）
- Top15 前必须剔除与关键词无关岗位。
- 固定关键词 `AI产品经理+广州` 的相关性规则：
  - 城市需匹配广州。
  - 标题或 JD 命中 AI 词：`AI|人工智能|AIGC|大模型|LLM|智能`。
  - 且命中 PM 词：`PM|产品经理|Product Manager|产品`。
- 输出需包含过滤统计：
  - `raw_jobs`
  - `relevant_jobs`
  - `dropped_jobs`
  - `drop_reason_breakdown`

5. 数据处理与分析
- 解析薪资得到 `salary_min`、`salary_max`、`salary_avg`。
- 统一单位到 `K/月`。
- 按 `job_title + company_name` 去重。
- 统计薪资分布：`0-20K`、`20K-40K`、`40K-60K`、`60K+`。
- 计算 `median_salary` 与 `top_cities`（前3）。
- 口径校验（必须）：
  - `salary_sample_jobs =` 有可解析薪资的岗位数。
  - `salary_distribution_total = 0-20K + 20K-40K + 40K-60K + 60K+`。
  - 必须满足 `salary_distribution_total == salary_sample_jobs`。
  - 若 `total_jobs != salary_distribution_total`，必须在报告中明确标注“薪资分布基于样本”，并给出覆盖率。
- 覆盖率字段（必须）：
  - `overall_coverage = sample_jobs / total_jobs`
  - `salary_coverage = salary_sample_jobs / sample_jobs`

5.1 脚本分析执行（必须）
- 默认通过脚本流程完成统计与落盘，不使用手工逐条汇总。
- 脚本必须完成：
  - `totalCount` 优先作为 `total_jobs` 来源。
  - 薪资解析到 `K/月`、分箱统计与中位数计算。
  - 输出 `salary_sample_jobs`、`salary_distribution_total`、`overall_coverage`、`salary_coverage`。
  - 校验 `salary_distribution_total == salary_sample_jobs`。
- 仅在脚本执行失败时允许人工兜底；若人工兜底，报告中必须标记 `manual_fallback=true`。

6. 结果落盘（必须）
- `04AI_Job_Report/jobs.csv`
- `04AI_Job_Report/Report_YYYYMMDD.md`
- `Report_YYYYMMDD.md` 标题日期必须是报告生成日期（非固定日期），格式：`YYYY年M月D日`（建议按 Asia/Shanghai 时区）
- `report.md` 输出模板参考文件（相对路径）为：`example/gz_report.md`（以 `.github/skills/job-site-job-count/SKILL.md` 为基准）
- 生成时必须读取并对齐该参考模板的结构与视觉层次（徽章 + 仪表盘表格 + 热力条 + Mermaid 图 + Top15 折叠详情卡）
- 若参考模板不可读，按最小兜底骨架输出：

```markdown
# 广州 AI产品经理 招聘市场报告（{{report_date}}）
## 市场仪表盘
## 薪资热力条
## 薪资分布图（mermaid pie）
## Top 15 最新岗位
```

## 站点提示
- 51job（前程无忧）
  - URL 示例：`https://www.51job.com/guangzhou`
  - 常见总数字段：`totalCount`
- BOSS 直聘
  - URL 示例：`https://www.zhipin.com/web/geek/jobs`
  - 登录墙更常见，必要时登录或报告阻塞

## 输出模板（对话）

### Part 1: High-level Summary
- `total_jobs`
- `median_salary`（K/月）
- `salary_distribution`
- `salary_sample_jobs`
- `salary_distribution_total`
- `overall_coverage`
- `salary_coverage`
- `top_cities`
- `report_date`（报告生成日期，`YYYY年M月D日`）
- `sample_pages`
- `sample_jobs`
- `coverage`
- `query_scope`（固定为 `keyword=AI产品经理+广州, city=广州`）
- `raw_jobs`
- `relevant_jobs`
- `dropped_jobs`
- `drop_reason_breakdown`

### Part 2: Top 15 Cases（最新优先）
每条包含：
- `job_title`
- `company_name`
- `city`
- `salary_range`
- `experience_required`
- `education_required`
- `post_date`
- `jd_summary`（<=100字）

### Evidence
- `browser_tool`: `chrome-devtools-mcp` 或 `fallback`
- `fallback_reason`: 当降级时的错误原因
- `source_type`: `page_text` 或 `api_field`
- `source_name`: 文本片段或字段名
- `source_url`: 页面或接口 URL
- `query`: keyword + city/filters
- `login_used`: yes/no
- `timestamp`: ISO-8601

## 约束
- 禁止回显 `key.txt` 明文账号密码。
- 禁止投递、沟通、改简历等副作用行为。
- 无法完整提取时，说明阻塞原因与已获取数据。
- 必须说明分页口径（全量分页或样本分页）。
- 视觉增强不得修改统计数值；`岗位详情卡` 必须覆盖 Top15 全部岗位。
- 详情卡标题中的岗位名为纯文本；展开后的“岗位”字段必须是可点击链接（基于 `job_url`）。
- 默认由脚本流程生成 `jobs.csv` 与 `Report_YYYYMMDD.md`，不得跳过脚本直接手工编造统计结果。
- 若为“Agent 子代理受限环境”，必须立即终止并返回受限原因，不得继续执行抓取、脚本分析或落盘。
