"""E2E 验证脚本：协同治理 5 类验证完整链路（GOV-01.2）

5 类协同验证：
  - 2 类互斥投票（validations）：confirmation（证实）/ refutation（证伪）
  - 3 类问题报告（change-reports）：update（更新建议）/ expiration_report（过期报告）/ conflict_report（冲突报告）

场景：
1. user1 创建帖子，admin 审核通过
2. user2 提交 confirmation 投票 → 聚合统计正确
3. user3 提交 refutation 投票 → 聚合统计正确（uncertain 状态）
4. user2 投票替换为 refutation → 替换语义正确（计数 -1/+1）
5. user1 不能给自己帖子投票（403）
6. user3 提交 update 报告
7. user3 提交 expiration_report 报告
8. user2 提交 conflict_report 报告
9. user3 重复提交 update 报告 → 400 拒绝
10. 列表查询：3 类报告齐全
11. admin 处理 update 报告 → resolved
12. 帖子作者 user1 标记 conflict_report → resolved
13. 帖子作者 user1 流转 update 报告至 dismissed → 403
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
print("协同治理 5 类验证 E2E 链路验证")
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
        "title": "[E2E协同治理] 5类验证测试帖",
        "content": "本帖用于测试 GOV-01.2 协同治理 5 类验证：证实、证伪、更新建议、过期报告、冲突报告。",
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
# 2. 3 类问题报告：update / expiration_report / conflict_report
# ============================================================
print("\n--- 2. 3 类问题报告（update / expiration_report / conflict_report） ---")

# user3 提交 update 报告
r = requests.post(
    f"{BASE}/posts/{post_id}/change-reports",
    json={
        "report_type": "update",
        "description": "建议更新内容：标题里的活动时间已过期",
        "evidence_url": "https://example.com/evidence/update.png",
    },
    headers=headers3,
)
print(f"User3 提交 update 报告: {r.status_code}")
assert r.status_code == 201, f"提交 update 报告失败: {r.text}"
update_report_id = r.json()["id"]

# user3 提交 expiration_report 报告
r = requests.post(
    f"{BASE}/posts/{post_id}/change-reports",
    json={
        "report_type": "expiration_report",
        "description": "活动已结束，建议标记为过期",
    },
    headers=headers3,
)
print(f"User3 提交 expiration_report 报告: {r.status_code}")
assert r.status_code == 201, f"提交 expiration_report 报告失败: {r.text}"
expiration_report_id = r.json()["id"]

# user2 提交 conflict_report 报告
r = requests.post(
    f"{BASE}/posts/{post_id}/change-reports",
    json={
        "report_type": "conflict_report",
        "description": "与另一帖子内容冲突",
        "evidence_url": "https://example.com/evidence/conflict.png",
    },
    headers=headers2,
)
print(f"User2 提交 conflict_report 报告: {r.status_code}")
assert r.status_code == 201, f"提交 conflict_report 报告失败: {r.text}"
conflict_report_id = r.json()["id"]

# user3 重复提交 update 报告 → 400
r = requests.post(
    f"{BASE}/posts/{post_id}/change-reports",
    json={
        "report_type": "update",
        "description": "再次提交 update 报告",
    },
    headers=headers3,
)
print(f"User3 重复提交 update 报告: {r.status_code} (期望 400)")
assert r.status_code == 400, f"重复提交应被拒绝，实际 {r.status_code}"

# 列表查询：3 类报告齐全
r = requests.get(f"{BASE}/posts/{post_id}/change-reports", headers=headers1)
report_list = r.json()
print(f"报告列表: total={report_list['total']} open_count={report_list['open_count']}")
assert report_list["total"] == 3, f"应有 3 个报告，实际 {report_list['total']}"
assert report_list["open_count"] == 3, "3 个报告均应为 open"
report_types = {r["report_type"] for r in report_list["items"]}
assert report_types == {"update", "expiration_report", "conflict_report"}, \
    f"3 类报告应齐全，实际 {report_types}"
print(f"  3 类报告齐全: ✅ ({report_types})")

# ============================================================
# 3. 处理报告：admin 流转 / 作者标记已处理
# ============================================================
print("\n--- 3. 报告处理（admin 流转 / 作者标记） ---")

# admin 处理 update 报告 → resolved
r = requests.put(
    f"{BASE}/governance/reports/{update_report_id}",
    json={"status": "resolved", "reason": "已联系作者更新内容"},
    headers=headers_admin,
)
print(f"Admin 处理 update 报告 → resolved: {r.status_code}")
assert r.status_code == 200, f"处理报告失败: {r.text}"
assert r.json()["status"] == "resolved"
assert r.json()["handler"]["id"] is not None

# admin 流转 expiration_report → in_review
r = requests.put(
    f"{BASE}/governance/reports/{expiration_report_id}",
    json={"status": "in_review", "reason": "核实中"},
    headers=headers_admin,
)
print(f"Admin 流转 expiration_report → in_review: {r.status_code}")
assert r.status_code == 200
assert r.json()["status"] == "in_review"

# 作者 user1 标记 conflict_report → resolved
r = requests.put(
    f"{BASE}/governance/reports/{conflict_report_id}",
    json={"status": "resolved", "reason": "已确认并修改"},
    headers=headers1,
)
print(f"作者标记 conflict_report → resolved: {r.status_code}")
assert r.status_code == 200, f"作者标记失败: {r.text}"
assert r.json()["status"] == "resolved"
assert r.json()["handler"]["id"] == 2  # user1.id

# 作者尝试流转 update（已被 admin 处理）→ dismissed（应被拒绝，作者只能 resolved）
r = requests.put(
    f"{BASE}/governance/reports/{update_report_id}",
    json={"status": "dismissed", "reason": "作者想驳回"},
    headers=headers1,
)
print(f"作者尝试 dismissed 流转: {r.status_code} (期望 403)")
assert r.status_code == 403, f"作者非 resolved 流转应被拒绝，实际 {r.status_code}"

# 普通用户 user2 处理他人报告 → 403
r = requests.put(
    f"{BASE}/governance/reports/{expiration_report_id}",
    json={"status": "resolved", "reason": "user2 想处理"},
    headers=headers2,
)
print(f"User2 处理他人报告: {r.status_code} (期望 403)")
assert r.status_code == 403

# 最终报告列表
r = requests.get(f"{BASE}/posts/{post_id}/change-reports", headers=headers1)
report_list = r.json()
print(f"\n最终报告列表: total={report_list['total']} open_count={report_list['open_count']}")
for r in report_list["items"]:
    print(f"  {r['report_type']}: status={r['status']} handler={r.get('handler', {}).get('nickname') if r.get('handler') else None}")

# 帖子详情中的 governance 聚合
r = requests.get(f"{BASE}/posts/{post_id}", headers=headers1)
post_detail = r.json()
governance = post_detail.get("governance", {})
print(f"\n帖子详情 governance 聚合:")
print(f"  confirmation_count={governance.get('confirmation_count')}")
print(f"  refutation_count={governance.get('refutation_count')}")
print(f"  validity_status={governance.get('validity_status')}")
print(f"  change_reports_total={governance.get('change_reports_total')}")
print(f"  change_reports_open={governance.get('change_reports_open')}")
print(f"  user_validation_type={governance.get('user_validation_type')}")

print("\n" + "=" * 60)
print("协同治理 5 类验证 E2E 验证完成")
print("=" * 60)
