"""E2E 验证脚本：专题订阅通知链路 + 个人中心 + 通知中心"""
import requests
import json

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
print("场景1：专题订阅通知链路")
print("=" * 60)

# user1 登录
token1 = login("13900000002")
headers1 = h(token1)

# 列出专题
r = requests.get(f"{BASE}/topics", headers=headers1)
print(f"GET /topics: {r.status_code}")
topics = r.json().get("items", [])
print(f"Topics: {len(topics)}")
for t in topics[:3]:
    print(f"  Topic ID={t['id']} name={t.get('name','')[:30]}")

if topics:
    topic_id = topics[0]["id"]
    print(f"\n使用 topic_id={topic_id}")

    # 检查订阅状态
    r = requests.get(
        f"{BASE}/subscriptions/check?target_type=topic&target_id={topic_id}",
        headers=headers1,
    )
    print(f"Check subscription: {r.status_code} {r.text[:200]}")

    # 如果未订阅，则订阅
    sub_id = None
    r_data = r.json() if r.status_code == 200 else {}
    if not r_data.get("subscribed"):
        r = requests.post(
            f"{BASE}/subscriptions",
            json={"target_type": "topic", "target_id": topic_id},
            headers=headers1,
        )
        print(f"Subscribe: {r.status_code} {r.text[:200]}")
        if r.status_code in (200, 201):
            sub_id = r.json().get("id")
    else:
        sub_id = r_data.get("subscription_id")
        print(f"Already subscribed, sub_id={sub_id}")

    # 列出我的订阅
    r = requests.get(f"{BASE}/subscriptions", headers=headers1)
    print(f"My subscriptions: {r.status_code} {r.text[:400]}")

# 测试用 user2 创建一个属于该 topic 的帖子，触发通知
print("\n--- 用 user2 创建帖子触发订阅通知 ---")
token2 = login("13900000003")
headers2 = h(token2)

# 先获取分类
r = requests.get(f"{BASE}/categories", headers=headers2)
cats = r.json() if r.status_code == 200 else []
print(f"Categories: {len(cats)}")

# 创建帖子（如果有 topic_id）
if topics and cats:
    cat_id = cats[0]["id"]
    topic_id = topics[0]["id"]
    r = requests.post(
        f"{BASE}/posts",
        json={
            "title": "[E2E订阅测试] 订阅通知触发帖",
            "content": "用于验证专题订阅后新内容通知链路。这条内容长度足够通过校验。",
            "category_id": cat_id,
            "topic_id": topic_id,
        },
        headers=headers2,
    )
    print(f"Create post: {r.status_code} {r.text[:300]}")
    new_post_id = r.json().get("id") if r.status_code in (200, 201) else None

    # 由于新帖子是 pending 状态，订阅通知可能不会立即触发
    # 检查 user1 的通知列表
    print("\n--- 检查 user1 通知 ---")
    r = requests.get(f"{BASE}/notifications?limit=5", headers=headers1)
    print(f"User1 notifications: {r.status_code}")
    notifs = r.json().get("items", []) if r.status_code == 200 else []
    print(f"Total: {r.json().get('total', 0) if r.status_code == 200 else 0}")
    for n in notifs[:5]:
        print(f"  Type={n.get('type')} Title={n.get('title','')[:50]} Read={n.get('is_read')}")

print("\n" + "=" * 60)
print("场景2：个人中心统计与资料编辑")
print("=" * 60)

# 个人中心统计
r = requests.get(f"{BASE}/users/me/stats", headers=headers1)
print(f"User stats: {r.status_code} {r.text[:400]}")

# 浏览历史
r = requests.get(f"{BASE}/users/me/view-history?limit=5", headers=headers1)
print(f"Browse history: {r.status_code} total={r.json().get('total', 0) if r.status_code == 200 else 'N/A'}")

# 我的发布
r = requests.get(f"{BASE}/users/me/posts?limit=5", headers=headers1)
print(f"My posts: {r.status_code} total={r.json().get('total', 0) if r.status_code == 200 else 'N/A'}")

# 我的发布 - 按状态筛选
r = requests.get(f"{BASE}/users/me/posts?status=published&limit=5", headers=headers1)
print(f"My published posts: {r.status_code} total={r.json().get('total', 0) if r.status_code == 200 else 'N/A'}")

# 编辑个人资料
r = requests.put(
    f"{BASE}/users/me",
    json={"nickname": "江南小李", "bio": "[E2E更新] 测试简介"},
    headers=headers1,
)
print(f"Update profile: {r.status_code} {r.text[:300]}")

# 验证更新
r = requests.get(f"{BASE}/users/me", headers=headers1)
print(f"Verify profile: {r.status_code} bio={r.json().get('bio') if r.status_code == 200 else 'N/A'}")

print("\n" + "=" * 60)
print("场景3：通知中心已读切换")
print("=" * 60)

# 获取通知列表
r = requests.get(f"{BASE}/notifications?limit=3", headers=headers1)
print(f"Notifications: {r.status_code} total={r.json().get('total', 0) if r.status_code == 200 else 'N/A'}")
notifs = r.json().get("items", []) if r.status_code == 200 else []

if notifs:
    # 找一条未读通知
    unread = next((n for n in notifs if not n.get("is_read")), None)
    if unread:
        nid = unread["id"]
        print(f"Marking notification {nid} as read...")
        r = requests.put(f"{BASE}/notifications/{nid}/read", headers=headers1)
        print(f"Mark read: {r.status_code} {r.text[:200]}")

        # 验证已读
        r = requests.get(f"{BASE}/notifications?limit=3", headers=headers1)
        notifs2 = r.json().get("items", []) if r.status_code == 200 else []
        updated = next((n for n in notifs2 if n["id"] == nid), None)
        if updated:
            print(f"  Verified is_read={updated.get('is_read')}")
    else:
        print("No unread notification found")

    # 全部已读
    r = requests.put(f"{BASE}/notifications/read-all", headers=headers1)
    print(f"Mark all read: {r.status_code} {r.text[:200]}")

    # 验证未读数
    r = requests.get(f"{BASE}/notifications?limit=3", headers=headers1)
    if r.status_code == 200:
        print(f"After read-all: unread_count={r.json().get('unread_count', 0)}")

print("\n" + "=" * 60)
print("所有场景验证完成")
print("=" * 60)
