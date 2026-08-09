"""AI-01.1: 结构化输出 JSON Schema 定义与校验。

职责：
1. 预定义 AI-02（搜索意图解析）与 AI-03（发布建议）所需的 JSON Schema，
   供 Provider 层在拿到模型输出后做结构化校验。
2. 提供 validate_structured_output(data, schema) 工具：
   - 校验失败抛 AIJSONParseError（带可读的校验路径信息）。
   - 校验通过返回 data 本身。

设计原则：
- Schema 只约束结构（字段名/类型/枚举），不约束业务白名单（白名单由上层场景校验）。
- 这里不引入业务依赖，仅依赖 jsonschema 标准库。
"""
from __future__ import annotations

from typing import Any

import jsonschema
from jsonschema import ValidationError

from app.ai.exceptions import AIJSONParseError


# ============================================================
# AI-02: 搜索意图解析 Schema
# 模型必须返回如下结构（reasons 可空，filters 内字段均可空）
# ============================================================
SEARCH_INTENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent", "filters"],
    "properties": {
        "intent": {
            "type": "string",
            "description": "用户搜索意图的自然语言概述",
        },
        "filters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "keyword": {"type": ["string", "null"]},
                "category": {"type": ["string", "null"]},
                "sort": {
                    "type": ["string", "null"],
                    "enum": ["latest", "hottest", "active", "relevance", None],
                },
                "date_from": {"type": ["string", "null"]},
                "date_to": {"type": ["string", "null"]},
                "map_bounds": {
                    "type": ["object", "null"],
                    "additionalProperties": False,
                    "properties": {
                        "north": {"type": "number"},
                        "south": {"type": "number"},
                        "east": {"type": "number"},
                        "west": {"type": "number"},
                    },
                    "required": ["north", "south", "east", "west"],
                },
            },
        },
        "reasons": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
    },
}


# ============================================================
# AI-03: 发布建议 Schema
# 模型必须返回 suggestions + missing_info + sensitive_warnings 三段
# 注：白名单（分类/标签）由 service 层校验，schema 只约束结构
# ============================================================
PUBLISH_SUGGESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["suggestions", "missing_info", "sensitive_warnings"],
    "properties": {
        "suggestions": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "title",
                "category",
                "tags",
                "default_validity_days",
            ],
            "properties": {
                "title": {"type": ["string", "null"]},
                "optimized_title": {"type": ["string", "null"]},
                "optimized_content": {"type": ["string", "null"]},
                "summary": {"type": ["string", "null"]},
                "category": {"type": ["string", "null"]},
                "tags": {
                    "type": ["array", "null"],
                    "items": {"type": "string"},
                },
                "default_validity_days": {"type": ["integer", "null"]},
            },
        },
        "missing_info": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
        "sensitive_warnings": {
            "type": ["array", "null"],
            "items": {"type": "string"},
        },
    },
}


def _strip_additional_properties(data: Any, schema: dict[str, Any]) -> Any:
    """递归剥离 schema 中未声明的额外字段。

    部分模型（如 DeepSeek）在 response_format=json_object 模式下仍会回显输入字段，
    导致 additionalProperties:false 的严格校验失败。本函数在校验前清洗数据，
    仅保留 schema.properties 中声明的键。
    """
    if not isinstance(schema, dict):
        return data

    schema_type = schema.get("type")

    if schema_type == "object" and isinstance(data, dict):
        properties = schema.get("properties", {})
        allowed_keys = set(properties.keys())
        stripped = {k: data[k] for k in data if k in allowed_keys}
        for key, sub_schema in properties.items():
            if key in stripped:
                stripped[key] = _strip_additional_properties(stripped[key], sub_schema)
        return stripped

    if schema_type == "array" and isinstance(data, list):
        items_schema = schema.get("items", {})
        return [_strip_additional_properties(item, items_schema) for item in data]

    return data


def validate_structured_output(data: Any, schema: dict[str, Any]) -> Any:
    """用 JSON Schema 校验模型结构化输出。

    校验前会自动剥离 schema 未声明的额外字段（应对 AI 回显输入字段的情况）。

    Args:
        data: 已解析的 Python 对象（通常为 dict）
        schema: JSON Schema 字典

    Returns:
        校验通过时返回清洗后的 data。

    Raises:
        AIJSONParseError: 校验失败，message 含可读的校验路径与原因。
    """
    cleaned = _strip_additional_properties(data, schema)
    try:
        jsonschema.validate(instance=cleaned, schema=schema)
    except ValidationError as exc:
        path = ".".join(str(p) for p in exc.absolute_path) or "<root>"
        raise AIJSONParseError(
            f"结构化输出校验失败：路径 {path} - {exc.message}",
            provider_message=exc.message,
        ) from exc
    return cleaned
