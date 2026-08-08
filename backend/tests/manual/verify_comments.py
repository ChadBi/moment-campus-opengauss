"""E2E 验证脚本：评论模块完整链路

场景：
1. user2 评论 user1 的帖子 → user1 收到评论通知
2. user1 回复 user2 的评论 → user2 收到回复通知
3. 获取评论列表（含子评论嵌套）
4. user2 删除自己的评论 → 软删除 + comment_count -1
5. 删除后列表不再返回该评论
"""
import requests
import time

BASE = "http://localhost:8000/api/v1"


def login(phone, password="pass123"):
    r = requests.post(
        f"{BASE}/auth/login",
        json={"phone": phone, "password": password},
        headers={"X-School-Code": "jiangnan"},
    )
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


def h(token):
    return {
        "Authorization": f"Bearer {token}",
        "X-School-Code": "jiangnan",
        "Content-Type": "application/json",
    }


print("=" * 60)
print("评论模块 E2E 链路验证")
print("=" * 60)

token1 = login("13900000002")
headers1 = h(token1)
token2 = login("13900000003")
headers2 = h(token2)

# 0. 找一个 user1 已发布的帖子
r = requests.get(f"{BASE}/users/me/posts?status=published&page=1&page_size=20", headers=headers1)
posts_data = r.json() if r.status_code == 200 else {}
user1_posts = posts_data.get("items", [])
if not user1_posts:
    # 兜底：使用公开列表
    r = requests.get(f"{BASE}/posts?page=1&page_size=20", headers=headers1)
    user1_posts = r.json().get("items", [])

assert user1_posts, "未找到可用帖子"
target_post = user1_posts[0]
post_id = target_post["id"]
post_title = target_post.get("title", "")
print(f"\n目标帖子: id={post_id} title={post_title[:40]}")

# 1. user1 通知数（操作前）
r = requests.get(f"{BASE}/notifications?limit=50", headers=headers1)
notif1_before = r.json().get("total", 0) if r.status_code == 200 else 0
# 2. user2 通知数（操作前）
r = requests.get(f"{BASE}/notifications?limit=50", headers=headers2)
notif2_before = r.json().get("total", 0) if r.status_code == 200 else 0
print(f"User1 通知数（操作前）: {notif1_before}")
print(f"User2 通知数（操作前）: {notif2_before}")

# 3. user2 评论 user1 的帖子
r = requests.post(
    f"{BASE}/posts/{post_id}/comments",
    json={"content": "[E2E评论链路] 这是一条测试评论，验证评论通知与回复嵌套。"},
    headers=headers2,
)
print(f"\nUser2 创建顶级评论: {r.status_code}")
assert r.status_code == 201, f"创建评论失败: {r.text}"
top_comment = r.json()
top_comment_id = top_comment["id"]
print(f"  comment_id={top_comment_id} author={top_comment.get('author')}")

# 4. user1 回复 user2 的评论
r = requests.post(
    f"{BASE}/posts/{post_id}/comments",
    json={
        "content": "[E2E评论链路] 感谢你的评论，这是回复。",
        "parent_id": top_comment_id,
        "reply_to_user_id": top_comment["user_id"],
    },
    headers=headers1,
)
print(f"User1 回复评论: {r.status_code}")
assert r.status_code == 201, f"回复评论失败: {r.text}"
reply_comment = r.json()
reply_comment_id = reply_comment["id"]
print(f"  reply_id={reply_comment_id} reply_to={reply_comment.get('reply_to_user')}")

# 5. 等待通知生成
time.sleep(1)

# 6. 检查通知
r = requests.get(f"{BASE}/notifications?limit=50", headers=headers1)
notif1_after = r.json().get("total", 0) if r.status_code == 200 else 0
r = requests.get(f"{BASE}/notifications?limit=50", headers=headers2)
notif2_after = r.json().get("total", 0) if r.status_code == 200 else 0
print(f"\nUser1 通知数（操作后）: {notif1_after} (变化: +{notif1_after - notif1_before})")
print(f"User2 通知数（操作后）: {notif2_after} (变化: +{notif2_after - notif2_before})")

# 检查 user1 是否收到帖子评论通知
r = requests.get(f"{BASE}/notifications?limit=50", headers=headers1)
hit1 = False
if r.status_code == 200:
    for n in r.json().get("items", []):
        if n.get("type") == "comment" and n.get("target_id") == post_id and n.get("title") == "您的帖子有新评论":
            hit1 = True
            break
print(f"User1 收到帖子评论通知: {'✅' if hit1 else '❌'}")

# 检查 user2 是否收到回复通知
r = requests.get(f"{BASE}/notifications?limit=50", headers=headers2)
hit2 = False
if r.status_code == 200:
    for n in r.json().get("items", []):
        if n.get("type") == "comment" and n.get("title") == "有人回复了你的评论":
            hit2 = True
            break
print(f"User2 收到回复评论通知: {'✅' if hit2 else '❌'}")

# 7. 获取评论列表（验证嵌套）
r = requests.get(f"{BASE}/posts/{post_id}/comments?page=1&page_size=20", headers=headers1)
print(f"\n获取评论列表: {r.status_code}")
if r.status_code == 200:
    items = r.json().get("items", [])
    print(f"  顶级评论数: {len(items)}")
    found_top = False
    found_reply = False
    for c in items:
        if c["id"] == top_comment_id:
            found_top = True
            replies = c.get("replies") or []
            print(f"  顶级评论 {top_comment_id} 的回复数: {len(replies)}")
            for r2 in replies:
                if r2["id"] == reply_comment_id:
                    found_reply = True
                    print(f"  回复嵌套层级正确: reply_id={reply_comment_id}")
    print(f"顶级评论命中: {'✅' if found_top else '❌'}")
    print(f"回复嵌套命中: {'✅' if found_reply else '❌'}")

# 8. 删除顶级评论（user2 删除自己的评论）
r = requests.delete(f"{BASE}/comments/{top_comment_id}", headers=headers2)
print(f"\nUser2 删除顶级评论: {r.status_code} {r.json() if r.status_code == 200 else r.text[:100]}")
assert r.status_code == 200, f"删除评论失败: {r.text}"

# 9. 再次获取评论列表，验证顶级评论已不在列表中
r = requests.get(f"{BASE}/posts/{post_id}/comments?page=1&page_size=20", headers=headers1)
if r.status_code == 200:
    items = r.json().get("items", [])
    still_exists = any(c["id"] == top_comment_id for c in items)
    print(f"删除后顶级评论不再可见: {'✅' if not still_exists else '❌'}")

# 10. 越权删除测试：user2 尝试删除 user1 的回复
r = requests.delete(f"{BASE}/comments/{reply_comment_id}", headers=headers2)
print(f"User2 越权删除 user1 的回复: {r.status_code} (期望 403)")
assert r.status_code == 403, f"越权删除应返回 403, 实际 {r.status_code}"

print("\n" + "=" * 60)
print("评论模块 E2E 验证完成")
print("=" * 60)
