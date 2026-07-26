"""E2E 验证脚本：通知中心交互（已读切换 + 偏好）

场景：
1. 触发一批通知（评论 + 订阅 + 投票/报告等），保证有未读
2. 获取未读数（unread-count）
3. 按已读状态筛选列表：unread / read
4. 标记单条已读 → 未读数 -1
5. 标记全部已读 → 未读数 = 0
6. 越权：user2 不能标记 user1 的通知
7. 不存在的通知 ID → 404
8. 通知偏好：安全账号通知不可全关（system/audit/instant 全关 → 400）
9. digest_time 格式校验
"""
import requests
import time

BASE = "http://localhost:8000/api/v1"


def login(email, password="pass123"):
    r = requests.post(
        f"{BASE}/auth/login",
        json={"email": email, "password": password},
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
print("通知中心 E2E 链路验证")
print("=" * 60)

token1 = login("user1@example.com")
headers1 = h(token1)
token2 = login("user2@example.com")
headers2 = h(token2)

# ============================================================
# 1. 触发一批通知（user2 评论 user1 的帖子 → user1 收到通知）
# ============================================================
print("\n--- 1. 触发新通知 ---")
r = requests.get(f"{BASE}/users/me/posts?status=published&page=1&page_size=5", headers=headers1)
user1_posts = r.json().get("items", [])
assert user1_posts, "user1 没有已发布帖子"
post_id = user1_posts[0]["id"]
print(f"  目标帖子: {post_id}")

# 触发评论通知
r = requests.post(
    f"{BASE}/posts/{post_id}/comments",
    json={"content": "[E2E通知中心] 触发评论通知"},
    headers=headers2,
)
print(f"  User2 评论: {r.status_code}")
assert r.status_code == 201

time.sleep(1)

# ============================================================
# 2. 获取未读数
# ============================================================
print("\n--- 2. 获取未读数 ---")
r = requests.get(f"{BASE}/notifications/unread-count", headers=headers1)
print(f"  GET /notifications/unread-count: {r.status_code}")
print(f"  {r.json()}")
unread_count = r.json()["unread_count"]
has_unread = r.json()["has_unread"]
assert unread_count > 0, "应有未读通知"
assert has_unread is True

# ============================================================
# 3. 按已读状态筛选
# ============================================================
print("\n--- 3. 按已读状态筛选 ---")
r = requests.get(f"{BASE}/notifications?is_read=false&page=1&page_size=20", headers=headers1)
unread_list = r.json()
print(f"  未读列表 total={unread_list['total']}")
assert unread_list["total"] == unread_count, "未读列表数应等于 unread-count"
all_unread_valid = all(not n["is_read"] for n in unread_list["items"])
print(f"  未读列表项状态正确: {'✅' if all_unread_valid else '❌'}")
assert all_unread_valid

r = requests.get(f"{BASE}/notifications?is_read=true&page=1&page_size=20", headers=headers1)
read_list = r.json()
print(f"  已读列表 total={read_list['total']}")
all_read_valid = all(n["is_read"] for n in read_list["items"])
print(f"  已读列表项状态正确: {'✅' if all_read_valid else '❌'}")
assert all_read_valid

# 按类型筛选
r = requests.get(f"{BASE}/notifications?type=comment&page=1&page_size=20", headers=headers1)
type_list = r.json()
print(f"  type=comment total={type_list['total']}")
all_comment = all(n["type"] == "comment" for n in type_list["items"])
print(f"  类型筛选正确: {'✅' if all_comment else '❌'}")
assert all_comment

# ============================================================
# 4. 标记单条已读
# ============================================================
print("\n--- 4. 标记单条已读 ---")
target_id = unread_list["items"][0]["id"]
print(f"  目标通知 ID: {target_id}")

r = requests.put(f"{BASE}/notifications/{target_id}/read", headers=headers1)
print(f"  PUT /notifications/{target_id}/read: {r.status_code} {r.json()}")
assert r.status_code == 200

# 重复标记（幂等）
r = requests.put(f"{BASE}/notifications/{target_id}/read", headers=headers1)
print(f"  重复标记: {r.status_code} (期望 200，幂等)")
assert r.status_code == 200

# 未读数 -1
r = requests.get(f"{BASE}/notifications/unread-count", headers=headers1)
new_unread = r.json()["unread_count"]
print(f"  未读数: {unread_count} → {new_unread} (期望 -1)")
assert new_unread == unread_count - 1, "标记后未读数应 -1"

# 验证该通知已读
r = requests.get(f"{BASE}/notifications?is_read=true&page=1&page_size=20", headers=headers1)
found_read = any(n["id"] == target_id and n["is_read"] for n in r.json()["items"])
print(f"  通知出现在已读列表: {'✅' if found_read else '❌'}")
assert found_read

# ============================================================
# 5. 不存在的通知 → 404
# ============================================================
print("\n--- 5. 不存在的通知 ---")
r = requests.put(f"{BASE}/notifications/999999/read", headers=headers1)
print(f"  标记不存在通知: {r.status_code} (期望 404)")
assert r.status_code == 404

# ============================================================
# 6. 越权：user2 标记 user1 的通知
# ============================================================
print("\n--- 6. 越权标记 ---")
r = requests.put(f"{BASE}/notifications/{target_id}/read", headers=headers2)
print(f"  User2 标记 user1 的通知: {r.status_code} (期望 404)")
assert r.status_code == 404, "越权标记应返回 404（不泄露存在性）"

# ============================================================
# 7. 标记全部已读
# ============================================================
print("\n--- 7. 标记全部已读 ---")
r = requests.put(f"{BASE}/notifications/read-all", headers=headers1)
print(f"  PUT /notifications/read-all: {r.status_code} {r.json()}")
assert r.status_code == 200

r = requests.get(f"{BASE}/notifications/unread-count", headers=headers1)
final_unread = r.json()["unread_count"]
print(f"  最终未读数: {final_unread} (期望 0)")
assert final_unread == 0, "全部已读后未读数应为 0"

# ============================================================
# 8. 通知偏好：安全账号通知不可全关
# ============================================================
print("\n--- 8. 通知偏好校验 ---")
r = requests.get(f"{BASE}/notifications/preferences", headers=headers1)
prefs = r.json()
print(f"  当前偏好: {prefs}")

# 尝试将 system/audit/instant 全部关闭 → 应被拒绝
r = requests.put(
    f"{BASE}/notifications/preferences",
    json={
        "system_enabled": False,
        "audit_enabled": False,
        "instant_enabled": False,
    },
    headers=headers1,
)
print(f"  全关安全通道: {r.status_code} (期望 400)")
assert r.status_code == 400, "安全账号通知全关应被拒绝"

# 仅关闭 system + audit（保留 instant） → 应允许
r = requests.put(
    f"{BASE}/notifications/preferences",
    json={
        "system_enabled": False,
        "audit_enabled": False,
        "instant_enabled": True,
    },
    headers=headers1,
)
print(f"  关 system+audit，保留 instant: {r.status_code} (期望 200)")
assert r.status_code == 200

# 还原
r = requests.put(
    f"{BASE}/notifications/preferences",
    json={
        "system_enabled": True,
        "audit_enabled": True,
        "instant_enabled": True,
    },
    headers=headers1,
)
print(f"  还原: {r.status_code}")

# digest_time 格式校验
r = requests.put(
    f"{BASE}/notifications/preferences",
    json={"digest_time": "25:00"},
    headers=headers1,
)
print(f"  非法 digest_time=25:00: {r.status_code} (期望 400)")
assert r.status_code == 400

r = requests.put(
    f"{BASE}/notifications/preferences",
    json={"digest_time": "08:30"},
    headers=headers1,
)
print(f"  合法 digest_time=08:30: {r.status_code} (期望 200)")
assert r.status_code == 200

# 还原 digest_time
requests.put(
    f"{BASE}/notifications/preferences",
    json={"digest_time": "09:00"},
    headers=headers1,
)

print("\n" + "=" * 60)
print("通知中心 E2E 验证完成")
print("=" * 60)
