import pytest
from sqlalchemy import select

from app.models.post import Post


@pytest.mark.asyncio
async def test_create_post_persists_generated_embedding(
    client, auth_headers, test_category, db_session, monkeypatch,
):
    vector = [0.01] * 512

    async def fake_generate(title, content):
        assert title == "向量创建测试"
        return vector

    monkeypatch.setattr("app.api.posts.generate_post_embedding", fake_generate)
    response = await client.post(
        "/api/v1/posts",
        json={
            "title": "向量创建测试",
            "content": "创建帖子时应生成三百八十四维向量",
            "category_id": test_category["id"],
        },
        headers=auth_headers,
    )

    assert response.status_code == 201, response.text
    post = (await db_session.execute(select(Post).where(Post.id == response.json()["id"]))).scalar_one()
    assert list(post.embedding) == pytest.approx(vector)


@pytest.mark.asyncio
async def test_update_content_refreshes_embedding(
    client, auth_headers, test_post, db_session, monkeypatch,
):
    vector = [0.02] * 512
    calls = []

    async def fake_generate(title, content):
        calls.append((title, content))
        return vector

    monkeypatch.setattr("app.api.posts.generate_post_embedding", fake_generate)
    response = await client.put(
        f"/api/v1/posts/{test_post['id']}",
        json={"content": "更新正文后必须重新生成帖子语义向量"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    post = (await db_session.execute(select(Post).where(Post.id == test_post["id"]))).scalar_one()
    assert calls == [(test_post["title"], "更新正文后必须重新生成帖子语义向量")]
    assert list(post.embedding) == pytest.approx(vector)


@pytest.mark.asyncio
async def test_embedding_failure_does_not_block_post_creation(
    client, auth_headers, test_category, db_session, monkeypatch,
):
    async def fake_generate(title, content):
        return None

    monkeypatch.setattr("app.api.posts.generate_post_embedding", fake_generate)
    response = await client.post(
        "/api/v1/posts",
        json={
            "title": "降级创建测试",
            "content": "外部向量服务失败时帖子仍然应该正常创建",
            "category_id": test_category["id"],
        },
        headers=auth_headers,
    )

    assert response.status_code == 201, response.text
    post = (await db_session.execute(select(Post).where(Post.id == response.json()["id"]))).scalar_one()
    assert post.embedding is None


@pytest.mark.asyncio
async def test_embedding_failure_on_update_preserves_previous_vector(
    client, auth_headers, test_post, db_session, monkeypatch,
):
    previous = [0.03] * 512
    post = (await db_session.execute(
        select(Post).where(Post.id == test_post["id"])
    )).scalar_one()
    post.embedding = previous
    await db_session.commit()

    async def fake_generate(title, content):
        return None

    monkeypatch.setattr("app.api.posts.generate_post_embedding", fake_generate)
    response = await client.put(
        f"/api/v1/posts/{test_post['id']}",
        json={"content": "向量服务失败时保留旧向量，避免破坏已有检索能力"},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    db_session.expunge_all()
    post = (await db_session.execute(
        select(Post).where(Post.id == test_post["id"])
    )).scalar_one()
    assert list(post.embedding) == pytest.approx(previous)
