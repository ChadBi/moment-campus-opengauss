"""T7b: posts.embedding 维度 384→512（适配阿里云百炼 qwen3.7-text-embedding）。

Revision ID: b6c7d8e9f0a1
Revises: a1b2c3d4e5f6
"""
from typing import Sequence, Union

from alembic import op

revision: str = "b6c7d8e9f0a1"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 先删 HNSW 索引，再改列类型，最后重建索引
    op.execute("DROP INDEX IF EXISTS idx_posts_embedding_hnsw")
    op.execute("ALTER TABLE posts ALTER COLUMN embedding TYPE vector(512)")
    op.execute(
        "CREATE INDEX idx_posts_embedding_hnsw "
        "ON posts USING hnsw (embedding vector_l2_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_posts_embedding_hnsw")
    op.execute("ALTER TABLE posts ALTER COLUMN embedding TYPE vector(384)")
    op.execute(
        "CREATE INDEX idx_posts_embedding_hnsw "
        "ON posts USING hnsw (embedding vector_l2_ops)"
    )
