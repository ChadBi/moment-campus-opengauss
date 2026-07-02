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

from sqlalchemy.dialects.postgresql.base import PGDialect

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

__all__ = []
