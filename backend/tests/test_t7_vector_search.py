from datetime import datetime

import pytest
from sqlalchemy import text

from app.models.post import Post


def _post() -> Post:
    return Post(
        id=1,
        user_id=1,
        school_id=1,
        category_id=1,
        title="打印店位置",
        content="图书馆旁边可以打印资料",
        status="published",
        valid_count=5,
        created_at=datetime.now(),
    )


def test_hybrid_score_uses_weights():
    from app.services.ai_search import _compute_score

    score, reasons = _compute_score(
        _post(),
        keyword="打印",
        now=datetime.now(),
        semantic_similarity=0.8,
    )

    # 权重取自 ai_search._SCORE_WEIGHT_*：语义 0.50 + 新鲜度 0.15 + 验证 0.15 + 相关度 0.20
    # 0.50*0.8 + 0.15*1.0(今日) + 0.15*0.5(valid_count=5→0.5) + 0.20*1.0(标题命中) = 0.825
    assert score == pytest.approx(0.825, abs=0.001)
    assert any("语义" in reason for reason in reasons)


@pytest.mark.asyncio
async def test_post_embedding_column_is_vector_512_and_round_trips(db_session):
    column = Post.__table__.c.embedding
    assert column.type.get_col_spec() == "vector(512)"

    raw = (await db_session.execute(text(
        "SELECT CAST('[1,0,0]' AS vector(3)) <=> CAST('[1,0,0]' AS vector(3))"
    ))).scalar_one()
    assert float(raw) == pytest.approx(0.0)


def test_vector_migration_contains_reversible_hnsw_operations():
    from pathlib import Path

    migration = Path(__file__).parents[1] / "alembic" / "versions" / "b6c7d8e9f0a1_embedding_dim_512.py"
    content = migration.read_text(encoding="utf-8")
    assert "ALTER TABLE posts ALTER COLUMN embedding TYPE vector(512)" in content
    assert "USING hnsw (embedding vector_l2_ops)" in content
    assert "DROP INDEX IF EXISTS idx_posts_embedding_hnsw" in content
    assert "TYPE vector(384)" in content


def test_vector_candidates_are_ordered_by_native_distance_before_limit():
    from sqlalchemy import select
    from app.services.ai_search import _apply_vector_candidate_order

    statement = _apply_vector_candidate_order(
        select(Post),
        [0.0] * 512,
    ).limit(200)
    sql = str(statement.compile(compile_kwargs={"literal_binds": False}))

    assert "posts.embedding <=>" in sql
    assert "ORDER BY" in sql


@pytest.mark.asyncio
async def test_semantic_score_prefers_closer_vector(
    db_session, test_user, test_school, test_category,
):
    from app.services.ai_search import _load_semantic_scores
    from app.core.security import decode_token

    base = [0.0] * 512
    near = base.copy()
    near[0] = 1.0
    far = base.copy()
    far[1] = 1.0
    query = near.copy()

    posts = [
        Post(
            user_id=int(decode_token(test_user["access_token"])["sub"]),
            school_id=test_school["id"], category_id=test_category["id"],
            title="近向量", content="近向量正文", embedding=near,
        ),
        Post(
            user_id=int(decode_token(test_user["access_token"])["sub"]),
            school_id=test_school["id"], category_id=test_category["id"],
            title="远向量", content="远向量正文", embedding=far,
        ),
    ]
    db_session.add_all(posts)
    await db_session.flush()

    scores = await _load_semantic_scores(db_session, posts, query)

    assert scores[posts[0].id] > scores[posts[1].id]


@pytest.mark.asyncio
async def test_vector_candidates_never_cross_tenant_boundary(
    db_session, test_user, test_school, test_category,
):
    from app.core.security import decode_token
    from app.core.tenant import TenantContext
    from app.models.school import School
    from app.schemas.search import AISearchIntent, AISearchIntentFilters
    from app.services.ai_search import _query_posts

    other_school = School(name="隔离测试大学", code="isolated-uni", is_active=True)
    db_session.add(other_school)
    await db_session.flush()
    user_id = int(decode_token(test_user["access_token"])["sub"])
    own = Post(
        user_id=user_id, school_id=test_school["id"], category_id=test_category["id"],
        title="本校打印店", content="本校内容", status="published", embedding=[0.1] * 512,
    )
    foreign = Post(
        user_id=user_id, school_id=other_school.id, category_id=test_category["id"],
        title="外校打印店", content="外校内容", status="published", embedding=[0.1] * 512,
    )
    db_session.add_all([own, foreign])
    await db_session.flush()

    tenant = TenantContext(
        school_id=test_school["id"], school_code=test_school["code"],
        user=None, effective_role="guest", is_guest=True,
    )
    intent = AISearchIntent(
        intent="打印",
        filters=AISearchIntentFilters(keyword="打印", sort="relevance"),
        reasons=[],
    )
    posts = await _query_posts(db_session, tenant, intent, None, [0.1] * 512)

    assert [post.id for post in posts] == [own.id]
