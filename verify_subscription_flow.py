"""E2E 验证脚本：专题订阅通知完整链路（创建→审核→订阅通知触发）"""
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
print("专题订阅通知完整链路（创建→审核→订阅通知触发）")
print("=" * 60)

# user1 登录（订阅者）
token1 = login("user1@example.com")
headers1 = h(token1)

# 检查 user1 当前订阅与通知数
r = requests.get(f"{BASE}/subscriptions", headers=headers1)
print(f"User1 订阅数: {r.json().get('total', 0)}")
subs = r.json().get("items", [])
topic_sub_id = None
sub_topic_id = None
for s in subs:
    if s.get("target_type") == "topic":
        topic_sub_id = s["id"]
        sub_topic_id = s["target_id"]
        print(f"  已订阅 topic_id={sub_topic_id} (sub_id={topic_sub_id}, name={s.get('target_name')})")

r = requests.get(f"{BASE}/notifications?limit=20", headers=headers1)
notif_before = r.json().get("total", 0) if r.status_code == 200 else 0
print(f"User1 通知数（操作前）: {notif_before}")

# user2 登录（发帖者）
token2 = login("user2@example.com")
headers2 = h(token2)

# 获取分类与帖子类型
r = requests.get(f"{BASE}/categories", headers=headers2)
cats = r.json() if r.status_code == 200 else []
r = requests.get(f"{BASE}/post-types", headers=headers2)
ptypes = r.json() if r.status_code == 200 else []

if sub_topic_id and cats and ptypes:
    cat_id = cats[0]["id"]
    pt_id = ptypes[0]["id"]

    # user2 创建帖子（关联到 user1 订阅的 topic）
    r = requests.post(
        f"{BASE}/posts",
        json={
            "title": "[E2E订阅链路] 审核通过触发订阅通知",
            "content": "验证：user2 发帖关联 topic → admin 审核通过 → user1 收到订阅通知。这条内容长度足够通过校验。",
            "category_id": cat_id,
            "post_type_id": pt_id,
            "topic_id": sub_topic_id,
        },
        headers=headers2,
    )
    print(f"\nUser2 创建帖子: {r.status_code}")
    if r.status_code == 201:
        new_post_id = r.json()["id"]
        print(f"  post_id={new_post_id}, status={r.json().get('status')}")

        # admin 登录审核
        token_admin = login("admin@momentcampus.com")
        headers_admin = h(token_admin)

        # 审核通过
        r = requests.put(
            f"{BASE}/admin/posts/{new_post_id}/approve",
            json={"reason": "审核通过，触发订阅通知测试"},
            headers=headers_admin,
        )
        print(f"Admin 审核通过: {r.status_code} {r.text[:200]}")

        # 等待通知生成（异步）
        time.sleep(1)

        # 检查 user1 通知数变化
        r = requests.get(f"{BASE}/notifications?limit=20", headers=headers1)
        notif_after = r.json().get("total", 0) if r.status_code == 200 else 0
        print(f"\nUser1 通知数（操作后）: {notif_after} (变化: +{notif_after - notif_before})")

        # 列出最新通知
        r = requests.get(f"{BASE}/notifications?limit=5", headers=headers1)
        if r.status_code == 200:
            notifs = r.json().get("items", [])
            print("\n最新通知:")
            for n in notifs[:5]:
                print(f"  Type={n.get('type')} Title={n.get('title','')[:60]} Read={n.get('is_read')}")
                if n.get("related_post_id") == new_post_id:
                    print(f"    *** 命中订阅通知: post_id={new_post_id} ***")

        # 验证帖子在首页可见
        r = requests.get(f"{BASE}/posts?status=published&page_size=20", headers=headers1)
        if r.status_code == 200:
            posts = r.json().get("items", [])
            found = next((p for p in posts if p["id"] == new_post_id), None)
            if found:
                print(f"\n帖子在首页可见: ✅ title={found['title'][:40]}")
            else:
                print(f"\n帖子在首页不可见: ❌")
    else:
        print(f"创建失败: {r.text[:200]}")
else:
    print("缺少必要条件（订阅/分类/帖子类型）")

print("\n" + "=" * 60)
print("专题订阅通知完整链路验证完成")
print("=" * 60)
