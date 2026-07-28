"""E2E 验证脚本：专题订阅通知完整链路（修复后验证）

场景：user1 订阅专题 → user2 发帖 → admin 审核通过 → admin 将帖子加入专题 → user1 收到订阅通知
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
print("专题订阅通知完整链路验证（修复后）")
print("=" * 60)

# 三个账号登录
token1 = login("user1@example.com")
headers1 = h(token1)
token2 = login("user2@example.com")
headers2 = h(token2)
token_admin = login("admin@momentcampus.com")
headers_admin = h(token_admin)

# 1. user1 检查订阅
r = requests.get(f"{BASE}/subscriptions", headers=headers1)
print(f"\nUser1 订阅列表: {r.status_code}")
subs = r.json().get("items", [])
sub_topic_id = None
for s in subs:
    if s.get("target_type") == "topic":
        sub_topic_id = s["target_id"]
        print(f"  已订阅 topic_id={sub_topic_id} name={s.get('target_name')}")

if not sub_topic_id:
    # 获取一个专题并订阅
    r = requests.get(f"{BASE}/topics", headers=headers1)
    topics = r.json().get("items", [])
    if topics:
        sub_topic_id = topics[0]["id"]
        r = requests.post(
            f"{BASE}/subscriptions",
            json={"target_type": "topic", "target_id": sub_topic_id},
            headers=headers1,
        )
        print(f"  新订阅 topic_id={sub_topic_id}: {r.status_code}")

# 2. 记录 user1 通知数
r = requests.get(f"{BASE}/notifications?limit=50", headers=headers1)
notif_before = r.json().get("total", 0) if r.status_code == 200 else 0
print(f"\nUser1 通知数（操作前）: {notif_before}")

# 3. user2 创建帖子
r = requests.get(f"{BASE}/categories", headers=headers2)
cats = r.json() if r.status_code == 200 else []

r = requests.post(
    f"{BASE}/posts",
    json={
        "title": "[E2E订阅链路修复验证] 加入专题触发订阅通知",
        "content": "验证修复：admin 将帖子加入专题后，订阅该专题的 user1 应收到 subscription_new 通知。这条内容长度足够通过校验。",
        "category_id": cats[0]["id"],
    },
    headers=headers2,
)
print(f"\nUser2 创建帖子: {r.status_code}")
new_post_id = r.json()["id"] if r.status_code == 201 else None
print(f"  post_id={new_post_id}, status={r.json().get('status')}")

# 4. admin 审核通过
r = requests.put(
    f"{BASE}/admin/posts/{new_post_id}/approve",
    json={"reason": "审核通过，准备加入专题"},
    headers=headers_admin,
)
print(f"Admin 审核通过: {r.status_code} {r.text[:100]}")

# 5. admin 将帖子加入专题
r = requests.post(
    f"{BASE}/admin/topics/{sub_topic_id}/posts",
    json={"posts": [{"post_id": new_post_id, "sort_order": 0}]},
    headers=headers_admin,
)
print(f"Admin 将帖子加入专题: {r.status_code} {r.text[:200]}")

# 6. 等待通知生成
time.sleep(2)

# 7. 检查 user1 通知数变化
r = requests.get(f"{BASE}/notifications?limit=50", headers=headers1)
notif_after = r.json().get("total", 0) if r.status_code == 200 else 0
print(f"\nUser1 通知数（操作后）: {notif_after} (变化: +{notif_after - notif_before})")

# 8. 列出最新通知
r = requests.get(f"{BASE}/notifications?limit=5", headers=headers1)
if r.status_code == 200:
    notifs = r.json().get("items", [])
    print("\n最新通知:")
    for n in notifs[:5]:
        print(f"  Type={n.get('type')} Title={n.get('title','')[:60]} Read={n.get('is_read')}")
        if n.get("target_id") == new_post_id:
            print(f"    *** 命中订阅通知: post_id={new_post_id} ***")

# 9. 验证帖子在专题详情中可见
r = requests.get(f"{BASE}/topics/{sub_topic_id}", headers=headers1)
if r.status_code == 200:
    topic_posts = r.json().get("posts", [])
    found = any(p.get("id") == new_post_id for p in topic_posts)
    print(f"\n帖子在专题详情中可见: {'✅' if found else '❌'}")

print("\n" + "=" * 60)
print("验证完成")
print("=" * 60)
