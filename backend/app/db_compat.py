r"""openGauss 兼容性补丁。

SQLAlchemy 的 PostgreSQL 方言在 `_get_server_version_info` 中使用正则
`.*(?:PostgreSQL|EnterpriseDB) (\d+)\.?(\d+)?...` 解析 version() 字符串，
无法识别 openGauss 的版本串（如 "(openGauss 7.0.0-RC3 build ...)"），
会抛出 AssertionError。

导入本模块即可全局应用补丁：先尝试原逻辑，失败后按 openGauss 版本格式解析。
应在创建任何 SQLAlchemy 引擎之前导入。
"""
from __future__ import annotations

import re

from sqlalchemy import event
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.pool import Pool

_original_get_server_version_info = PGDialect._get_server_version_info


def _patched_get_server_version_info(self, connection):
    try:
        return _original_get_server_version_info(self, connection)
    except AssertionError:
        v = connection.exec_driver_sql("select pg_catalog.version()").scalar()
        m = re.match(r".*openGauss (\d+)\.(\d+)(?:\.(\d+))?", v)
        if not m:
            raise AssertionError(
                "Could not determine version from string '%s'" % v
            )
        return tuple(int(x) for x in m.group(1, 2, 3) if x is not None)


PGDialect._get_server_version_info = _patched_get_server_version_info


def _encode_vector(value):
    if value is None or isinstance(value, str):
        return value
    return "[" + ",".join(format(float(item), ".12g") for item in value) + "]"


def _decode_vector(value):
    if value is None:
        return None
    text = str(value).strip("[]")
    return [float(item) for item in text.split(",")] if text else []


@event.listens_for(Pool, "connect")
def _register_opengauss_vector_codec(dbapi_connection, connection_record):
    """为 asyncpg 注册 openGauss 内核级 vector 的文本 codec。"""
    run_async = getattr(dbapi_connection, "run_async", None)
    if run_async is None:
        return

    async def register(driver_connection):
        try:
            await driver_connection.set_type_codec(
                "vector",
                schema="pg_catalog",
                encoder=_encode_vector,
                decoder=_decode_vector,
                format="text",
            )
        except ValueError:
            # 兼容尚未包含 DataVec 类型的数据库实例。
            return

    run_async(register)

__all__ = []
