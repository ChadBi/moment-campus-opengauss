"""重置开发库中指定邮箱用户的全链路关联数据（严格符合 AGENTS.md 规则）。

严格流程：
    Phase 1: 枚举所有含 user_id 列的表 → 导出该用户记录 → JSON 备份到 delete/
    Phase 2: 按子表 FK 方向多趟 DELETE → 最后 DELETE users 父表记录
    Phase 3: VERIFY — 重新扫描所有 21 张表确认残留记录总数为 0

环境变量要求：
    $env:APP_ENV = "opengauss"

使用：
    只需要修改本文件顶部的 TARGET_EMAIL 常量即可复用给任意其他用户。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime
from pathlib import Path

# ==============================================
# ★ 只需修改这里：目标账号邮箱
# ==============================================
TARGET_EMAIL = "1030424433@stu.jiangnan.edu.cn"

APP_ROOT = Path(__file__).resolve().parents[1]  # backend/
PROJECT_ROOT = APP_ROOT.parent
DELETE_DIR = PROJECT_ROOT / "delete"
DELETE_DIR.mkdir(exist_ok=True)

# 必须在任何 app.* import 之前设置 APP_ENV
os.environ.setdefault("APP_ENV", "opengauss")
os.chdir(APP_ROOT)  # 让相对路径类的 import 正常

import sys
sys.path.insert(0, str(APP_ROOT))

from sqlalchemy import select, text, delete as sqla_delete  # noqa: E402

from app.database import async_session_maker, engine  # noqa: E402


def _json_safe(value):
    """让 datetime / bytes 也能被 json.dump 序列化。"""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    return value


async def find_user_id_by_email(db, email: str) -> int | None:
    from app.models.user import User  # noqa: WPS433 lazy import to avoid startup side-effects
    row = (await db.execute(
        select(User.id, User.email).where(User.email == email)
    )).first()
    return int(row[0]) if row else None


async def enumerate_tables_with_user_id(db) -> list[str]:
    """从 information_schema 找出所有含 user_id 列的 public 表（子表）。"""
    rows = (await db.execute(text("""
        SELECT table_name
        FROM   information_schema.columns
        WHERE  table_schema = 'public'
          AND  column_name  = 'user_id'
        ORDER BY table_name
    """))).all()
    return [r[0] for r in rows if r and r[0] != "users"]


async def snapshot_table(db, table: str, user_id: int, *, use_id_pk: bool = False) -> list[dict]:
    col = "id" if use_id_pk else "user_id"
    rows = (await db.execute(
        text(f'SELECT * FROM {table} WHERE {col} = :uid'), {"uid": user_id}
    )).mappings().all()
    return [{k: _json_safe(v) for k, v in dict(r).items()} for r in rows]


async def main():  # noqa: WPS213 - 主流程长点没问题
    async with async_session_maker() as db:
        print(f"[INFO] 锁定目标邮箱：{TARGET_EMAIL}")
        user_id = await find_user_id_by_email(db, TARGET_EMAIL)
        if user_id is None:
            # 可能已经清理过了，找备份文件里 uid 也可以
            print(f"[WARN] users 表查不到邮箱 {TARGET_EMAIL}，尝试从已有备份拿 user_id…")
            import re
            backups = sorted(DELETE_DIR.glob("user_id*_*_backup_*.json"))
            matched = None
            for b in backups:
                if TARGET_EMAIL.replace("@", "_at_").replace(".", ".") in b.name:
                    m = re.search(r"user_id(\d+)", b.name)
                    if m:
                        matched = int(m.group(1))
                        break
            if matched is None:
                print("[EXIT] 无法定位目标 user_id，脚本已中止（无需再删？）。")
                return
            user_id = matched
            print(f"[INFO] 从历史备份定位到 user_id={user_id}，继续执行子表残留扫描+删除。")

        child_tables = await enumerate_tables_with_user_id(db)
        all_tables = child_tables + ["users"]
        print(f"[INFO] 扫描到 {len(child_tables)} 张子表 + users 父表 = {len(all_tables)} 张待清理表：\n  - "
              + "\n  - ".join(all_tables))

        # =========================
        # Phase 1: 备份
        # =========================
        print("\n===== Phase 1. 备份所有 user_id=%d 行 =====" % user_id)
        backup: dict = {"TARGET_EMAIL": TARGET_EMAIL, "user_id": user_id,
                        "exported_at": datetime.now().isoformat(timespec="seconds"),
                        "tables": {}}
        total_backed_up = 0
        for tbl in child_tables:
            rows = await snapshot_table(db, tbl, user_id, use_id_pk=False)
            backup["tables"][tbl] = rows
            if rows:
                print(f"  + {tbl}: {len(rows)} 条 → 备份")
                total_backed_up += len(rows)
            else:
                print(f"  - {tbl}: 0 条跳过")
        # users 父表主键列是 id
        rows = await snapshot_table(db, "users", user_id, use_id_pk=True)
        backup["tables"]["users"] = rows
        if rows:
            print(f"  + users: {len(rows)} 条 → 备份")
            total_backed_up += len(rows)
        else:
            print(f"  - users: 0 条跳过")

        safe_email = TARGET_EMAIL.replace("@", "_at_").replace(".", ".")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = DELETE_DIR / f"user_id{user_id}_{safe_email}_backup_{ts}.json"
        backup_path.write_text(json.dumps(backup, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[DONE] 备份文件：{backup_path}（共 {total_backed_up} 条记录）")

        # =========================
        # Phase 2: 多趟 DELETE 子表 → 最后删 users 父表
        # =========================
        print("\n===== Phase 2. DELETE 清理 =====")
        total_deleted = 0
        # 先多趟子表（最多 3 遍，避免循环 FK）
        for pass_idx in range(1, 4):
            pass_deleted = 0
            for tbl in child_tables:
                res = await db.execute(
                    text(f'DELETE FROM {tbl} WHERE user_id = :uid'), {"uid": user_id}
                )
                pass_deleted += res.rowcount or 0
            await db.commit()
            total_deleted += pass_deleted
            print(f"  [pass {pass_idx}] 子表删除 {pass_deleted} 行（累计 {total_deleted}）")
            if pass_deleted == 0:
                break

        # 最后删除 users
        res = await db.execute(text('DELETE FROM users WHERE id = :uid'), {"uid": user_id})
        users_del = res.rowcount or 0
        await db.commit()
        total_deleted += users_del
        print(f"  [parent] users 删除 {users_del} 行（累计删除 {total_deleted} 条）")

        # =========================
        # Phase 3: VERIFY 清零验证
        # =========================
        print("\n===== Phase 3. 残留验证 =====")
        residual_total = 0
        for tbl in child_tables:
            cnt = (await db.execute(
                text(f'SELECT COUNT(*) FROM {tbl} WHERE user_id = :uid'), {"uid": user_id}
            )).scalar_one()
            residual_total += cnt or 0
            if cnt:
                print(f"  !! {tbl}: 残留 {cnt} 条")
            else:
                print(f"  OK {tbl}: 0 条")
        # users 父表用 id
        cnt = (await db.execute(
            text('SELECT COUNT(*) FROM users WHERE id = :uid'), {"uid": user_id}
        )).scalar_one()
        residual_total += cnt or 0
        if cnt:
            print(f"  !! users: 残留 {cnt} 条")
        else:
            print(f"  OK users: 0 条")
        print(f"\n[VERIFY] {len(all_tables)} 张表残留总条数 = {residual_total}")
        if residual_total == 0:
            print("VERIFY PASS ✅")
        else:
            print("VERIFY FAIL ❌，残留 %d 条，请人工检查。" % residual_total)
            raise SystemExit(2)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
