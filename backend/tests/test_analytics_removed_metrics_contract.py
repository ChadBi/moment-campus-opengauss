"""运行时 analytics 契约清理回归测试。"""
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

RUNTIME_ANALYTICS_FILES = (
    PROJECT_ROOT / "backend/app/api/analytics.py",
    PROJECT_ROOT / "backend/app/services/analytics_service.py",
    PROJECT_ROOT / "frontend/src/services/analytics.ts",
    PROJECT_ROOT / "frontend/src/services/admin.ts",
    PROJECT_ROOT / "frontend/src/pages/admin/AnalyticsPage.tsx",
    PROJECT_ROOT / "frontend/src/pages/admin/PlatformOverviewPage.tsx",
)

REMOVED_RUNTIME_TERMS = (
    "open_change_reports",
    "avg_change_report_handle_seconds",
    "change_reports_handled_count",
    "post_change_reports",
    "问题报告",
)


def test_runtime_analytics_no_longer_references_removed_change_report_metrics():
    """后端契约、前端类型和分析页面不再暴露已删除的问题报告指标。"""
    violations = []
    for path in RUNTIME_ANALYTICS_FILES:
        content = path.read_text(encoding="utf-8")
        for term in REMOVED_RUNTIME_TERMS:
            if term in content:
                violations.append(f"{path.relative_to(PROJECT_ROOT)}: {term}")

    assert violations == [], "发现废弃运行时 analytics 契约：\n" + "\n".join(violations)


def test_report_metrics_keep_report_semantics():
    """清理问题报告指标时必须保留普通举报的字段和页面语义。"""
    service = (PROJECT_ROOT / "backend/app/services/analytics_service.py").read_text(
        encoding="utf-8"
    )
    analytics_types = (PROJECT_ROOT / "frontend/src/services/analytics.ts").read_text(
        encoding="utf-8"
    )
    analytics_page = (
        PROJECT_ROOT / "frontend/src/pages/admin/AnalyticsPage.tsx"
    ).read_text(encoding="utf-8")
    overview_page = (
        PROJECT_ROOT / "frontend/src/pages/admin/PlatformOverviewPage.tsx"
    ).read_text(encoding="utf-8")

    assert '"avg_report_handle_seconds"' in service
    assert '"reports_handled_count"' in service
    assert "avg_report_handle_seconds: number" in analytics_types
    assert "reports_handled_count: number" in analytics_types
    assert "平均举报处理时长" in analytics_page
    assert "举报创建 → 处理完成" in analytics_page
    assert "举报 ${data.pending_reports}" in overview_page
