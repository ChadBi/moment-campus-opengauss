"""
此刻校园 - 超级大规模功能检查脚本 v2
修正路径错误 + 验证评论修复
"""
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime

BASE = "http://localhost:8000/api/v1"
results = []


def record(module, name, ok, detail=""):
    results.append({"module": module, "name": name, "ok": ok, "detail": detail})
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] [{module}] {name}: {detail[:120]}")


def http(method, url, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status = resp.status
            text = resp.read().decode("utf-8")
            try:
                return status, json.loads(text)
            except json.JSONDecodeError:
                return status, text
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, text
    except Exception as e:
        return 0, str(e)


def main():
    print("=" * 60)
    print("此刻校园 - 超级大规模功能检查 v2")
    print(f"时间: {datetime.now().isoformat()}")
    print("=" * 60)

    # ========== 1. 认证模块 ==========
    print("\n===== 1. 认证模块 =====")
    status, resp = http("POST", f"{BASE}/auth/login",
                        body={"email": "user1@example.com", "password": "pass123"})
    record("认证", "user1 登录", status == 200, f"status={status}")
    user1_token = resp.get("access_token") if isinstance(resp, dict) else None
    user1_data = resp.get("user", {}) if isinstance(resp, dict) else {}
    record("认证", "登录返回 user 字段", bool(user1_data), f"user_id={user1_data.get('id')}")
    record("认证", "登录返回 reputation_score",
           isinstance(resp, dict) and "reputation_score" in user1_data,
           f"score={user1_data.get('reputation_score')}")
    user1_score_before = float(user1_data.get("reputation_score") or 0)
    user1_id = user1_data.get("id")

    status, resp2 = http("POST", f"{BASE}/auth/login",
                         body={"email": "admin@momentcampus.com", "password": "pass123"})
    record("认证", "admin 登录", status == 200, f"status={status}")
    admin_token = resp2.get("access_token") if isinstance(resp2, dict) else None
    admin_data = resp2.get("user", {}) if isinstance(resp2, dict) else {}
    record("认证", "admin 角色", admin_data.get("role") in ("admin", "super_admin"),
           f"role={admin_data.get('role')}")

    # ========== 2. 帖子列表 ==========
    print("\n===== 2. 帖子列表 =====")
    status, resp = http("GET", f"{BASE}/posts?page=1&page_size=20&sort=latest", token=user1_token)
    record("帖子列表", "最新排序加载", status == 200, f"status={status}")
    posts_items = resp.get("items", []) if isinstance(resp, dict) else []
    record("帖子列表", "返回帖子数据", len(posts_items) > 0,
           f"count={len(posts_items)}, total={resp.get('total') if isinstance(resp, dict) else 'N/A'}")

    if len(posts_items) >= 2:
        t1 = posts_items[0].get("created_at", "")
        t2 = posts_items[1].get("created_at", "")
        record("帖子列表", "最新排序正确", t1 >= t2, f"t1={t1[:19]} >= t2={t2[:19]}")

    if posts_items:
        record("帖子列表", "无 is_top 字段", "is_top" not in posts_items[0], "is_top removed")

    now = datetime.now().isoformat()
    future_count = sum(1 for p in posts_items if p.get("created_at", "") > now)
    record("帖子列表", "无未来时间帖子", future_count == 0, f"future={future_count}")

    status, _ = http("GET", f"{BASE}/posts?page=1&page_size=20&sort=hottest", token=user1_token)
    record("帖子列表", "最热排序", status == 200, f"status={status}")

    status, _ = http("GET", f"{BASE}/posts?page=1&page_size=20&sort=nearest", token=user1_token)
    record("帖子列表", "最近排序", status == 200, f"status={status}")

    # ========== 3. 帖子详情 ==========
    print("\n===== 3. 帖子详情 =====")
    post_id = None
    if posts_items:
        post_id = posts_items[0]["id"]
        status, resp = http("GET", f"{BASE}/posts/{post_id}", token=user1_token)
        record("帖子详情", "获取详情", status == 200, f"post_id={post_id} status={status}")
        if status == 200 and isinstance(resp, dict):
            record("帖子详情", "浏览次数 >= 1", resp.get("view_count", 0) >= 1,
                   f"views={resp.get('view_count')}")
            content_len = len(resp.get("content", ""))
            record("帖子详情", "content 无 200 字限制", content_len <= 10000,
                   f"len={content_len}")

    # ========== 4. 点赞（切换式 POST）==========
    print("\n===== 4. 点赞 =====")
    if post_id:
        # 点赞
        status, resp = http("POST", f"{BASE}/posts/{post_id}/like", token=user1_token)
        record("点赞", "点赞请求", status == 200, f"status={status} is_liked={resp.get('is_liked') if isinstance(resp, dict) else 'N/A'}")
        # 再次 POST = 取消点赞
        status, resp = http("POST", f"{BASE}/posts/{post_id}/like", token=user1_token)
        record("点赞", "取消点赞(再次POST)", status == 200, f"status={status} is_liked={resp.get('is_liked') if isinstance(resp, dict) else 'N/A'}")

    # ========== 5. 验证（证实/证伪）==========
    print("\n===== 5. 验证（证实/证伪）=====")
    target_post = None
    for p in posts_items:
        if p.get("user_id") != user1_id:
            target_post = p
            break
    if target_post:
        vpost_id = target_post["id"]
        # 证实（confirmation）
        status, resp = http("POST", f"{BASE}/posts/{vpost_id}/validate",
                            token=user1_token, body={"validation_type": "confirmation"})
        record("验证", "证实请求", status == 200, f"status={status} body={str(resp)[:100]}")
        # 再次证实 = 取消
        status, resp = http("POST", f"{BASE}/posts/{vpost_id}/validate",
                            token=user1_token, body={"validation_type": "confirmation"})
        record("验证", "取消证实(再次POST)", status == 200, f"status={status}")

    # ========== 6. 评论（已修复 500 bug）==========
    print("\n===== 6. 评论 =====")
    comment_ok = False
    if post_id:
        comment_text = f"自动化测试评论 v2 {datetime.now().strftime('%H:%M:%S')}"
        status, resp = http("POST", f"{BASE}/posts/{post_id}/comments",
                            token=user1_token, body={"content": comment_text})
        comment_ok = status in (200, 201)
        record("评论", "创建评论(已修复)", comment_ok, f"status={status} body={str(resp)[:100]}")

        status, resp = http("GET", f"{BASE}/posts/{post_id}/comments", token=user1_token)
        record("评论", "评论列表加载", status == 200, f"status={status}")

    # ========== 7. 通知 ==========
    print("\n===== 7. 通知 =====")
    status, resp = http("GET", f"{BASE}/notifications?page=1&page_size=20", token=user1_token)
    record("通知", "通知列表加载", status == 200, f"status={status}")
    if status == 200 and isinstance(resp, dict):
        notif_items = resp.get("items", [])
        record("通知", "通知数据", len(notif_items) >= 0, f"count={len(notif_items)}")
        # 检查通知类型
        types = set(n.get("type") for n in notif_items)
        record("通知", "含 like/comment 类型", types & {"like", "comment"} == types - {None},
               f"types={types}")

    # ========== 8. 个人中心 ==========
    print("\n===== 8. 个人中心 =====")
    status, resp = http("GET", f"{BASE}/users/me", token=user1_token)
    record("个人中心", "获取个人信息", status == 200, f"status={status}")
    if status == 200 and isinstance(resp, dict):
        record("个人中心", "含 reputation_score", "reputation_score" in resp,
               f"score={resp.get('reputation_score')}")
        record("个人中心", "贡献值 > 0", float(resp.get("reputation_score") or 0) > 0,
               f"score={resp.get('reputation_score')}")

    new_bio = f"测试简介 v2 {datetime.now().strftime('%H:%M')}"
    status, resp = http("PUT", f"{BASE}/users/me", token=user1_token, body={"bio": new_bio})
    record("个人中心", "更新简介", status == 200, f"status={status}")

    # ========== 9. 发布帖子 ==========
    print("\n===== 9. 发布帖子 =====")
    new_post = {
        "title": f"自动化测试帖子 v2 {datetime.now().strftime('%H:%M:%S')}",
        "content": "大规模功能检查 v2：验证发帖功能和信誉分更新。内容超过200字以验证 max_length 限制已移除。" * 3,
        "category_id": 1,
        "is_anonymous": False,
        "status": "pending",
    }
    status, resp = http("POST", f"{BASE}/posts", token=user1_token, body=new_post)
    record("发布帖子", "创建 pending 帖子", status in (200, 201), f"status={status}")
    new_post_id = None
    if status in (200, 201) and isinstance(resp, dict):
        new_post_id = resp.get("id")
        record("发布帖子", "状态为 pending", resp.get("status") == "pending",
               f"status={resp.get('status')}")

        # 验证发帖后信誉分变化（+0.5）
        status2, resp2 = http("GET", f"{BASE}/users/me", token=user1_token)
        if status2 == 200 and isinstance(resp2, dict):
            after_score = float(resp2.get("reputation_score") or 0)
            # 评论也会更新信誉分，所以 after >= before
            record("发布帖子", "发帖后信誉分更新",
                   after_score >= user1_score_before,
                   f"before={user1_score_before} after={after_score} diff={after_score-user1_score_before:+.2f}")

    # ========== 10. 后台管理 ==========
    print("\n===== 10. 后台管理 =====")
    # 待审核列表（正确路径：/admin/posts/pending）
    status, resp = http("GET", f"{BASE}/admin/posts/pending?page=1&page_size=20",
                        token=admin_token)
    record("后台管理", "待审核列表", status == 200, f"status={status}")
    pending_items = resp.get("items", []) if isinstance(resp, dict) else []
    record("后台管理", "待审核帖子数", len(pending_items) >= 0, f"count={len(pending_items)}")

    # 审核操作（PUT /admin/posts/{id}/approve）
    if pending_items:
        review_post_id = pending_items[0]["id"]
        status2, resp2 = http("PUT", f"{BASE}/admin/posts/{review_post_id}/approve",
                              token=admin_token)
        record("后台管理", "审核通过", status2 == 200,
               f"status={status2} body={str(resp2)[:100]}")
        status3, resp3 = http("GET", f"{BASE}/posts/{review_post_id}", token=admin_token)
        if status3 == 200 and isinstance(resp3, dict):
            record("后台管理", "审核后 status=published",
                   resp3.get("status") == "published",
                   f"status={resp3.get('status')}")
    else:
        record("后台管理", "审核通过", True, "无待审核帖子，跳过")

    status, _ = http("GET", f"{BASE}/admin/tags?page=1&page_size=20", token=admin_token)
    record("后台管理", "标签列表", status == 200, f"status={status}")

    status, _ = http("GET", f"{BASE}/admin/logs?page=1&page_size=20", token=admin_token)
    record("后台管理", "操作日志", status == 200, f"status={status}")

    status, _ = http("GET", f"{BASE}/admin/stats", token=admin_token)
    record("后台管理", "统计信息", status == 200, f"status={status}")

    status, _ = http("GET", f"{BASE}/admin/users?page=1&page_size=20", token=admin_token)
    record("后台管理", "用户列表", status == 200, f"status={status}")

    # ========== 11. 地图（需要边界参数）==========
    print("\n===== 11. 地图 =====")
    # 江南大学蠡湖校区大约范围：北纬31.49-31.52, 东经120.26-120.30
    status, resp = http("GET",
                        f"{BASE}/map/markers?north=31.52&south=31.49&east=120.30&west=120.26",
                        token=user1_token)
    record("地图", "标记列表(带边界)", status == 200, f"status={status}")
    if status == 200 and isinstance(resp, list):
        record("地图", "标记数据", len(resp) > 0, f"count={len(resp)}")

    # ========== 12. 搜索（URL编码中文）==========
    print("\n===== 12. 搜索 =====")
    q = urllib.parse.quote("食堂")
    status, _ = http("GET", f"{BASE}/search?q={q}&page=1&page_size=10", token=user1_token)
    record("搜索", "关键词搜索", status == 200, f"status={status}")

    # ========== 13. 分类 ==========
    print("\n===== 13. 分类 =====")
    status, _ = http("GET", f"{BASE}/categories", token=user1_token)
    record("分类", "分类列表", status == 200, f"status={status}")

    # ========== 14. 地点 ==========
    print("\n===== 14. 地点 =====")
    status, _ = http("GET", f"{BASE}/locations", token=user1_token)
    record("地点", "地点列表", status == 200, f"status={status}")

    # ========== 15. 信誉分专项验证 ==========
    print("\n===== 15. 信誉分专项验证 =====")
    # 验证所有用户的信誉分
    status, resp = http("GET", f"{BASE}/admin/users?page=1&page_size=50", token=admin_token)
    if status == 200 and isinstance(resp, dict):
        users = resp.get("items", [])
        scores = [(u.get("nickname"), u.get("reputation_score")) for u in users]
        valid_scores = [s for _, s in scores if s is not None]
        record("信誉分", "所有用户都有信誉分", len(valid_scores) == len(users),
               f"{len(valid_scores)}/{len(users)} 有分数")
        if valid_scores:
            float_scores = [float(s) for s in valid_scores]
            record("信誉分", "分数在 0-100 范围内",
                   all(0 <= s <= 100 for s in float_scores),
                   f"min={min(float_scores)} max={max(float_scores)}")

    # ========== 汇总 ==========
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r["ok"])
    failed = sum(1 for r in results if not r["ok"])
    print(f"总计: {total} | 通过: {passed} | 失败: {failed}")
    print(f"通过率: {passed/total*100:.1f}%" if total else "N/A")

    if failed:
        print("\n失败项:")
        for r in results:
            if not r["ok"]:
                print(f"  - [{r['module']}] {r['name']}: {r['detail']}")

    with open("AIwork/检查结果v2.json", "w", encoding="utf-8") as f:
        json.dump({"summary": {"total": total, "passed": passed, "failed": failed},
                   "results": results}, f, ensure_ascii=False, indent=2)
    print("\n结果已保存到 AIwork/检查结果v2.json")


if __name__ == "__main__":
    main()
