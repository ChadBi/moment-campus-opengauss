"""AI 地点摘要的来源和证据纯函数测试。"""

import pytest

from app.services.location_summary import (
    _location_summary_ai_options,
    _normalise_output,
    snapshot_hash,
)


def _snapshot():
    return {
        "location": {"id": 1, "name": "测试地点"},
        "facts": [{"source_type": "fact", "source_id": 9, "value": "08:00-18:00"}],
        "posts": [
            {"source_type": "post", "source_id": 1, "author_id": 11, "title": "A", "content": "动态 A"},
            {"source_type": "post", "source_id": 2, "author_id": 12, "title": "B", "content": "动态 B"},
        ],
        "reviews": [],
    }


def test_summary_claim_requires_two_independent_dynamic_authors():
    snapshot = _snapshot()
    parsed, refs = _normalise_output(
        {
            "summary_text": "近期有人反馈排队较短",
            "claims": [{
                "claim_id": "c1",
                "text": "近期有人反馈排队较短",
                "source_refs": [{"source_type": "post", "source_id": 1}],
            }],
            "conflicts": [],
        },
        snapshot,
    )
    assert parsed["claims"] == []
    assert parsed["confidence_level"] == "insufficient"
    assert refs == []


def test_summary_accepts_two_authors_and_rejects_virtual_source():
    snapshot = _snapshot()
    parsed, refs = _normalise_output(
        {
            "summary_text": "近期两位同学都提到排队较短",
            "claims": [{
                "claim_id": "c1",
                "text": "近期两位同学都提到排队较短",
                "source_refs": [
                    {"source_type": "post", "source_id": 1},
                    {"source_type": "post", "source_id": 2},
                ],
            }],
            "conflicts": [],
        },
        snapshot,
    )
    assert len(parsed["claims"]) == 1
    assert parsed["confidence_level"] == "medium"
    assert len(refs) == 2

    with pytest.raises(ValueError, match="输入快照"):
        _normalise_output(
            {
                "summary_text": "虚构来源",
                "claims": [{
                    "claim_id": "bad",
                    "text": "不应接受",
                    "source_refs": [
                        {"source_type": "post", "source_id": 1},
                        {"source_type": "post", "source_id": 99},
                    ],
                }],
                "conflicts": [],
            },
            snapshot,
        )


def test_snapshot_hash_is_stable_for_same_payload():
    assert snapshot_hash(_snapshot()) == snapshot_hash(_snapshot())


def test_location_summary_disables_deepseek_thinking_mode():
    options = _location_summary_ai_options()
    assert options.temperature == 0.1
    assert options.max_tokens == 1500
    assert options.timeout == 60.0
    assert options.thinking is False
