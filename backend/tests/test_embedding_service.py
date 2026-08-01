from types import SimpleNamespace
import math

import pytest


@pytest.mark.asyncio
async def test_generate_embedding_uses_independent_openai_compatible_settings(monkeypatch):
    from app.services import embedding_service

    captured = {}

    class FakeEmbeddings:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.25] * 512)])

    fake_client = SimpleNamespace(embeddings=FakeEmbeddings())
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_API_KEY", "embedding-only-key")
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_API_BASE", "https://embedding.example/v1")
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_MODEL", "text-embedding-512")
    monkeypatch.setattr(embedding_service, "_get_client", lambda: fake_client)

    vector = await embedding_service.generate_embedding("  标题\n内容  ")

    assert vector == [0.25] * 512
    assert captured == {
        "model": "text-embedding-512",
        "input": "标题\n内容",
        "dimensions": 512,
    }


@pytest.mark.asyncio
async def test_generate_embedding_rejects_wrong_dimension_without_leaking_key(monkeypatch, caplog):
    from app.services import embedding_service

    class FakeEmbeddings:
        async def create(self, **kwargs):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1] * 3)])

    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_API_KEY", "must-not-appear")
    monkeypatch.setattr(embedding_service, "_get_client", lambda: SimpleNamespace(embeddings=FakeEmbeddings()))

    assert await embedding_service.generate_embedding("测试") is None
    assert "must-not-appear" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_value", [math.nan, math.inf, -math.inf])
async def test_generate_embedding_rejects_non_finite_values_and_degrades_safely(
    monkeypatch, caplog, invalid_value,
):
    from app.services import embedding_service

    vector = [0.1] * 512
    vector[17] = invalid_value

    class FakeEmbeddings:
        async def create(self, **kwargs):
            return SimpleNamespace(data=[SimpleNamespace(embedding=vector)])

    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_PROVIDER", "openai")
    monkeypatch.setattr(embedding_service.settings, "EMBEDDING_API_KEY", "finite-check-secret")
    monkeypatch.setattr(
        embedding_service,
        "_get_client",
        lambda: SimpleNamespace(embeddings=FakeEmbeddings()),
    )

    assert await embedding_service.generate_embedding("不得写入非法向量") is None
    assert "finite-check-secret" not in caplog.text
    assert "不得写入非法向量" not in caplog.text


def test_build_post_embedding_text_is_stable_and_bounded():
    from app.services.embedding_service import build_post_embedding_text

    text = build_post_embedding_text(" 标题 ", " 正文 ")

    assert text == "标题\n正文"
