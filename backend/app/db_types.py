"""openGauss 原生 DataVec 类型适配。"""
from __future__ import annotations

from typing import Any

from sqlalchemy.types import UserDefinedType


class Vector(UserDefinedType):
    """SQLAlchemy 对 openGauss ``vector(n)`` 的轻量映射。"""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **kw: Any) -> str:
        return f"vector({self.dimensions})"

    def bind_processor(self, dialect):
        def process(value):
            if value is None or isinstance(value, str):
                return value
            return "[" + ",".join(format(float(item), ".12g") for item in value) + "]"
        return process

    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None or isinstance(value, list):
                return value
            text = str(value).strip("[]")
            return [float(item) for item in text.split(",")] if text else []
        return process

