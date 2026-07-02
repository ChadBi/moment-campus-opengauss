r"""
openGauss asyncpg 连接测试脚本

测试 asyncpg 与 openGauss 的兼容性，包括：
1. 基础连接验证 (SELECT 1)
2. 查询版本信息 (SELECT version())
3. 建表 (CREATE TABLE)
4. 插入数据 (INSERT)
5. 查询数据 (SELECT)
6. 清理 (DROP TABLE)

使用方法：
    backend\.venv\Scripts\python.exe backend\scripts\test_opengauss_conn.py
"""
import asyncio
import sys
import traceback
from typing import Tuple

import asyncpg


# 连接配置
# 注意：密码含 @，需 URL 编码为 %40
# gaussdb 用户连接串
GAUSSDB_DSN = "postgresql://gaussdb:Gaussdb%40123@localhost:5432/moment_campus"
# omm 用户连接串（备选）
OMM_DSN = "postgresql://omm:Gaussdb%40123@localhost:5432/moment_campus"


async def run_step(name: str, coro) -> Tuple[bool, str]:
    """执行单个测试步骤，返回 (是否成功, 信息)"""
    try:
        result = await coro
        return True, str(result) if result is not None else "OK"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"


async def test_connection(dsn: str, user_label: str) -> bool:
    """对给定 DSN 执行 5 项测试，返回是否全部通过"""
    print(f"\n{'=' * 60}")
    print(f"尝试使用用户 [{user_label}] 连接 openGauss")
    print(f"DSN: {dsn}")
    print(f"{'=' * 60}")

    results = []  # [(step_name, success, info), ...]

    try:
        conn = await asyncpg.connect(dsn)
    except Exception as e:
        print(f"\n[连接失败] 无法建立连接")
        print(f"错误类型: {type(e).__name__}")
        print(f"错误信息: {e}")
        print(f"\n完整堆栈:\n{traceback.format_exc()}")
        return False

    print(f"\n[连接成功] 已建立到 openGauss 的连接\n")

    try:
        # 步骤 a: SELECT 1
        print("-" * 60)
        print("步骤 a: SELECT 1（基础连接验证）")
        ok, info = await run_step("SELECT 1", conn.fetchval("SELECT 1"))
        results.append(("a. SELECT 1", ok, info))
        print(f"  结果: {'✓ 成功' if ok else '✗ 失败'}")
        if ok:
            print(f"  返回值: {info}")
        else:
            print(f"  错误:\n{info}")

        # 步骤 b: SELECT version()
        print("\n步骤 b: SELECT version()（查询版本信息）")
        ok, info = await run_step("SELECT version()", conn.fetchval("SELECT version();"))
        results.append(("b. SELECT version()", ok, info))
        print(f"  结果: {'✓ 成功' if ok else '✗ 失败'}")
        if ok:
            print(f"  版本信息: {info}")
        else:
            print(f"  错误:\n{info}")

        # 步骤 c: CREATE TABLE
        print("\n步骤 c: CREATE TABLE _conn_test(id BIGINT PRIMARY KEY, name VARCHAR(50))")
        ok, info = await run_step(
            "CREATE TABLE",
            conn.execute(
                "CREATE TABLE _conn_test(id BIGINT PRIMARY KEY, name VARCHAR(50))"
            ),
        )
        results.append(("c. CREATE TABLE", ok, info))
        print(f"  结果: {'✓ 成功' if ok else '✗ 失败'}")
        if ok:
            print(f"  执行状态: {info}")
        else:
            print(f"  错误:\n{info}")

        # 步骤 d: INSERT
        print("\n步骤 d: INSERT INTO _conn_test VALUES (1, 'test')")
        ok, info = await run_step(
            "INSERT",
            conn.execute("INSERT INTO _conn_test VALUES (1, 'test')"),
        )
        results.append(("d. INSERT", ok, info))
        print(f"  结果: {'✓ 成功' if ok else '✗ 失败'}")
        if ok:
            print(f"  执行状态: {info}")
        else:
            print(f"  错误:\n{info}")

        # 步骤 e: SELECT * FROM _conn_test
        print("\n步骤 e: SELECT * FROM _conn_test")
        ok, info = await run_step(
            "SELECT",
            conn.fetch("SELECT * FROM _conn_test"),
        )
        results.append(("e. SELECT", ok, info))
        print(f"  结果: {'✓ 成功' if ok else '✗ 失败'}")
        if ok:
            print(f"  查询结果: {info}")
        else:
            print(f"  错误:\n{info}")

    finally:
        # 步骤 f: DROP TABLE（清理，无论前面是否成功都尝试）
        print("\n步骤 f: DROP TABLE _conn_test（清理）")
        try:
            drop_result = await conn.execute("DROP TABLE IF EXISTS _conn_test")
            results.append(("f. DROP TABLE", True, drop_result))
            print(f"  结果: ✓ 成功")
            print(f"  执行状态: {drop_result}")
        except Exception as e:
            results.append(("f. DROP TABLE", False, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"))
            print(f"  结果: ✗ 失败")
            print(f"  错误:\n{traceback.format_exc()}")
        finally:
            await conn.close()
            print("\n[连接已关闭]")

    # 汇总
    print("\n" + "=" * 60)
    print(f"测试汇总（用户: {user_label}）")
    print("=" * 60)
    all_pass = True
    for step_name, ok, _ in results:
        status = "✓ 通过" if ok else "✗ 未通过"
        print(f"  {step_name}: {status}")
        if not ok:
            all_pass = False

    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n通过: {passed}/{total}")
    if all_pass:
        print(f"结论: 5 项测试全部通过 ✓")
    else:
        print(f"结论: 存在未通过的测试 ✗")
    print("=" * 60)

    return all_pass


async def main():
    print("openGauss asyncpg 连接测试")
    print(f"Python: {sys.version.split()[0]}")
    print(f"asyncpg: {asyncpg.__version__}")

    # 优先使用 gaussdb 用户
    gaussdb_ok = await test_connection(GAUSSDB_DSN, "gaussdb")
    if gaussdb_ok:
        print("\n>>> 最终结论：使用 [gaussdb] 用户连接成功，5 项测试全部通过。")
        return 0

    # gaussdb 失败，尝试 omm 用户
    print("\n\n!!! gaussdb 用户连接失败，尝试使用 omm 用户 !!!")
    omm_ok = await test_connection(OMM_DSN, "omm")
    if omm_ok:
        print("\n>>> 最终结论：使用 [omm] 用户连接成功，5 项测试全部通过。")
        return 0

    print("\n>>> 最终结论：gaussdb 与 omm 用户均连接失败。")
    print(">>> 建议：通过 docker exec 进入容器为 omm 设置密码后重试：")
    print('    docker exec opengauss su - omm -c "gsql -d moment_campus -c "ALTER USER omm WITH PASSWORD \'Gaussdb@123\';""')
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
