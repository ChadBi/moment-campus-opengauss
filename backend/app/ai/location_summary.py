"""AI-04：地点摘要结构化输出约束。"""
from typing import Any


LOCATION_SUMMARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary_text", "claims", "conflicts"],
    "properties": {
        "summary_text": {"type": ["string", "null"], "maxLength": 1200},
        "claims": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["claim_id", "text", "source_refs"],
                "properties": {
                    "claim_id": {"type": "string", "maxLength": 60},
                    "text": {"type": "string", "minLength": 1, "maxLength": 300},
                    "source_refs": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": 20,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["source_type", "source_id"],
                            "properties": {
                                "source_type": {"type": "string", "enum": ["post", "review", "fact"]},
                                "source_id": {"type": "integer", "minimum": 1},
                            },
                        },
                    },
                },
            },
        },
        "conflicts": {
            "type": "array",
            "maxItems": 8,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["text", "source_refs"],
                "properties": {
                    "text": {"type": "string", "minLength": 1, "maxLength": 300},
                    "source_refs": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 20,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["source_type", "source_id"],
                            "properties": {
                                "source_type": {"type": "string", "enum": ["post", "review", "fact"]},
                                "source_id": {"type": "integer", "minimum": 1},
                            },
                        },
                    },
                },
            },
        },
    },
}
