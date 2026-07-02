"""
API Test Agent — Streamlit Dashboard

启动:
    streamlit run frontend/app.py

模式:
    - 在线模式: 连接 FastAPI 后端，启动测试 + 查看历史 + SSE 进度
    - 离线模式: 直接读取 reports/*.json 文件，无需后端运行
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# Plotly (keep optional — 离线模式不需要)
try:
    import plotly.express as px
    import plotly.graph_objects as go

    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False

# === Page Config ===
st.set_page_config(
    page_title="API Test Agent",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

PROJECT_ROOT = Path(__file__).parent.parent.resolve()
REPORTS_DIR = PROJECT_ROOT / "reports"


# ==================================================================
# Helpers
# ==================================================================

def load_local_reports() -> list[dict]:
    """Scan reports/ dir for JSON files, return list sorted by time desc."""
    if not REPORTS_DIR.exists():
        return []
    reports = []
    for f in sorted(REPORTS_DIR.glob("report_*.json"), key=os.path.getmtime, reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_file"] = str(f.name)
            data["_mtime"] = os.path.getmtime(f)
            reports.append(data)
        except Exception:
            continue
    return reports


def _fail_reason(result: dict) -> str:
    """Extract a concise failure reason from a test result."""
    for c in result.get("checks", []):
        if not c.get("passed"):
            detail = c.get("detail", "")
            # 简化中文乱码问题 — 提取关键信息
            if "状态码" in detail or "status" in detail.lower():
                parts = detail.split("(")
                return parts[0].strip() if parts else detail[:50]
            return detail[:60]
    err = result.get("error")
    if err:
        return str(err)[:60]
    return "验证失败"


def render_summary_cards(run: dict):
    """Render 5 summary metric cards."""
    cols = st.columns(5)
    cols[0].metric("Total Cases", run.get("total_cases", run.get("summary", {}).get("total", 0)))
    cols[1].metric("✅ Passed", run.get("passed", run.get("summary", {}).get("passed", 0)))
    cols[2].metric("❌ Failed", run.get("failed", run.get("summary", {}).get("failed", 0)))
    cols[3].metric("⚠️ Errors", run.get("errors", run.get("summary", {}).get("errors", 0)))
    rate = run.get("pass_rate", run.get("summary", {}).get("pass_rate", 0))
    cols[4].metric("📈 Pass Rate", f"{rate:.1%}")


def normalize_results(raw_results: list[dict]) -> pd.DataFrame:
    """Normalize results list to DataFrame with consistent columns."""
    rows = []
    for i, r in enumerate(raw_results, 1):
        rows.append({
            "#": i,
            "Case": r.get("case_name", r.get("name", "?"))[:55],
            "Category": r.get("category", "?"),
            "Method": r.get("method", "?"),
            "Path": r.get("path", "?")[:40],
            "Status": r.get("status_code", 0),
            "Time": f"{r.get('elapsed_ms', 0):.0f}ms",
            "Result": "✅" if r.get("passed") else ("⚠️" if r.get("error") else "❌"),
            "_passed": r.get("passed", False),
            "_error": r.get("error"),
            "_checks": r.get("checks", []),
            "_response": r.get("response_preview", "") or "",
        })
    return pd.DataFrame(rows)


# ==================================================================
# Sidebar
# ==================================================================

with st.sidebar:
    st.title("🧪 API Test Agent")
    st.markdown("**LangGraph + DeepSeek**  API 自动化测试")
    st.divider()

    # ── Mode ──
    st.markdown("### 📡 数据源")
    mode = st.radio("选择模式", ["🌐 在线 (FastAPI 后端)", "📁 离线 (本地报告文件)"],
                     help="在线: 连接后端启动测试 / 离线: 直接读取 reports/ 目录")

    online_mode = "在线" in mode

    if online_mode:
        backend_url = st.text_input("API Base URL", value="http://localhost:8002",
                                    help="api-test-agent 的 FastAPI 后端地址")

        if st.button("🔗 测试连接"):
            try:
                resp = requests.get(f"{backend_url}/api/health", timeout=5)
                if resp.status_code == 200:
                    st.success(f"✅ 已连接 | Model: {resp.json().get('model', '?')}")
                else:
                    st.error(f"状态码: {resp.status_code}")
            except Exception as e:
                st.error(f"连接失败: {e}")

        st.divider()
        st.markdown("### ⚙️ 认证配置")
        auth_type = st.selectbox("认证方式", ["无", "Bearer Token", "API Key", "Basic Auth"])
        auth_token = st.text_input("Token/Key", type="password") if auth_type in ("Bearer Token", "API Key") else None
        auth_username = st.text_input("用户名") if auth_type == "Basic Auth" else None
        auth_password = st.text_input("密码", type="password") if auth_type == "Basic Auth" else None

    else:
        # 离线模式 — 列出本地报告
        local_reports = load_local_reports()
        if not local_reports:
            st.warning("reports/ 目录下暂无 JSON 报告文件")

        st.divider()
        st.caption(f"报告目录: {REPORTS_DIR}")


# ==================================================================
# Tabs
# ==================================================================

if online_mode:
    tab1, tab2, tab3 = st.tabs(["🚀 启动测试", "📊 测试历史", "📋 结果详情"])
else:
    tab1, tab2 = st.tabs(["📊 报告浏览", "📋 结果详情"])
    tab3 = None  # 离线模式无独立详情 tab


# ════════════════════════════════════════════════════════════════
# Tab 1 — 启动测试 (在线) / 报告浏览 (离线)
# ════════════════════════════════════════════════════════════════

with tab1:
    if online_mode:
        st.markdown("## 🚀 启动 API 自动化测试")

        col1, col2 = st.columns([3, 1])
        with col1:
            spec_url = st.text_input(
                "OpenAPI Spec URL",
                value="https://petstore3.swagger.io/api/v3/openapi.json",
                placeholder="输入 OpenAPI JSON/YAML URL",
                key="spec_url",
            )
        with col2:
            st.markdown("### 快速填充")
            if st.button("🐶 Petstore API"):
                st.session_state.spec_url = "https://petstore3.swagger.io/api/v3/openapi.json"
                st.rerun()
            if st.button("🏠 Localhost:8000"):
                st.session_state.spec_url = "http://localhost:8000/openapi.json"
                st.rerun()

        st.divider()

        if st.button("▶️ 开始测试", type="primary", use_container_width=True):
            if not spec_url:
                st.warning("请输入 API 文档 URL")
            else:
                auth_config = {}
                if auth_type == "Bearer Token" and auth_token:
                    auth_config = {"type": "bearer", "token": auth_token}
                elif auth_type == "API Key" and auth_token:
                    auth_config = {"type": "api_key", "key": auth_token}
                elif auth_type == "Basic Auth" and auth_username:
                    auth_config = {"type": "basic", "username": auth_username, "password": auth_password}

                with st.spinner("启动中..."):
                    try:
                        resp = requests.post(
                            f"{backend_url}/api/test/run",
                            json={
                                "spec_url": spec_url,
                                "auth_type": auth_config.get("type"),
                                "auth_token": auth_config.get("token") or auth_config.get("key"),
                                "auth_username": auth_config.get("username"),
                                "auth_password": auth_config.get("password"),
                            },
                            timeout=10,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            st.success(f"✅ 已启动！Run ID: `{data['run_id']}`")
                            st.session_state.last_run_id = data["run_id"]
                            st.session_state.completed_run = None  # 清除上次结果
                            # SSE 进度流
                            with st.expander("📡 实时进度 (SSE)", expanded=True):
                                sse_placeholder = st.empty()
                                try:
                                    sse_resp = requests.get(
                                        f"{backend_url}/api/test/stream/{data['run_id']}",
                                        stream=True, timeout=120,
                                    )
                                    for line in sse_resp.iter_lines(decode_unicode=True):
                                        if line and line.startswith("data:"):
                                            payload = line[5:].strip()
                                            if payload:
                                                try:
                                                    evt = json.loads(payload)
                                                    evt_type = evt.get("event", "")
                                                    evt_data = evt.get("data", {})
                                                    if evt_type == "progress":
                                                        node = evt_data.get("node", "?")
                                                        pct = evt_data.get("progress", 0)
                                                        msg = evt_data.get("message", "")
                                                        sse_placeholder.info(f"[{node}] {pct:.0%} — {msg}")
                                                    elif evt_type == "completed":
                                                        pass_rate = evt_data.get("pass_rate", 0)
                                                        passed = evt_data.get("passed", 0)
                                                        total = evt_data.get("total", 0)
                                                        failed = evt_data.get("failed", 0)
                                                        errors = evt_data.get("errors", 0)
                                                        report_path = evt_data.get("report_path", "")
                                                        sse_placeholder.success(
                                                            f"✅ 测试完成！通过率 {pass_rate:.1f}% "
                                                            f"({passed} passed / {failed} failed / {errors} errors)"
                                                        )
                                                        # 存到 session state 供后续 Tab 使用
                                                        st.session_state.completed_run = {
                                                            "run_id": data["run_id"],
                                                            "pass_rate": pass_rate,
                                                            "passed": passed,
                                                            "failed": failed,
                                                            "errors": errors,
                                                            "total": total,
                                                            "report_path": report_path,
                                                        }
                                                        break
                                                    elif evt_type == "error":
                                                        err_msg = evt_data.get("message", evt_data) if isinstance(evt_data, dict) else str(evt_data)
                                                        sse_placeholder.error(f"❌ {err_msg}")
                                                        break
                                                except Exception:
                                                    pass
                                except Exception:
                                    sse_placeholder.warning("SSE 连接中断（测试可能仍在进行）")
                        else:
                            st.error(f"启动失败: {resp.text}")
                    except Exception as e:
                        st.error(f"请求失败: {e}")

            # 持久化显示最近完成的测试（跨 rerun 保持可见）
            if st.session_state.get("completed_run"):
                cr = st.session_state.completed_run
                col_info, col_clear = st.columns([4, 1])
                with col_info:
                    st.success(
                        f"✅ 测试完成！通过率 **{cr['pass_rate']:.1f}%** "
                        f"({cr['passed']} passed / {cr['failed']} failed / {cr['errors']} errors) "
                        f"| Run: `{cr['run_id']}`"
                    )
                with col_clear:
                    if st.button("🧹 清除", key="clear_completed"):
                        st.session_state.completed_run = None
                        st.rerun()

                # ── 从后端拉取详细结果 ──
                try:
                    detail_resp = requests.get(
                        f"{backend_url}/api/test/results/{cr['run_id']}", timeout=5
                    )
                    if detail_resp.status_code == 200:
                        detail_data = detail_resp.json()
                        results = detail_data.get("results", [])
                    else:
                        results = []
                except Exception:
                    results = []

                # ── 内联展示失败用例 ──
                if results:
                    failures = [r for r in results if not r.get("passed")]
                    if failures:
                        st.markdown(f"##### ❌ 失败用例 ({len(failures)})")
                        fail_rows = []
                        for i, f in enumerate(failures, 1):
                            fail_rows.append({
                                "#": i,
                                "用例": f.get("case_name", f.get("name", "?"))[:60],
                                "类别": f.get("category", "?"),
                                "方法": f.get("method", "?"),
                                "路径": f.get("path", "?")[:40],
                                "状态码": f.get("status_code", "?"),
                                "失败原因": _fail_reason(f),
                            })
                        st.dataframe(
                            pd.DataFrame(fail_rows),
                            use_container_width=True, hide_index=True,
                            height=min(35 * len(failures) + 38, 300),
                        )
                    else:
                        st.success("🎉 全部用例通过！")

                # ── 报告下载按钮 ──
                report_path = cr.get("report_path", "")
                if report_path:
                    st.markdown("##### 📥 下载报告")
                    import os as _os
                    dl_cols = st.columns(3)
                    report_prefix = report_path.replace(".md", "")
                    for i, (label, ext, mime) in enumerate([
                        ("🌐 HTML 报告", ".html", "text/html"),
                        ("📝 Markdown", ".md", "text/markdown"),
                        ("📊 JSON 数据", ".json", "application/json"),
                    ]):
                        fp = report_prefix + ext
                        if _os.path.exists(fp):
                            with dl_cols[i]:
                                with open(fp, "r", encoding="utf-8") as fh:
                                    st.download_button(
                                        label, fh.read(),
                                        file_name=f"report_{cr['run_id']}{ext}",
                                        mime=mime, use_container_width=True,
                                        key=f"dl_{ext}_{cr['run_id']}",
                                    )

                # 提示切 tab
                st.caption("💡 切换到「📊 测试历史」或「📋 结果详情」标签页查看完整数据")

    else:
        # ── 离线模式: 报告浏览 ──
        st.markdown("## 📊 本地报告浏览")

        local_reports = load_local_reports()
        if not local_reports:
            st.info("reports/ 目录下暂无 JSON 报告。运行一次 E2E 测试后可在此查看。")
        else:
            # 多报告对比选择
            selected_indices = []
            report_options = [
                f"{r.get('api_name','?')} | {r.get('generated_at','?')[:19]} | "
                f"通过率 {r.get('summary',{}).get('pass_rate',0):.1%} | "
                f"({r.get('summary',{}).get('total',0)} cases) | "
                f"{r['_file']}"
                for r in local_reports
            ]

            # 默认选最新
            default_idx = 0

            st.markdown("### 选择报告")
            selected_idx = st.selectbox(
                "报告列表（按时间倒序）",
                range(len(local_reports)),
                format_func=lambda i: report_options[i],
                index=default_idx,
            )

            report = local_reports[selected_idx]
            summary = report.get("summary", {})
            results = report.get("results", [])

            # 摘要卡片
            st.markdown("### 📊 测试概要")
            render_summary_cards({
                "total_cases": summary.get("total", 0),
                "passed": summary.get("passed", 0),
                "failed": summary.get("failed", 0),
                "errors": summary.get("errors", 0),
                "pass_rate": summary.get("pass_rate", 0),
            })

            # 图表区
            if HAS_PLOTLY:
                chart_col1, chart_col2 = st.columns(2)

                with chart_col1:
                    # Pie: pass/fail/error
                    pie_data = pd.DataFrame({
                        "Status": ["Passed", "Failed", "Errors"],
                        "Count": [summary.get("passed", 0), summary.get("failed", 0), summary.get("errors", 0)],
                    })
                    pie_data = pie_data[pie_data["Count"] > 0]
                    fig_pie = px.pie(pie_data, values="Count", names="Status",
                                     color="Status",
                                     color_discrete_map={"Passed": "#22c55e", "Failed": "#ef4444", "Errors": "#f59e0b"},
                                     title="Test Result Distribution")
                    fig_pie.update_traces(textinfo="value+percent")
                    st.plotly_chart(fig_pie, use_container_width=True)

                with chart_col2:
                    # Bar: by category
                    by_cat = report.get("by_category", {})
                    if by_cat:
                        cat_data = pd.DataFrame([
                            {"Category": cat, "Passed": s["passed"], "Failed": s["failed"], "Errors": s["errors"]}
                            for cat, s in sorted(by_cat.items())
                        ])
                        fig_bar = px.bar(cat_data, x="Category",
                                         y=["Passed", "Failed", "Errors"],
                                         title="Results by Category",
                                         color_discrete_map={"Passed": "#22c55e", "Failed": "#ef4444", "Errors": "#f59e0b"},
                                         barmode="stack")
                        st.plotly_chart(fig_bar, use_container_width=True)

                # Bar: by endpoint (top 15)
                by_ep = report.get("by_endpoint", {})
                if by_ep:
                    ep_data = pd.DataFrame([
                        {"Endpoint": ep[:50], "Passed": s["passed"], "Failed": s["failed"], "Errors": s["errors"]}
                        for ep, s in sorted(by_ep.items(), key=lambda x: -x[1]["total"])[:15]
                    ])
                    fig_ep = px.bar(ep_data, y="Endpoint",
                                    x=["Passed", "Failed", "Errors"],
                                    title="Results by Endpoint (Top 15)",
                                    color_discrete_map={"Passed": "#22c55e", "Failed": "#ef4444", "Errors": "#f59e0b"},
                                    barmode="stack", orientation="h",
                                    height=max(400, len(ep_data) * 22))
                    st.plotly_chart(fig_ep, use_container_width=True)

            # 失败用例
            failures = [r for r in results if not r.get("passed")]
            if failures:
                st.markdown(f"### ❌ 失败/错误用例 ({len(failures)})")
                for f in failures:
                    icon = "⚠️" if f.get("error") else "❌"
                    with st.expander(f"{icon} [{f.get('category','?')}] {f.get('name', f.get('case_name','?'))[:70]}"):
                        st.markdown(f"""
                        - **Method/Path**: `{f.get('method','?')} {f.get('path','?')}`
                        - **Status Code**: {f.get('status_code','?')}
                        - **Error**: {f.get('error') or 'Validation failed'}
                        """)
                        if f.get("response_preview"):
                            st.caption("Response preview:")
                            st.code(f["response_preview"][:500], language="json")

            # 完整结果表
            st.markdown(f"### 📋 全部结果 ({len(results)} cases)")
            if results:
                df = normalize_results(results)
                # Filter
                cat_filter = st.multiselect(
                    "按类别筛选", options=sorted(df["Category"].unique()),
                    key="offline_cat_filter"
                )
                if cat_filter:
                    df = df[df["Category"].isin(cat_filter)]
                st.dataframe(
                    df.drop(columns=["_passed", "_error", "_checks", "_response"]),
                    use_container_width=True,
                    height=400,
                    hide_index=True,
                )

            # 下载
            st.markdown("### 📥 报告文件")
            dl_col1, dl_col2, dl_col3 = st.columns(3)
            report_prefix = report.get("_file", "").replace(".json", "")
            with dl_col1:
                md_file = REPORTS_DIR / f"{report_prefix}.md"
                if md_file.exists():
                    st.download_button("📝 Markdown", md_file.read_text(encoding="utf-8"),
                                       file_name=f"{report_prefix}.md", mime="text/markdown")
            with dl_col2:
                html_file = REPORTS_DIR / f"{report_prefix}.html"
                if html_file.exists():
                    st.download_button("🌐 HTML", html_file.read_text(encoding="utf-8"),
                                       file_name=f"{report_prefix}.html", mime="text/html")
            with dl_col3:
                json_file = REPORTS_DIR / f"{report_prefix}.json"
                if json_file.exists():
                    st.download_button("📊 JSON", json_file.read_text(encoding="utf-8"),
                                       file_name=f"{report_prefix}.json", mime="application/json")


# ════════════════════════════════════════════════════════════════
# Tab 2 — 测试历史 (在线) / 报告详情 (离线)
# ════════════════════════════════════════════════════════════════

with tab2:
    if online_mode:
        st.markdown("## 📊 测试历史")

        col_refresh, col_empty = st.columns([1, 5])
        with col_refresh:
            if st.button("🔄 刷新", key="refresh_history"):
                st.rerun()

        try:
            resp = requests.get(f"{backend_url}/api/test/history?limit=50", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                runs = data.get("runs", [])

                if not runs:
                    st.info("暂无测试记录")
                else:
                    completed = [r for r in runs if r.get("status") == "completed"]
                    running = [r for r in runs if r.get("status") == "running"]

                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("总测试次数", len(runs))
                    col2.metric("已完成", len(completed))
                    col3.metric("运行中", len(running))
                    col4.metric("平均通过率",
                                f"{sum(r.get('pass_rate',0) for r in completed)/max(len(completed),1):.1%}"
                                if completed else "N/A")

                    if completed and HAS_PLOTLY:
                        df_trend = pd.DataFrame([
                            {"id": r["id"][:8], "pass_rate": r.get("pass_rate", 0) * 100,
                             "api": r.get("api_name", "")}
                            for r in completed[-10:]
                        ])
                        fig = px.bar(df_trend, x="id", y="pass_rate",
                                     title="Recent Pass Rate Trend (%)",
                                     labels={"id": "Run", "pass_rate": "Pass Rate (%)"},
                                     text_auto=".1f")
                        fig.add_hline(y=95, line_dash="dash", line_color="green",
                                      annotation_text="95% baseline")
                        st.plotly_chart(fig, use_container_width=True)

                    st.markdown("### 📜 历史列表")
                    for run in reversed(runs[:20]):
                        status_icon = {"completed": "✅", "running": "⏳", "error": "❌"}.get(run.get("status"), "❓")
                        with st.expander(
                            f"{status_icon} [{run['id'][:8]}] {run.get('api_name','?')} — "
                            f"{run.get('pass_rate',0):.1%} ({run.get('passed',0)}/{run.get('total_cases',0)})"
                        ):
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.markdown(f"""
                                - **Run ID**: `{run['id']}`
                                - **Status**: {run.get('status')}
                                - **Spec**: {run.get('spec_url','?')}
                                - **Started**: {run.get('started_at','?')}
                                """)
                            with col_b:
                                st.markdown(f"""
                                - **Total**: {run.get('total_cases',0)}
                                - **Passed**: {run.get('passed',0)} ✅
                                - **Failed**: {run.get('failed',0)} ❌
                                - **Errors**: {run.get('errors',0)} ⚠️
                                """)
                            if st.button("📋 查看详情", key=f"detail_{run['id']}"):
                                st.session_state.detail_run_id = run["id"]
        except Exception as e:
            st.error(f"加载失败: {e}")

    else:
        # 离线模式 Tab 2 — 单报告详情
        local_reports = load_local_reports()
        if not local_reports:
            st.info("暂无报告")
        else:
            report_options = [
                f"{r.get('api_name','?')} | {r.get('generated_at','?')[:19]} | "
                f"通过率 {r.get('summary',{}).get('pass_rate',0):.1%} | {r['_file']}"
                for r in local_reports
            ]

            selected_idx = st.selectbox(
                "选择要查看的报告",
                range(len(local_reports)),
                format_func=lambda i: report_options[i],
                key="detail_report_select",
            )

            report = local_reports[selected_idx]
            summary = report.get("summary", {})
            results = report.get("results", [])

            st.markdown(f"### 📋 报告详情 — `{report['_file']}`")
            render_summary_cards({
                "total_cases": summary.get("total", 0),
                "passed": summary.get("passed", 0),
                "failed": summary.get("failed", 0),
                "errors": summary.get("errors", 0),
                "pass_rate": summary.get("pass_rate", 0),
            })

            st.markdown(f"""
            - **API**: {report.get('api_name','?')}
            - **Base URL**: {report.get('base_url','?')}
            - **Spec**: {report.get('spec_url','?')}
            - **Generated**: {report.get('generated_at','?')}
            - **Report ID**: {report.get('report_id','?')}
            """)

            # 失败用例
            failures = [r for r in results if not r.get("passed")]
            if failures:
                st.markdown(f"### ❌ 失败/错误用例 ({len(failures)})")
                for f in failures:
                    icon = "⚠️" if f.get("error") else "❌"
                    with st.expander(f"{icon} [{f.get('category','?')}] {f.get('name', f.get('case_name','?'))[:70]}"):
                        st.json({
                            "method": f.get("method"),
                            "path": f.get("path"),
                            "status_code": f.get("status_code"),
                            "category": f.get("category"),
                            "error": f.get("error"),
                            "checks": f.get("checks", []),
                            "response": (f.get("response_preview", "") or "")[:500],
                        })

            # 全部结果
            if results:
                st.markdown(f"### 📋 All Results ({len(results)} cases)")
                df = normalize_results(results)
                cat_filter = st.multiselect(
                    "按类别筛选", options=sorted(df["Category"].unique()),
                    key="detail_cat_filter"
                )
                result_filter = st.radio("结果筛选", ["All", "Passed", "Failed/Error"],
                                         horizontal=True, key="detail_result_filter")
                if cat_filter:
                    df = df[df["Category"].isin(cat_filter)]
                if result_filter == "Passed":
                    df = df[df["_passed"]]
                elif result_filter == "Failed/Error":
                    df = df[~df["_passed"]]

                st.dataframe(
                    df.drop(columns=["_passed", "_error", "_checks", "_response"]),
                    use_container_width=True, height=500, hide_index=True,
                )


# ════════════════════════════════════════════════════════════════
# Tab 3 — 结果详情 (仅在线模式)
# ════════════════════════════════════════════════════════════════

if online_mode and tab3:
    with tab3:
        st.markdown("## 📋 测试结果详情")

        run_id = st.text_input(
            "Run ID",
            value=st.session_state.get("detail_run_id", st.session_state.get("last_run_id", "")),
            placeholder="输入 Run ID 查看详情",
        )

        if run_id and st.button("🔍 加载结果"):
            try:
                resp = requests.get(f"{backend_url}/api/test/results/{run_id}", timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    run = data.get("run", {})
                    results = data.get("results", [])
                    categories = data.get("categories", [])

                    st.markdown("### 📊 测试概要")
                    render_summary_cards(run)

                    if categories and HAS_PLOTLY:
                        st.markdown("### 📂 类别分布")
                        df_cat = pd.DataFrame(categories)
                        fig = px.sunburst(
                            df_cat, path=["category"], values="total",
                            color="failed", color_continuous_scale="RdYlGn_r",
                            title="Category Distribution (red = more failures)",
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    if results:
                        st.markdown(f"### 📋 全部结果 ({len(results)} cases)")
                        df = normalize_results(results)
                        st.dataframe(
                            df.drop(columns=["_passed", "_error", "_checks", "_response"]),
                            use_container_width=True, height=400, hide_index=True,
                        )

                        failures = [r for r in results if not r.get("passed")]
                        if failures:
                            st.markdown(f"### ❌ 失败/错误 ({len(failures)})")
                            for f in failures:
                                icon = "⚠️" if f.get("error") else "❌"
                                with st.expander(f"{icon} {f.get('case_name', f.get('name','?'))[:60]}"):
                                    st.json({
                                        "method": f.get("method"),
                                        "path": f.get("path"),
                                        "status_code": f.get("status_code"),
                                        "category": f.get("category"),
                                        "error": f.get("error"),
                                        "checks": f.get("checks", []),
                                        "response_preview": (f.get("response_preview", "") or "")[:500],
                                    })

                    # Download
                    st.markdown("### 📥 下载报告")
                    dl_cols = st.columns(3)
                    for fmt, col in zip(["md", "html", "json"], dl_cols):
                        with col:
                            label = {"md": "📝 Markdown", "html": "🌐 HTML", "json": "📊 JSON"}[fmt]
                            try:
                                report_resp = requests.get(
                                    f"{backend_url}/api/test/report/{run_id}?format={fmt}", timeout=5
                                )
                                if report_resp.status_code == 200:
                                    mime = {"md": "text/markdown", "html": "text/html", "json": "application/json"}[fmt]
                                    st.download_button(
                                        label, report_resp.content,
                                        file_name=f"report_{run_id}.{fmt}",
                                        mime=mime, use_container_width=True,
                                        key=f"detail_dl_{fmt}_{run_id}",
                                    )
                                else:
                                    st.caption(f"{label} (不可用)")
                            except Exception:
                                st.caption(f"{label} (获取失败)")
                else:
                    st.error(f"加载失败: {resp.status_code}")
            except Exception as e:
                st.error(f"请求失败: {e}")


# === Footer ===
st.divider()
st.caption(f"API Test Agent v0.1.0 | LangGraph + DeepSeek | {mode} | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
