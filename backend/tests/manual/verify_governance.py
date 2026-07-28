"""E2E 验证脚本：协同治理 2 类互斥投票完整链路（GOV-01.2）

Task 1.1 调整（PostChangeReport 已删除）：
  - 原 5 类协同验证 → 2 类互斥投票（validations）：confirmation（证实）/ refutation（证伪）
  - 3 类问题报告（update / expiration_report / conflict_report）已整体移除
    （与评论 / 举报功能冲突，帖子过期/冲突状态改由管理员通过举报队列处理）
  - /posts/{id}/change-reports 与 /governance/reports/{id} 端点已删除

场景：
1. user1 创建帖子，admin 审核通过
2. user2 提交 confirmation 投票 → 聚合统计正确
3. user3 提交 refutation 投票 → 聚合统计正确（uncertain 状态）
4. user2 投票替换为 refutation → 替换语义正确（计数 -1/+1）
5. user1 不能给自己帖子投票（403）
6. 帖子详情 governance 聚合字段正确
"""
import requests

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
print("协同治理 2 类互斥投票 E2E 链路验证")
print("=" * 60)

token1 = login("user1@example.com")
headers1 = h(token1)
token2 = login("user2@example.com")
headers2 = h(token2)
token3 = login("user3@example.com")
headers3 = h(token3)
token_admin = login("admin@momentcampus.com")
headers_admin = h(token_admin)

# 0. user1 创建一个新帖子用于本次测试
r = requests.get(f"{BASE}/categories", headers=headers1)
cats = r.json() if r.status_code == 200 else []
r = requests.post(
    f"{BASE}/posts",
    json={
        "title": "[E2E协同治理] 2类投票测试帖",
        "content": "本帖用于测试 GOV-01.2 协同治理 2 类互斥投票：证实、证伪。",
        "category_id": cats[0]["id"],
    },
    headers=headers1,
)
assert r.status_code == 201, f"创建帖子失败: {r.text}"
post_id = r.json()["id"]
print(f"\nUser1 创建帖子: id={post_id} status={r.json().get('status')}")

# admin 审核通过
r = requests.put(
    f"{BASE}/admin/posts/{post_id}/approve",
    json={"reason": "审核通过，用于协同治理测试"},
    headers=headers_admin,
)
print(f"Admin 审核通过: {r.status_code}")
assert r.status_code == 200, f"审核失败: {r.text}"

# ============================================================
# 1. 2 类互斥投票：confirmation / refutation
# ============================================================
print("\n--- 1. 2 类互斥投票（confirmation / refutation） ---")

# user2 投 confirmation
r = requests.post(
    f"{BASE}/posts/{post_id}/validations",
    json={"validation_type": "confirmation", "comment": "信息属实"},
    headers=headers2,
)
print(f"User2 投 confirmation: {r.status_code}")
assert r.status_code == 200, f"投票失败: {r.text}"

# user3 投 refutation
r = requests.post(
    f"{BASE}/posts/{post_id}/validations",
    json={"validation_type": "refutation", "comment": "信息有误"},
    headers=headers3,
)
print(f"User3 投 refutation: {r.status_code}")
assert r.status_code == 200, f"投票失败: {r.text}"

# 聚合查询
r = requests.get(f"{BASE}/posts/{post_id}/validations", headers=headers2)
agg = r.json()
print(f"聚合统计: confirmation={agg['confirmation_count']} refutation={agg['refutation_count']} "
      f"total={agg['total_count']} validity_status={agg['validity_status']}")
print(f"  user2 投票类型: {agg['user_validation_type']} (期望 confirmation)")
assert agg["confirmation_count"] == 1, "confirmation 计数错误"
assert agg["refutation_count"] == 1, "refutation 计数错误"
assert agg["validity_status"] == "uncertain", "1:1 应为 uncertain"
assert agg["user_validation_type"] == "confirmation"

# user1 不能给自己帖子投票
r = requests.post(
    f"{BASE}/posts/{post_id}/validations",
    json={"validation_type": "confirmation", "comment": "我是作者"},
    headers=headers1,
)
print(f"User1 给自己帖子投票: {r.status_code} (期望 403)")
assert r.status_code == 403, f"作者投票应被拒绝，实际 {r.status_code}"

# user2 替换投票为 refutation（替换语义）
r = requests.post(
    f"{BASE}/posts/{post_id}/validations",
    json={"validation_type": "refutation", "comment": "改主意，认为信息有误"},
    headers=headers2,
)
print(f"User2 替换投票为 refutation: {r.status_code}")
assert r.status_code == 200

r = requests.get(f"{BASE}/posts/{post_id}/validations", headers=headers2)
agg = r.json()
print(f"替换后统计: confirmation={agg['confirmation_count']} refutation={agg['refutation_count']}")
assert agg["confirmation_count"] == 0, "替换后 confirmation 应为 0"
assert agg["refutation_count"] == 2, "替换后 refutation 应为 2"
assert agg["validity_status"] == "invalid", "2:0 应为 invalid"

# ============================================================
# 2. 帖子详情 governance 聚合字段验证
# ============================================================
print("\n--- 2. 帖子详情 governance 聚合字段 ---")

r = requests.get(f"{BASE}/posts/{post_id}", headers=headers1)
post_detail = r.json()
governance = post_detail.get("governance", {})
print(f"帖子详情 governance 聚合:")
print(f"  confirmation_count={governance.get('confirmation_count')}")
print(f"  refutation_count={governance.get('refutation_count')}")
print(f"  total_count={governance.get('total_count')}")
print(f"  validity_status={governance.get('validity_status')}")
print(f"  user_validation_type={governance.get('user_validation_type')}")

# Task 1.2 调整：change_reports_total/open/recent_change_reports 已随 PostChangeReport 删除移除
# governance 仅保留 2 类投票聚合
assert governance.get("confirmation_count") == 0, "详情 governance confirmation_count 应为 0"
assert governance.get("refutation_count") == 2, "详情 governance refutation_count 应为 2"
assert governance.get("validity_status") == "invalid", "详情 governance validity_status 应为 invalid"

print("\n" + "=" * 60)
print("协同治理 2 类互斥投票 E2E 验证完成")
print("=" * 60)
