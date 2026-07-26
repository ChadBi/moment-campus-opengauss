"""E2E 验证脚本：个人中心完整链路（PRF-01.2 / PRF-01.3 / PUB-02）

场景：
1. 获取当前用户信息
2. 更新昵称 / 简介 / 头像 URL
3. 更新后再次查询，验证持久化
4. 我的发布：按状态筛选（published / pending / draft）
5. 我的统计：状态分组 + 贡献验证
6. 浏览历史：访问帖子 → 列表新增 → 删除单条 → 清空全部
7. 通知偏好（如有）
"""
import requests
import time
import uuid

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
print("个人中心 E2E 链路验证")
print("=" * 60)

token1 = login("user1@example.com")
headers1 = h(token1)
token2 = login("user2@example.com")
headers2 = h(token2)

# ============================================================
# 1. 获取当前用户信息
# ============================================================
print("\n--- 1. 获取当前用户信息 ---")
r = requests.get(f"{BASE}/users/me", headers=headers1)
print(f"GET /users/me: {r.status_code}")
assert r.status_code == 200
me = r.json()
print(f"  id={me['id']} nickname={me['nickname']} bio={me.get('bio')} avatar_url={me.get('avatar_url')}")

# ============================================================
# 2. 更新昵称 / 简介 / 头像 URL
# ============================================================
print("\n--- 2. 更新用户资料 ---")
new_nickname = f"E2E测试_{uuid.uuid4().hex[:6]}"
new_bio = f"E2E测试简介_{uuid.uuid4().hex[:8]}"
new_avatar = f"https://example.com/avatars/{uuid.uuid4().hex[:8]}.png"
r = requests.put(
    f"{BASE}/users/me",
    json={"nickname": new_nickname, "bio": new_bio, "avatar_url": new_avatar},
    headers=headers1,
)
print(f"PUT /users/me: {r.status_code}")
assert r.status_code == 200, f"更新失败: {r.text}"
updated = r.json()
assert updated["nickname"] == new_nickname, "昵称未更新"
assert updated["bio"] == new_bio, "简介未更新"
assert updated["avatar_url"] == new_avatar, "头像未更新"
print(f"  昵称: {updated['nickname']}")
print(f"  简介: {updated['bio']}")
print(f"  头像: {updated['avatar_url']}")

# 重新查询验证持久化
r = requests.get(f"{BASE}/users/me", headers=headers1)
me_after = r.json()
assert me_after["nickname"] == new_nickname, "持久化失败：昵称"
assert me_after["bio"] == new_bio, "持久化失败：简介"
assert me_after["avatar_url"] == new_avatar, "持久化失败：头像"
print(f"  持久化验证: ✅")

# ============================================================
# 3. 我的发布：按状态筛选
# ============================================================
print("\n--- 3. 我的发布：按状态筛选 ---")
r = requests.get(f"{BASE}/users/me/posts?page=1&page_size=20", headers=headers1)
all_posts = r.json()
print(f"全部帖子: total={all_posts['total']}")

r = requests.get(f"{BASE}/users/me/posts?status=published&page=1&page_size=20", headers=headers1)
published_posts = r.json()
print(f"published: total={published_posts['total']}")

r = requests.get(f"{BASE}/users/me/posts?status=draft&page=1&page_size=20", headers=headers1)
draft_posts = r.json()
print(f"draft: total={draft_posts['total']}")

r = requests.get(f"{BASE}/users/me/posts?status=pending&page=1&page_size=20", headers=headers1)
pending_posts = r.json()
print(f"pending: total={pending_posts['total']}")

# 验证状态筛选有效：published 列表中所有项 status 都是 published
all_pub_valid = all(p["status"] == "published" for p in published_posts["items"])
print(f"  published 列表项状态全部正确: {'✅' if all_pub_valid else '❌'}")
assert all_pub_valid

# 各状态数相加应等于总数（draft+pending+published+expired+conflict+archived = total）
status_sum = (
    published_posts["total"] + draft_posts["total"] + pending_posts["total"]
)
# 还可能有 expired/conflict/archived
r = requests.get(f"{BASE}/users/me/posts?status=expired&page=1&page_size=20", headers=headers1)
status_sum += r.json()["total"]
r = requests.get(f"{BASE}/users/me/posts?status=conflict&page=1&page_size=20", headers=headers1)
status_sum += r.json()["total"]
r = requests.get(f"{BASE}/users/me/posts?status=archived&page=1&page_size=20", headers=headers1)
status_sum += r.json()["total"]
print(f"  6 态求和={status_sum} vs total={all_posts['total']}: {'✅' if status_sum == all_posts['total'] else '❌'}")
assert status_sum == all_posts["total"], "6 态求和应等于总数"

# ============================================================
# 4. 我的统计
# ============================================================
print("\n--- 4. 我的统计（PRF-01.2） ---")
r = requests.get(f"{BASE}/users/me/stats", headers=headers1)
stats = r.json()
print(f"  school_id={stats['school_id']}")
print(f"  published_count={stats['published_count']}")
print(f"  draft_count={stats['draft_count']}")
print(f"  pending_count={stats['pending_count']}")
print(f"  expired_count={stats['expired_count']}")
print(f"  conflict_count={stats['conflict_count']}")
print(f"  archived_count={stats['archived_count']}")
print(f"  total_count={stats['total_count']}")
print(f"  confirmation_count={stats['confirmation_count']}")

# 验证统计数与列表一致
assert stats["published_count"] == published_posts["total"], "published_count 与列表不符"
assert stats["draft_count"] == draft_posts["total"], "draft_count 与列表不符"
assert stats["pending_count"] == pending_posts["total"], "pending_count 与列表不符"
assert stats["total_count"] == all_posts["total"], "total_count 与列表不符"
print(f"  统计与列表一致: ✅")

# ============================================================
# 5. 浏览历史
# ============================================================
print("\n--- 5. 浏览历史（PRF-01.3） ---")
# user1 浏览 user2 的帖子（user2 至少有一个 published 帖子）
r = requests.get(f"{BASE}/users/me/posts?status=published&page=1&page_size=5", headers=headers2)
user2_posts = r.json().get("items", [])
if not user2_posts:
    # 兜底：使用 user1 的帖子
    target_post_id = published_posts["items"][0]["id"]
else:
    target_post_id = user2_posts[0]["id"]
print(f"目标帖子: {target_post_id}")

# 浏览前历史数
r = requests.get(f"{BASE}/users/me/view-history?page=1&page_size=20", headers=headers1)
history_before = r.json()
print(f"  浏览前历史数: {history_before['total']}")

# 访问帖子详情（写入浏览历史）
r = requests.get(f"{BASE}/posts/{target_post_id}", headers=headers1)
print(f"  访问帖子详情: {r.status_code}")
assert r.status_code == 200

# 浏览后历史数
r = requests.get(f"{BASE}/users/me/view-history?page=1&page_size=20", headers=headers1)
history_after = r.json()
print(f"  浏览后历史数: {history_after['total']}")

# 验证目标帖子在历史中
target_in_history = any(h["post_id"] == target_post_id for h in history_after["items"])
print(f"  目标帖子在历史中: {'✅' if target_in_history else '❌'}")
assert target_in_history

# 再次访问同一帖子，验证唯一约束（不重复创建）
r = requests.get(f"{BASE}/posts/{target_post_id}", headers=headers1)
r = requests.get(f"{BASE}/users/me/view-history?page=1&page_size=20", headers=headers1)
history_after_2 = r.json()
# 同一帖子应该只有一条记录
target_count = sum(1 for h in history_after_2["items"] if h["post_id"] == target_post_id)
print(f"  重复访问后该帖子历史记录数: {target_count} (期望 1)")
assert target_count == 1, "同一帖子应只有一条历史记录"

# 删除单条浏览历史
r = requests.delete(f"{BASE}/users/me/view-history/{target_post_id}", headers=headers1)
print(f"  删除单条历史: {r.status_code} {r.json()}")
assert r.status_code == 200

r = requests.get(f"{BASE}/users/me/view-history?page=1&page_size=20", headers=headers1)
history_after_delete = r.json()
target_still = any(h["post_id"] == target_post_id for h in history_after_delete["items"])
print(f"  删除后该帖子不在历史中: {'✅' if not target_still else '❌'}")
assert not target_still

# 清空当前学校全部浏览历史
r = requests.delete(f"{BASE}/users/me/view-history", headers=headers1)
print(f"  清空全部历史: {r.status_code} {r.json()}")
assert r.status_code == 200

r = requests.get(f"{BASE}/users/me/view-history?page=1&page_size=20", headers=headers1)
history_cleared = r.json()
print(f"  清空后历史数: {history_cleared['total']} (期望 0)")
assert history_cleared["total"] == 0, "清空后历史应为 0"

# ============================================================
# 6. 通知偏好（NotificationPreference）
# ============================================================
print("\n--- 6. 通知偏好（如端点存在） ---")
# 尝试获取通知偏好
r = requests.get(f"{BASE}/notifications/preferences", headers=headers1)
print(f"  GET /notifications/preferences: {r.status_code}")
if r.status_code == 200:
    prefs = r.json()
    print(f"    {prefs}")
    # 尝试更新
    if isinstance(prefs, dict):
        update_data = dict(prefs)
        if "subscription_enabled" in update_data:
            original = update_data["subscription_enabled"]
            update_data["subscription_enabled"] = not original
            r = requests.put(
                f"{BASE}/notifications/preferences",
                json=update_data,
                headers=headers1,
            )
            print(f"  PUT /notifications/preferences: {r.status_code}")
            if r.status_code == 200:
                new_prefs = r.json()
                toggle_ok = new_prefs.get("subscription_enabled") == (not original)
                print(f"    切换 subscription_enabled: {'✅' if toggle_ok else '❌'}")
                # 还原
                update_data["subscription_enabled"] = original
                requests.put(
                    f"{BASE}/notifications/preferences",
                    json=update_data,
                    headers=headers1,
                )
                print(f"    已还原")
else:
    print(f"  通知偏好端点不可用（可能未实现）: {r.text[:100]}")

print("\n" + "=" * 60)
print("个人中心 E2E 验证完成")
print("=" * 60)
