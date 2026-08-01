import re
from pathlib import Path

import pytest
from sqlalchemy import text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
OPENGAUSS_DIR = BACKEND_ROOT / "scripts" / "opengauss"
ACTIVE_SQL_FILES = (
    "03_alter_tables.sql",
    "04_create_indexes.sql",
    "06_create_materialized_views.sql",
    "07_create_functions.sql",
    "08_create_triggers.sql",
    "09_create_partitions.sql",
    "10_init_data.sql",
    "11_grant_permissions.sql",
    "performance_test.sql",
)
TRANSACTION_SQL_FILES = ACTIVE_SQL_FILES[:5]
REMOVED_IDENTIFIERS = (
    "favorites",
    "favorite_count",
    "is_top",
    "pending_review",
    "rejected",
    "expiration_report",
    "conflict_report",
)


def _without_comments(sql: str) -> str:
    return re.sub(r"--.*?$|/\*.*?\*/", "", sql, flags=re.MULTILINE | re.DOTALL)


@pytest.mark.parametrize("filename", ACTIVE_SQL_FILES)
def test_active_opengauss_sql_has_no_removed_runtime_contract(filename: str):
    """当前可执行 SQL 不得继续依赖已删除字段、表、状态和旧三类验证。"""
    sql = _without_comments((OPENGAUSS_DIR / filename).read_text(encoding="utf-8"))
    lowered = sql.lower()

    for identifier in REMOVED_IDENTIFIERS:
        assert re.search(rf"\b{re.escape(identifier)}\b", lowered) is None, (
            f"{filename} 仍依赖已删除运行时标识 {identifier}"
        )

    assert re.search(r"validation_type\s*=\s*'update'", lowered) is None


def test_database_design_generator_matches_current_interaction_contract():
    """设计产物生成器只描述点赞和两类协同验证，不复活旧收藏/旧三类。"""
    source = (BACKEND_ROOT / "scripts" / "generate_db_design.py").read_text(
        encoding="utf-8"
    )
    lowered = source.lower()

    for identifier in ("favorites", "favorite_count", "is_top"):
        assert re.search(rf"\b{identifier}\b", lowered) is None
    for validation_type in ("update/", "expiration_report", "conflict_report", "含5类", "验证类型：5类"):
        assert validation_type not in lowered


def test_data_verifier_imports_only_current_models():
    """数据核验脚本不得导入已经删除的收藏模型。"""
    source = (BACKEND_ROOT / "scripts" / "verify_data.py").read_text(
        encoding="utf-8"
    )

    assert re.search(r"\bFavorite\b", source) is None


def test_full_report_generator_matches_current_interaction_contract():
    """全量报告生成器不得继续生成旧收藏或旧三类协同验证内容。"""
    source = (BACKEND_ROOT.parent / "scripts" / "generate_full_report.py").read_text(
        encoding="utf-8"
    )
    lowered = source.lower()

    for identifier in ("favorites", "favorite_count"):
        assert re.search(rf"\b{identifier}\b", lowered) is None
    for obsolete_text in (
        "收藏",
        "5类协同验证",
        "五类协同验证",
        "validation_type = 'update'",
        "v_update_cnt",
        "v_expire_cnt",
        "v_conflict_cnt",
        "expiration_report",
        "conflict_report",
        "补充更新",
        "favorite",
    ):
        assert obsolete_text not in lowered


def test_database_check_script_uses_current_key_tables():
    source = (BACKEND_ROOT / "scripts" / "_check_db.py").read_text(encoding="utf-8")

    assert "post_change_reports" not in source


def test_tablespace_script_describes_current_interaction_tables():
    source = (OPENGAUSS_DIR / "01_create_tablespaces.sql").read_text(encoding="utf-8")

    assert re.search(r"\bfavorites\b", source.lower()) is None


def test_category_index_keeps_tenant_scoped_uniqueness():
    """分类 code 只在学校内唯一，运维索引不得收紧成平台级唯一。"""
    sql = _without_comments(
        (OPENGAUSS_DIR / "04_create_indexes.sql").read_text(encoding="utf-8")
    ).lower()

    assert "unique index if not exists idx_category_code_uidx" not in sql
    assert re.search(
        r"unique\s+index\s+if\s+not\s+exists\s+idx_category_school_code\s+"
        r"on\s+categories\s*\(\s*school_id\s*,\s*code\s*\)",
        sql,
    )


@pytest.mark.asyncio
async def test_active_opengauss_sql_executes_in_one_rollback_transaction(
    opengauss_test_engine,
):
    """物理对象脚本必须能在独立测试库的单一事务内完整执行并回滚。"""
    async with opengauss_test_engine.connect() as conn:
        transaction = await conn.begin()
        try:
            raw = await conn.get_raw_connection()
            driver = raw.driver_connection
            for filename in TRANSACTION_SQL_FILES:
                sql = (OPENGAUSS_DIR / filename).read_text(encoding="utf-8")
                await driver.execute(sql)

            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM pg_proc "
                    "WHERE proname IN ('sp_recalc_credibility', 'sp_mark_expired_posts')"
                )
            )
            assert result.scalar_one() == 2
        finally:
            await transaction.rollback()
