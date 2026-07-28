"""DSC-02.1: 帖子详情页全字段展示 + 权限脱敏 + 回复树 测试

覆盖：
1. 详情展示所有字段：图片 / 状态 / 有效期 / 活动时间 / 联系方式 / 验证 / 回复树
2. 游客访问详情时不请求需登录的统计接口（is_liked 恒 False，user_validation_type 恒 None）
3. 联系方式等敏感字段按权限显示：游客返回 None，登录用户可见
4. governance 聚合 user_validation_type：登录用户返回其投票类型，游客恒 None
5. 评论按回复树展示（顶级 + 嵌套回复，含 reply_to_user）
"""
import pytest
from datetime import datetime, timedelta
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.post_status import PostStatus
from app.models.post import Post
from app.models.post_image import PostImage
from app.models.comment import Comment
from app.models.validation_record import ValidationRecord


# ============================================================
# 辅助：直接在 DB 创建 published 帖子（游客可见）
# ============================================================
async def _create_published_post(
    db_session: AsyncSession,
    user_id: int,
    school_id: int,
    category_id: int,
    *,
    title: str = "DSC-02 测试帖子",
    content: str = "这是 DSC-02.1 详情字段测试帖子的内容，至少十个字符",
    contact_info: str | None = "13800000000",
    expire_at: datetime | None = None,
    activity_start_at: datetime | None = None,
    activity_end_at: datetime | None = None,
) -> Post:
    """直接在 DB 创建 published 状态帖子（绕过状态机，仅用于测试展示）"""
    post = Post(
        user_id=user_id,
        school_id=school_id,
        category_id=category_id,
        title=title,
        content=content,
        status=PostStatus.PUBLISHED,
        contact_info=contact_info,
        expire_at=expire_at,
        activity_start_at=activity_start_at,
        activity_end_at=activity_end_at,
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)
    return post


async def _add_post_images(
    db_session: AsyncSession, post_id: int, urls: list[str]
) -> list[PostImage]:
    """为帖子附加图片"""
    images = []
    for idx, url in enumerate(urls):
        img = PostImage(post_id=post_id, image_url=url, sort_order=idx)
        db_session.add(img)
        images.append(img)
    await db_session.commit()
    for img in images:
        await db_session.refresh(img)
    return images


# ============================================================
# DSC-02.1: 详情页全字段展示（图片/状态/有效期/活动时间/联系方式）
# ============================================================

@pytest.mark.asyncio
async def test_detail_returns_all_fields_for_logged_in_user(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict,
):
    """DSC-02.1: 登录用户访问详情返回所有字段（含图片/状态/有效期/活动时间/联系方式）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    expire = datetime.now() + timedelta(days=7)
    start = datetime.now() + timedelta(days=1)
    end = datetime.now() + timedelta(days=2)
    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="test@example.com",
        expire_at=expire,
        activity_start_at=start,
        activity_end_at=end,
    )
    await _add_post_images(db_session, post.id, [
        "https://example.com/img1.jpg",
        "https://example.com/img2.jpg",
    ])

    # 登录用户访问
    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"Authorization": f"Bearer {test_user['access_token']}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 全字段校验
    assert data["id"] == post.id
    assert data["status"] == PostStatus.PUBLISHED
    assert data["contact_info"] == "test@example.com"  # 登录用户可见
    assert data["expire_at"] is not None
    assert data["activity_start_at"] is not None
    assert data["activity_end_at"] is not None
    # 图片列表
    assert data["images"] is not None
    assert len(data["images"]) == 2
    assert data["images"][0]["image_url"] == "https://example.com/img1.jpg"
    # governance 聚合字段存在
    assert "governance" in data
    assert data["governance"] is not None


@pytest.mark.asyncio
async def test_detail_returns_all_fields_for_guest_except_contact(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict,
):
    """DSC-02.1: 游客访问详情返回所有公开字段，但 contact_info 为 None"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    expire = datetime.now() + timedelta(days=7)
    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="13800000000",
        expire_at=expire,
    )
    await _add_post_images(db_session, post.id, ["https://example.com/guest.jpg"])

    # 游客访问（必须显式提供 X-School-Code）
    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == post.id
    assert data["status"] == PostStatus.PUBLISHED
    # 游客不可见联系方式
    assert data["contact_info"] is None
    # 游客可见其他公开字段
    assert data["expire_at"] is not None
    assert data["images"] is not None
    assert len(data["images"]) == 1
    # governance 聚合字段存在
    assert data["governance"] is not None


# ============================================================
# DSC-02.1: 联系方式按权限脱敏（游客 None，登录用户可见）
# ============================================================

@pytest.mark.asyncio
async def test_guest_contact_info_is_none(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict,
):
    """DSC-02.1: 游客访问详情，contact_info 恒为 None（敏感字段脱敏）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="secret-contact-12345",
    )

    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200
    assert resp.json()["contact_info"] is None


@pytest.mark.asyncio
async def test_logged_in_user_contact_info_visible(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    second_auth_headers: dict, test_school: dict, test_category: dict,
):
    """DSC-02.1: 登录用户（含非作者）访问详情，contact_info 可见"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="visible-to-logged-in@example.com",
    )

    # 第二个登录用户（非作者）访问
    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers=second_auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["contact_info"] == "visible-to-logged-in@example.com"


# ============================================================
# DSC-02.1: governance.user_validation_type 按权限返回
# ============================================================

@pytest.mark.asyncio
async def test_guest_governance_user_validation_type_is_none(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    second_auth_headers: dict, test_school: dict, test_category: dict,
):
    """DSC-02.1: 游客访问详情，governance.user_validation_type 恒为 None

    前端据此隐藏投票按钮（游客不请求需登录的投票接口）。
    即便 DB 中存在其他用户的投票，游客也看不到自己的投票类型。
    """
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )

    # 第二用户投票（confirmation），游客不应继承其投票类型
    vote_resp = await client.post(
        f"/api/v1/posts/{post.id}/validations",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )
    assert vote_resp.status_code == 200

    # 游客访问详情
    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200
    gov = resp.json()["governance"]
    # 游客：user_validation_type 恒为 None
    assert gov["user_validation_type"] is None
    # 但投票计数对游客可见（公开统计）
    assert gov["confirmation_count"] >= 1
    assert gov["total_validation_count"] >= 1


@pytest.mark.asyncio
async def test_logged_in_user_governance_user_validation_type_reflects_vote(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    second_auth_headers: dict, test_school: dict, test_category: dict,
):
    """DSC-02.1: 登录用户投票后，详情 governance.user_validation_type 返回其投票类型"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )

    # 第二用户投 confirmation
    await client.post(
        f"/api/v1/posts/{post.id}/validations",
        json={"validation_type": "confirmation"},
        headers=second_auth_headers,
    )

    # 第二用户访问详情：user_validation_type 应为 confirmation
    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers=second_auth_headers,
    )
    assert resp.status_code == 200
    gov = resp.json()["governance"]
    assert gov["user_validation_type"] == "confirmation"

    # 切换为 refutation
    await client.post(
        f"/api/v1/posts/{post.id}/validations",
        json={"validation_type": "refutation"},
        headers=second_auth_headers,
    )
    resp2 = await client.get(
        f"/api/v1/posts/{post.id}",
        headers=second_auth_headers,
    )
    assert resp2.status_code == 200
    gov2 = resp2.json()["governance"]
    assert gov2["user_validation_type"] == "refutation"


@pytest.mark.asyncio
async def test_logged_in_user_without_vote_returns_none_validation_type(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    second_auth_headers: dict, test_school: dict, test_category: dict,
):
    """DSC-02.1: 登录用户未投票时 user_validation_type 为 None（区别于游客的恒 None）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )

    # 第二用户访问但未投票
    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers=second_auth_headers,
    )
    assert resp.status_code == 200
    gov = resp.json()["governance"]
    # 未投票时为 None
    assert gov["user_validation_type"] is None


# ============================================================
# DSC-02.1: 游客不请求需登录的统计接口（is_liked / user_validation_type）
# ============================================================

@pytest.mark.asyncio
async def test_guest_detail_is_liked_is_false(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict,
):
    """DSC-02.1: 游客访问详情 is_liked 恒为 False（后端不查询 Like 表）

    前端据此不展示"已点赞"状态，且不调用需登录的点赞切换接口。
    """
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )

    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    # 游客：is_liked 恒 False（后端不查询 Like 表，current_user 为 None 分支）
    assert data["is_liked"] is False


@pytest.mark.asyncio
async def test_logged_in_user_detail_is_liked_reflects_state(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict,
):
    """DSC-02.1: 登录用户 is_liked 反映实际点赞状态（与游客形成对比）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )
    headers = {"Authorization": f"Bearer {test_user['access_token']}"}

    # 初始未点赞
    resp1 = await client.get(f"/api/v1/posts/{post.id}", headers=headers)
    assert resp1.status_code == 200
    assert resp1.json()["is_liked"] is False

    # 点赞
    like_resp = await client.post(f"/api/v1/posts/{post.id}/like", headers=headers)
    assert like_resp.status_code == 200

    # 再次查询：is_liked 为 True
    resp2 = await client.get(f"/api/v1/posts/{post.id}", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["is_liked"] is True


# ============================================================
# DSC-02.1: 评论按回复树展示（嵌套回复 + reply_to_user）
# ============================================================

@pytest.mark.asyncio
async def test_comment_reply_tree_structure(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    second_auth_headers: dict, test_school: dict, test_category: dict,
):
    """DSC-02.1: 评论按回复树展示——顶级评论 + 嵌套回复，含 reply_to_user

    场景：
        1. 第二用户发顶级评论 C1
        2. 作者回复 C1 → R1（reply_to_user=第二用户）
        3. 第二用户回复 R1 → R2（挂在 C1 下，reply_to_user=作者）
    验证：
        - GET /posts/{id}/comments 返回顶级评论列表，每条含 replies 数组
        - replies 中的 reply_to_user 字段正确填充
    """
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])
    author_headers = {"Authorization": f"Bearer {test_user['access_token']}"}

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )

    # 1) 第二用户发顶级评论 C1
    c1_resp = await client.post(
        f"/api/v1/posts/{post.id}/comments",
        json={"content": "这是顶级评论 C1"},
        headers=second_auth_headers,
    )
    assert c1_resp.status_code == 201
    c1_id = c1_resp.json()["id"]
    second_user_id = c1_resp.json()["user_id"]

    # 2) 作者回复 C1 → R1（reply_to_user=第二用户）
    r1_resp = await client.post(
        f"/api/v1/posts/{post.id}/comments",
        json={
            "content": "作者回复 C1",
            "parent_id": c1_id,
            "reply_to_user_id": second_user_id,
        },
        headers=author_headers,
    )
    assert r1_resp.status_code == 201
    r1_id = r1_resp.json()["id"]
    assert r1_resp.json()["parent_id"] == c1_id
    assert r1_resp.json()["reply_to_user_id"] == second_user_id

    # 3) 第二用户回复 R1 → R2（仍挂在 C1 下，reply_to_user=作者）
    r2_resp = await client.post(
        f"/api/v1/posts/{post.id}/comments",
        json={
            "content": "回复 R1",
            "parent_id": c1_id,  # 顶级父评论
            "reply_to_user_id": user_id,
        },
        headers=second_auth_headers,
    )
    assert r2_resp.status_code == 201
    r2_id = r2_resp.json()["id"]

    # 查询评论列表：应返回顶级评论 C1，replies 含 R1 和 R2
    # 评论列表需租户上下文（X-School-Code 或 auth token）
    list_resp = await client.get(
        f"/api/v1/posts/{post.id}/comments",
        headers={"X-School-Code": test_school["code"]},
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) >= 1

    top = next((c for c in items if c["id"] == c1_id), None)
    assert top is not None, "顶级评论 C1 应在列表中"
    assert top["content"] == "这是顶级评论 C1"
    assert top["reply_count"] >= 2

    # 嵌套回复
    replies = top.get("replies") or []
    assert len(replies) == 2

    r1 = next((r for r in replies if r["id"] == r1_id), None)
    r2 = next((r for r in replies if r["id"] == r2_id), None)
    assert r1 is not None, "R1 应在 C1 的 replies 中"
    assert r2 is not None, "R2 应在 C1 的 replies 中"

    # R1 回复第二用户
    assert r1["reply_to_user"] is not None
    assert r1["reply_to_user"]["id"] == second_user_id
    # R2 回复作者
    assert r2["reply_to_user"] is not None
    assert r2["reply_to_user"]["id"] == user_id


@pytest.mark.asyncio
async def test_comment_list_guest_accessible(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    second_auth_headers: dict, test_school: dict, test_category: dict,
):
    """DSC-02.1: 游客可访问评论列表（评论接口不要求登录，公开可见）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )

    # 第二用户发评论
    await client.post(
        f"/api/v1/posts/{post.id}/comments",
        json={"content": "游客可见的评论"},
        headers=second_auth_headers,
    )

    # 游客访问评论列表
    resp = await client.get(
        f"/api/v1/posts/{post.id}/comments",
        headers={"X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) >= 1
    assert items[0]["content"] == "游客可见的评论"


@pytest.mark.asyncio
async def test_guest_cannot_create_comment(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict,
):
    """DSC-02.1: 游客不能发评论（POST /comments 需登录，返回 401）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )

    # 游客发评论：未带 token → 401
    resp = await client.post(
        f"/api/v1/posts/{post.id}/comments",
        json={"content": "游客不能评论"},
        headers={"X-School-Code": test_school["code"]},
    )
    assert resp.status_code == 401


# ============================================================
# DSC-02.1: 详情 governance 字段完整结构校验
# ============================================================

@pytest.mark.asyncio
async def test_detail_governance_has_all_required_fields(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict,
):
    """DSC-02.1: 详情 governance 聚合返回所有契约字段（前端依赖）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )

    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"Authorization": f"Bearer {test_user['access_token']}"},
    )
    assert resp.status_code == 200
    gov = resp.json()["governance"]
    # 契约字段全部存在
    # Task 1.2 调整：change_reports_total/open/recent_change_reports
    # 已随 PostChangeReport 删除移除，governance 仅保留 2 类投票聚合
    for field in (
        "confirmation_count",
        "refutation_count",
        "total_validation_count",
        "validity_status",
        "user_validation_type",
    ):
        assert field in gov, f"governance 缺少字段 {field}"
    # 默认空状态
    assert gov["confirmation_count"] == 0
    assert gov["refutation_count"] == 0
    assert gov["total_validation_count"] == 0
    assert gov["validity_status"] in ("valid", "invalid", "uncertain")
    assert gov["user_validation_type"] is None  # 未投票


@pytest.mark.asyncio
async def test_detail_change_reports_aggregated_in_governance(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    second_auth_headers: dict, test_school: dict, test_category: dict,
):
    """DSC-02.1: 详情 governance 聚合 3 类问题报告（update/expiration_report/conflict_report）

    Task 1.2 调整：PostChangeReport 模型与 /posts/{id}/change-reports 端点已删除，
    3 类问题报告功能整体移除（与评论/举报功能冲突）。帖子过期/冲突状态由管理员
    通过举报队列处理。
    """
    pytest.skip("Task 1.2: PostChangeReport 已删除，3 类问题报告功能移除")
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )

    # 第二用户提交 3 类问题报告
    for rtype, desc in [
        ("update", "建议更新内容"),
        ("expiration_report", "信息已过期"),
        ("conflict_report", "与其他信息冲突"),
    ]:
        r = await client.post(
            f"/api/v1/posts/{post.id}/change-reports",
            json={"report_type": rtype, "description": desc},
            headers=second_auth_headers,
        )
        assert r.status_code == 201

    # 查询详情
    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"Authorization": f"Bearer {test_user['access_token']}"},
    )
    assert resp.status_code == 200
    gov = resp.json()["governance"]
    assert gov["change_reports_total"] == 3
    assert gov["change_reports_open"] == 3
    assert len(gov["recent_change_reports"]) == 3
    # 报告类型集合正确
    report_types = {r["report_type"] for r in gov["recent_change_reports"]}
    assert report_types == {"update", "expiration_report", "conflict_report"}


# ============================================================
# DSC-02.1: 详情图片字段（多图轮播）
# ============================================================

@pytest.mark.asyncio
async def test_detail_multiple_images_with_sort_order(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict,
):
    """DSC-02.1: 详情返回多张图片，按 sort_order 顺序排列（前端轮播依赖）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )
    await _add_post_images(db_session, post.id, [
        "https://example.com/a.jpg",
        "https://example.com/b.jpg",
        "https://example.com/c.jpg",
    ])

    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"Authorization": f"Bearer {test_user['access_token']}"},
    )
    assert resp.status_code == 200
    images = resp.json()["images"]
    assert len(images) == 3
    # sort_order 递增
    assert images[0]["sort_order"] == 0
    assert images[1]["sort_order"] == 1
    assert images[2]["sort_order"] == 2
    assert images[0]["image_url"] == "https://example.com/a.jpg"


@pytest.mark.asyncio
async def test_detail_no_images_returns_empty_list(
    client: AsyncClient, db_session: AsyncSession, test_user: dict,
    test_school: dict, test_category: dict,
):
    """DSC-02.1: 无图片的帖子详情 images 为空列表（前端轮播不渲染）"""
    from app.core.security import decode_token
    user_id = int(decode_token(test_user["access_token"])["sub"])

    post = await _create_published_post(
        db_session, user_id, test_school["id"],
        test_category["id"],
        contact_info="x",
    )

    resp = await client.get(
        f"/api/v1/posts/{post.id}",
        headers={"Authorization": f"Bearer {test_user['access_token']}"},
    )
    assert resp.status_code == 200
    images = resp.json()["images"]
    # 无图片时返回空列表（DSC-02.1: 详情接口显式设置为 []，前端轮播不渲染）
    assert images is not None
    assert len(images) == 0
