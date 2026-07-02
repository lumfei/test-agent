"""
测试报告生成器 — 生成 Markdown/HTML/JSON 格式的测试报告。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class TestCaseResult:
    """单个用例的执行结果"""
    case_name: str
    passed: bool
    method: str
    path: str
    status_code: int
    elapsed_ms: float
    expected_status: Any
    category: str
    checks: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    response_preview: str = ""


@dataclass
class TestReport:
    """完整的测试报告"""
    report_id: str
    api_name: str
    base_url: str
    spec_url: str | None
    generated_at: str
    total_cases: int
    passed: int
    failed: int
    errors: int
    duration_seconds: float
    results: list[TestCaseResult] = field(default_factory=list)
    summary_by_category: dict[str, dict[str, int]] = field(default_factory=dict)
    summary_by_endpoint: dict[str, dict[str, int]] = field(default_factory=dict)

    @property
    def pass_rate(self) -> float:
        if self.total_cases == 0:
            return 0.0
        return self.passed / self.total_cases

    @property
    def is_healthy(self) -> bool:
        """pass_rate >= 95% 视为健康"""
        return self.pass_rate >= 0.95


class ReportGenerator:
    """
    测试报告生成工具。

    职责：将测试结果汇总为结构化报告，支持多种输出格式。
    边界：只生成报告，不分析结果——分析由 LLM 完成。
    """

    def generate(
        self,
        api_name: str,
        base_url: str,
        spec_url: str | None,
        results: list[TestCaseResult],
        duration_seconds: float,
    ) -> TestReport:
        """从测试结果生成报告对象"""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = sum(1 for r in results if not r.passed and not r.error)
        errors = sum(1 for r in results if r.error)

        # 按类别汇总
        by_category: dict[str, dict[str, int]] = {}
        for r in results:
            cat = r.category or "unknown"
            if cat not in by_category:
                by_category[cat] = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
            by_category[cat]["total"] += 1
            if r.passed:
                by_category[cat]["passed"] += 1
            elif r.error:
                by_category[cat]["errors"] += 1
            else:
                by_category[cat]["failed"] += 1

        # 按端点汇总
        by_endpoint: dict[str, dict[str, int]] = {}
        for r in results:
            key = f"{r.method} {r.path}"
            if key not in by_endpoint:
                by_endpoint[key] = {"total": 0, "passed": 0, "failed": 0, "errors": 0}
            by_endpoint[key]["total"] += 1
            if r.passed:
                by_endpoint[key]["passed"] += 1
            elif r.error:
                by_endpoint[key]["errors"] += 1
            else:
                by_endpoint[key]["failed"] += 1

        import uuid
        report_id = uuid.uuid4().hex[:12]

        return TestReport(
            report_id=report_id,
            api_name=api_name,
            base_url=base_url,
            spec_url=spec_url,
            generated_at=datetime.now(timezone.utc).isoformat(),
            total_cases=total,
            passed=passed,
            failed=failed,
            errors=errors,
            duration_seconds=duration_seconds,
            results=results,
            summary_by_category=by_category,
            summary_by_endpoint=by_endpoint,
        )

    def to_markdown(self, report: TestReport) -> str:
        """生成 Markdown 报告"""
        lines = [
            f"# 🔬 API 自动化测试报告",
            "",
            f"| 项目 | 详情 |",
            f"|------|------|",
            f"| **API 名称** | {report.api_name} |",
            f"| **Base URL** | {report.base_url} |",
            f"| **Spec 来源** | {report.spec_url or '手动配置'} |",
            f"| **报告 ID** | {report.report_id} |",
            f"| **生成时间** | {report.generated_at} |",
            f"| **总耗时** | {report.duration_seconds:.1f}s |",
            "",
            f"## 📊 总览",
            "",
            f"| 指标 | 值 |",
            f"|------|------|",
            f"| 总用例数 | {report.total_cases} |",
            f"| ✅ 通过 | {report.passed} |",
            f"| ❌ 失败 | {report.failed} |",
            f"| ⚠️ 错误 | {report.errors} |",
            f"| 📈 通过率 | **{report.pass_rate:.1%}** |",
            "",
        ]

        # 按类别
        if report.summary_by_category:
            lines.append("## 📂 按类别统计")
            lines.append("")
            lines.append("| 类别 | 总数 | 通过 | 失败 | 错误 | 通过率 |")
            lines.append("|------|------|------|------|------|--------|")
            for cat, stats in sorted(report.summary_by_category.items()):
                rate = stats["passed"] / max(stats["total"], 1)
                lines.append(
                    f"| {cat} | {stats['total']} | {stats['passed']} | "
                    f"{stats['failed']} | {stats['errors']} | {rate:.0%} |"
                )
            lines.append("")

        # 按端点
        if report.summary_by_endpoint:
            lines.append("## 🔗 按端点统计")
            lines.append("")
            lines.append("| 端点 | 总数 | 通过 | 失败 | 错误 |")
            lines.append("|------|------|------|------|------|")
            for ep, stats in report.summary_by_endpoint.items():
                lines.append(
                    f"| {ep} | {stats['total']} | {stats['passed']} | "
                    f"{stats['failed']} | {stats['errors']} |"
                )
            lines.append("")

        # 失败详情
        failures = [r for r in report.results if not r.passed]
        if failures:
            lines.append("## ❌ 失败/错误用例详情")
            lines.append("")
            for i, r in enumerate(failures, 1):
                lines.extend([
                    f"### {i}. {r.case_name}",
                    "",
                    f"- **请求**: {r.method} {r.path}",
                    f"- **类别**: {r.category}",
                    f"- **状态码**: {r.status_code} (期望 {r.expected_status})",
                    f"- **耗时**: {r.elapsed_ms:.0f}ms",
                    f"- **错误**: {r.error or '验证未通过'}",
                ])
                if r.response_preview:
                    lines.append(f"- **响应预览**: `{r.response_preview[:500]}`")
                if r.checks:
                    for check in r.checks:
                        if not check.get("passed"):
                            lines.append(f"- **检查失败**: {check.get('detail', '')}")
                lines.append("")

        # 全部结果表
        lines.append("## 📋 全部结果")
        lines.append("")
        lines.append("| # | 用例 | 方法 | 路径 | 状态码 | 耗时 | 结果 |")
        lines.append("|---|------|------|------|--------|------|------|")
        for i, r in enumerate(report.results, 1):
            status = "✅" if r.passed else ("⚠️" if r.error else "❌")
            lines.append(
                f"| {i} | {r.case_name[:50]} | {r.method} | {r.path[:40]} | "
                f"{r.status_code} | {r.elapsed_ms:.0f}ms | {status} |"
            )

        return "\n".join(lines)

    def to_html(self, report: TestReport) -> str:
        """生成富交互 HTML 报告（单文件，无外部依赖）"""
        return _render_html_report(report)

    def to_json(self, report: TestReport) -> str:
        """生成 JSON 报告"""
        data = {
            "report_id": report.report_id,
            "api_name": report.api_name,
            "base_url": report.base_url,
            "spec_url": report.spec_url,
            "generated_at": report.generated_at,
            "duration_seconds": report.duration_seconds,
            "summary": {
                "total": report.total_cases,
                "passed": report.passed,
                "failed": report.failed,
                "errors": report.errors,
                "pass_rate": report.pass_rate,
            },
            "by_category": report.summary_by_category,
            "by_endpoint": report.summary_by_endpoint,
            "results": [
                {
                    "name": r.case_name,
                    "passed": r.passed,
                    "method": r.method,
                    "path": r.path,
                    "status_code": r.status_code,
                    "elapsed_ms": r.elapsed_ms,
                    "category": r.category,
                    "checks": r.checks,
                    "error": r.error,
                }
                for r in report.results
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def save(
        self, report: TestReport, output_dir: str | Path, formats: list[str] | None = None
    ) -> dict[str, str]:
        """
        保存报告到文件。

        Args:
            report: 测试报告
            output_dir: 输出目录
            formats: 输出格式列表，默认 ["md", "json"]

        Returns:
            各格式的文件路径映射
        """
        formats = formats or ["md", "json"]
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        prefix = f"report_{report.report_id}"
        paths: dict[str, str] = {}

        generators = {
            "md": (self.to_markdown, f"{prefix}.md"),
            "html": (self.to_html, f"{prefix}.html"),
            "json": (self.to_json, f"{prefix}.json"),
        }

        for fmt in formats:
            if fmt in generators:
                gen_func, filename = generators[fmt]
                content = gen_func(report)
                filepath = output_dir / filename
                filepath.write_text(content, encoding="utf-8")
                paths[fmt] = str(filepath)

        return paths


# ── Rich HTML Report ──────────────────────────────────────────────

def _render_html_report(report: TestReport) -> str:
    """将 TestReport 渲染为自包含的富交互 HTML 单文件"""

    # 通过率颜色
    rate = report.pass_rate
    if rate >= 0.95:
        rate_color = "#22c55e"
    elif rate >= 0.80:
        rate_color = "#f59e0b"
    else:
        rate_color = "#ef4444"

    def _category_rows() -> str:
        rows = []
        for cat, stats in sorted(report.summary_by_category.items()):
            cat_rate = stats["passed"] / max(stats["total"], 1) * 100
            bg = "#22c55e" if cat_rate >= 90 else ("#f59e0b" if cat_rate >= 70 else "#ef4444")
            rows.append(f"""
            <tr>
                <td><span class="badge badge-{cat}">{cat}</span></td>
                <td>{stats['total']}</td>
                <td class="c-pass">{stats['passed']}</td>
                <td class="c-fail">{stats['failed']}</td>
                <td class="c-err">{stats['errors']}</td>
                <td>
                    <div class="bar-track"><div class="bar-fill" style="width:{cat_rate}%;background:{bg}"></div></div>
                    <span class="bar-label">{cat_rate:.0f}%</span>
                </td>
            </tr>""")
        return "".join(rows)

    def _endpoint_rows() -> str:
        rows = []
        for ep, stats in sorted(report.summary_by_endpoint.items(), key=lambda x: -x[1]["total"]):
            ep_rate = stats["passed"] / max(stats["total"], 1) * 100
            bg = "#22c55e" if ep_rate >= 90 else ("#f59e0b" if ep_rate >= 70 else "#ef4444")
            rows.append(f"""
            <tr>
                <td class="ep-cell">{ep}</td>
                <td>{stats['total']}</td>
                <td class="c-pass">{stats['passed']}</td>
                <td class="c-fail">{stats['failed']}</td>
                <td class="c-err">{stats['errors']}</td>
                <td>
                    <div class="bar-track"><div class="bar-fill" style="width:{ep_rate}%;background:{bg}"></div></div>
                    <span class="bar-label">{ep_rate:.0f}%</span>
                </td>
            </tr>""")
        return "".join(rows)

    def _result_rows() -> str:
        rows = []
        for i, r in enumerate(report.results, 1):
            cls = "r-pass" if r.passed else ("r-err" if r.error else "r-fail")
            status_text = "PASS" if r.passed else ("ERR" if r.error else "FAIL")
            status_code = r.status_code
            sc_cls = ""
            if 200 <= status_code < 300:
                sc_cls = "sc-2xx"
            elif 400 <= status_code < 500:
                sc_cls = "sc-4xx"
            elif 500 <= status_code < 600:
                sc_cls = "sc-5xx"
            rows.append(f"""
            <tr class="{cls}">
                <td>{i}</td>
                <td title="{r.case_name}">{r.case_name[:55]}</td>
                <td><span class="badge badge-{r.category}">{r.category}</span></td>
                <td><code>{r.method}</code></td>
                <td class="ep-cell" title="{r.path}">{r.path[:40]}</td>
                <td class="{sc_cls}">{status_code}</td>
                <td>{r.elapsed_ms:.0f}ms</td>
                <td class="status-cell">{status_text}</td>
            </tr>""")
        return "".join(rows)

    def _failure_detail() -> str:
        failures = [r for i, r in enumerate(report.results, 1) if not r.passed]
        if not failures:
            return '<div class="empty-state">🎉 所有用例全部通过！</div>'
        items = []
        for idx, r in enumerate(failures, 1):
            checks_html = ""
            if r.checks:
                checks_html = "<ul class='check-list'>" + "".join(
                    f"<li>{c.get('detail', str(c))}</li>"
                    for c in r.checks if not c.get("passed")
                ) + "</ul>"
            resp_html = f'<pre class="resp-preview">{r.response_preview[:500]}</pre>' if r.response_preview else ""
            items.append(f"""
            <div class="failure-card">
                <div class="failure-header">
                    <span class="failure-idx">#{idx}</span>
                    <span class="badge badge-{r.category}">{r.category}</span>
                    <code>{r.method} {r.path}</code>
                </div>
                <div class="failure-body">
                    <div class="failure-meta">
                        <span>状态码: <strong class="sc-bad">{r.status_code}</strong> (期望 {r.expected_status})</span>
                        <span>耗时: {r.elapsed_ms:.0f}ms</span>
                        <span>错误: {r.error or '验证未通过'}</span>
                    </div>
                    {checks_html}
                    {resp_html}
                </div>
            </div>""")
        return "".join(items)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>API Test Report — {report.api_name}</title>
<style>
:root {{
    --bg: #f8fafc; --card: #fff; --text: #1e293b; --muted: #64748b;
    --border: #e2e8f0; --pass: #22c55e; --fail: #ef4444; --err: #f59e0b;
    --shadow: 0 1px 3px rgba(0,0,0,.08);
}}
* {{ box-sizing:border-box; margin:0; padding:0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); line-height:1.5; }}
.container {{ max-width:1200px; margin:0 auto; padding:24px; }}

/* Header */
.header {{ background:linear-gradient(135deg,#1e293b,#334155); color:#fff; padding:32px 24px; border-radius:12px; margin-bottom:24px; }}
.header h1 {{ font-size:24px; margin-bottom:4px; }}
.header .meta {{ color:#94a3b8; font-size:13px; }}
.header .meta span {{ margin-right:16px; }}

/* Summary Cards */
.summary {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:16px; margin-bottom:24px; }}
.card {{ background:var(--card); border-radius:10px; padding:20px; box-shadow:var(--shadow); text-align:center; }}
.card .num {{ font-size:36px; font-weight:700; }}
.card .label {{ color:var(--muted); font-size:13px; margin-top:2px; }}
.card.total .num {{ color:#3b82f6; }}
.card.pass .num {{ color:var(--pass); }}
.card.fail .num {{ color:var(--fail); }}
.card.error .num {{ color:var(--err); }}
.card.rate .num {{ color:{rate_color}; }}

/* Gauge */
.gauge-section {{ display:flex; align-items:center; gap:24px; background:var(--card); border-radius:10px; padding:24px; box-shadow:var(--shadow); margin-bottom:24px; }}
.gauge {{ width:120px; height:120px; flex-shrink:0; }}
.gauge-bg {{ fill:none; stroke:var(--border); stroke-width:10; }}
.gauge-fill {{ fill:none; stroke:{rate_color}; stroke-width:10; stroke-linecap:round; transform:rotate(-90deg); transform-origin:50% 50%; transition:stroke-dashoffset 0.6s; }}
.gauge-text {{ font-size:22px; font-weight:700; fill:var(--text); text-anchor:middle; dominant-baseline:central; }}
.gauge-label {{ font-size:9px; fill:var(--muted); text-anchor:middle; }}
.gauge-info h3 {{ font-size:16px; margin-bottom:6px; }}
.gauge-info p {{ color:var(--muted); font-size:13px; }}

/* Tables */
.section {{ background:var(--card); border-radius:10px; box-shadow:var(--shadow); margin-bottom:24px; overflow:hidden; }}
.section-title {{ font-size:16px; font-weight:600; padding:16px 20px; border-bottom:1px solid var(--border); cursor:pointer; user-select:none; display:flex; justify-content:space-between; align-items:center; }}
.section-title:hover {{ background:#f1f5f9; }}
.section-body {{ padding:0; overflow-x:auto; }}
.section-body.collapsed {{ display:none; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }}
th {{ background:#f1f5f9; padding:10px 12px; text-align:left; font-weight:600; border-bottom:2px solid var(--border); white-space:nowrap; position:sticky; top:0; z-index:1; }}
td {{ padding:8px 12px; border-bottom:1px solid var(--border); }}
tr:hover {{ background:#f8fafc; }}

/* Bars */
.bar-track {{ display:inline-block; width:80px; height:6px; background:var(--border); border-radius:3px; vertical-align:middle; margin-right:6px; }}
.bar-fill {{ height:6px; border-radius:3px; transition:width 0.4s; }}
.bar-label {{ font-size:11px; color:var(--muted); }}

/* Badges */
.badge {{ display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:600; }}
.badge-normal {{ background:#dbeafe; color:#1e40af; }}
.badge-boundary {{ background:#fef3c7; color:#92400e; }}
.badge-error {{ background:#fee2e2; color:#991b1b; }}
.badge-security {{ background:#ede9fe; color:#5b21b6; }}

/* Status */
.c-pass {{ color:var(--pass); font-weight:600; }}
.c-fail {{ color:var(--fail); font-weight:600; }}
.c-err {{ color:var(--err); font-weight:600; }}
.sc-2xx {{ color:#16a34a; }}
.sc-4xx {{ color:#d97706; }}
.sc-5xx {{ color:#dc2626; }}
.sc-bad {{ color:var(--fail); }}
.ep-cell {{ font-family:"SF Mono",Monaco,monospace; font-size:12px; max-width:300px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.status-cell {{ font-weight:700; font-size:11px; }}

/* Result rows */
.r-pass {{ }} .r-fail {{ background:#fef2f2; }} .r-err {{ background:#fffbeb; }}

/* Search */
.search-bar {{ padding:12px 20px; border-bottom:1px solid var(--border); }}
.search-bar input {{ width:100%; padding:8px 12px; border:1px solid var(--border); border-radius:6px; font-size:13px; outline:none; }}
.search-bar input:focus {{ border-color:#3b82f6; box-shadow:0 0 0 2px rgba(59,130,246,.15); }}

/* Failure cards */
.failure-card {{ border:1px solid var(--border); border-radius:8px; margin:12px 20px; overflow:hidden; }}
.failure-card:last-child {{ margin-bottom:20px; }}
.failure-header {{ background:#fef2f2; padding:10px 14px; display:flex; align-items:center; gap:10px; font-size:13px; }}
.failure-header code {{ font-size:12px; }}
.failure-idx {{ font-weight:700; color:var(--fail); }}
.failure-body {{ padding:14px; font-size:13px; }}
.failure-meta {{ display:flex; flex-wrap:wrap; gap:12px; margin-bottom:8px; color:var(--muted); }}
.check-list {{ list-style:none; margin-top:8px; }}
.check-list li {{ padding:3px 0; color:var(--fail); }}
.check-list li::before {{ content:"✗ "; font-weight:700; }}
.resp-preview {{ background:#f1f5f9; padding:10px; border-radius:6px; font-size:12px; margin-top:8px; max-height:150px; overflow:auto; white-space:pre-wrap; word-break:break-all; }}
.empty-state {{ text-align:center; padding:40px; color:var(--muted); font-size:15px; }}

/* Footer */
.footer {{ text-align:center; color:var(--muted); font-size:12px; padding:20px; }}

@media print {{
    body {{ background:#fff; }}
    .section-body.collapsed {{ display:block!important; }}
}}
</style>
</head>
<body>

<div class="container">

<!-- Header -->
<div class="header">
    <h1>API Test Report</h1>
    <div class="meta">
        <span>API: <strong>{report.api_name}</strong></span>
        <span>Base: {report.base_url}</span>
        <span>Report ID: {report.report_id}</span>
        <span>{report.generated_at[:19]}</span>
    </div>
</div>

<!-- Summary Cards -->
<div class="summary">
    <div class="card total"><div class="num">{report.total_cases}</div><div class="label">Total Cases</div></div>
    <div class="card pass"><div class="num">{report.passed}</div><div class="label">Passed</div></div>
    <div class="card fail"><div class="num">{report.failed}</div><div class="label">Failed</div></div>
    <div class="card error"><div class="num">{report.errors}</div><div class="label">Errors</div></div>
    <div class="card rate"><div class="num">{rate:.1%}</div><div class="label">Pass Rate</div></div>
</div>

<!-- Gauge -->
<div class="gauge-section">
    <svg class="gauge" viewBox="0 0 120 120">
        <circle class="gauge-bg" cx="60" cy="60" r="52"/>
        <circle class="gauge-fill" cx="60" cy="60" r="52"
            stroke-dasharray="{3.14159 * 104:.1f}" stroke-dashoffset="{(1 - rate) * 3.14159 * 104:.1f}"/>
        <text class="gauge-text" x="60" y="54">{rate:.0%}</text>
        <text class="gauge-label" x="60" y="70">pass rate</text>
    </svg>
    <div class="gauge-info">
        <h3>{report.api_name}</h3>
        <p>{report.total_cases} test cases across {len(report.summary_by_endpoint)} endpoints &middot; {report.duration_seconds:.1f}s</p>
        <p style="margin-top:4px">Spec: {report.spec_url or 'N/A'}</p>
    </div>
</div>

<!-- Category Breakdown -->
<div class="section">
    <div class="section-title" onclick="this.nextElementSibling.classList.toggle('collapsed')">
        Category Breakdown <span style="font-size:12px;color:var(--muted)">{len(report.summary_by_category)} categories</span>
    </div>
    <div class="section-body">
        <table>
            <thead><tr><th>Category</th><th>Total</th><th>Passed</th><th>Failed</th><th>Errors</th><th>Pass Rate</th></tr></thead>
            <tbody>{_category_rows()}</tbody>
        </table>
    </div>
</div>

<!-- Endpoint Breakdown -->
<div class="section">
    <div class="section-title" onclick="this.nextElementSibling.classList.toggle('collapsed')">
        Endpoint Breakdown <span style="font-size:12px;color:var(--muted)">{len(report.summary_by_endpoint)} endpoints</span>
    </div>
    <div class="section-body">
        <table>
            <thead><tr><th>Endpoint</th><th>Total</th><th>Passed</th><th>Failed</th><th>Errors</th><th>Pass Rate</th></tr></thead>
            <tbody>{_endpoint_rows()}</tbody>
        </table>
    </div>
</div>

<!-- Failures -->
<div class="section">
    <div class="section-title" onclick="this.nextElementSibling.classList.toggle('collapsed')">
        Failed / Error Cases <span style="font-size:12px;color:var(--muted)">{report.failed + report.errors} items</span>
    </div>
    <div class="section-body">
        {_failure_detail()}
    </div>
</div>

<!-- All Results -->
<div class="section">
    <div class="section-title" onclick="this.nextElementSibling.classList.toggle('collapsed')">
        All Results <span style="font-size:12px;color:var(--muted)">{report.total_cases} cases</span>
    </div>
    <div class="section-body">
        <div class="search-bar">
            <input type="text" id="searchInput" placeholder="Search by name, method, path, or category..." oninput="filterResults()">
        </div>
        <table id="resultsTable">
            <thead><tr><th>#</th><th>Case</th><th>Category</th><th>Method</th><th>Path</th><th>Status</th><th>Time</th><th>Result</th></tr></thead>
            <tbody>{_result_rows()}</tbody>
        </table>
    </div>
</div>

<div class="footer">API Test Agent &mdash; Generated at {report.generated_at}</div>

</div>

<script>
function filterResults() {{
    const q = document.getElementById('searchInput').value.toLowerCase();
    const rows = document.querySelectorAll('#resultsTable tbody tr');
    rows.forEach(r => {{
        const text = r.textContent.toLowerCase();
        r.style.display = text.includes(q) ? '' : 'none';
    }});
}}
</script>

</body>
</html>"""


# 工具定义
REPORT_GEN_SCHEMA = {
    "type": "function",
    "function": {
        "name": "generate_report",
        "description": "将测试结果汇总生成 Markdown/HTML/JSON 格式的测试报告并保存到文件。",
        "parameters": {
            "type": "object",
            "properties": {
                "api_name": {
                    "type": "string",
                    "description": "被测 API 名称",
                },
                "base_url": {
                    "type": "string",
                    "description": "API 基础 URL",
                },
                "spec_url": {
                    "type": "string",
                    "description": "OpenAPI Spec 的来源 URL",
                },
                "results_json": {
                    "type": "string",
                    "description": "测试结果的 JSON 字符串（TestCaseResult 数组）",
                },
                "duration_seconds": {
                    "type": "number",
                    "description": "测试执行总耗时（秒）",
                },
            },
            "required": ["api_name", "base_url", "results_json", "duration_seconds"],
        },
    },
}
